import time

from django.core.management.base import BaseCommand
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from cities_api.models import City
from cities_api.views import PROXIMITY_FIELDS

# (name, lat, lng) search points used for timing
TEST_POINTS = [
    ('Dublin', 53.3498, -6.2603),
    ('London', 51.5074, -0.1278),
    ('New York', 40.7128, -74.0060),
    ('Tokyo', 35.6762, 139.6503),
    ('Sydney', -33.8688, 151.2093),
]


def nearest_queryset(lat, lng):
    """Same query as the /nearest/ endpoint"""
    point = Point(lng, lat, srid=4326)
    return City.objects.filter(location__isnull=False).only(
        *PROXIMITY_FIELDS
    ).annotate(
        distance=Distance('location', point)
    ).order_by('distance')[:10]


class Command(BaseCommand):
    help = 'Time the nearest-city query and report whether the spatial index is used'

    def add_arguments(self, parser):
        parser.add_argument(
            '--runs',
            type=int,
            default=20,
            help='Number of timed runs per test point',
        )

    def handle(self, *args, **options):
        runs = options['runs']
        self.stdout.write(f'Cities in table: {City.objects.count()}')
        self.stdout.write(f'Timed runs per point: {runs}\n')

        averages = []
        for name, lat, lng in TEST_POINTS:
            # Warm-up run so connection/setup cost is not counted
            list(nearest_queryset(lat, lng))

            timings = []
            for _ in range(runs):
                start = time.perf_counter()
                results = list(nearest_queryset(lat, lng))
                timings.append((time.perf_counter() - start) * 1000)

            avg_ms = sum(timings) / len(timings)
            averages.append(avg_ms)
            self.stdout.write(
                f'{name:<10} avg {avg_ms:7.2f} ms  '
                f'(min {min(timings):.2f}, max {max(timings):.2f})  '
                f'nearest: {results[0].name if results else "-"}'
            )

        self.stdout.write(self.style.SUCCESS(
            f'\nOverall average: {sum(averages) / len(averages):.2f} ms'
        ))

        name, lat, lng = TEST_POINTS[0]
        plan = nearest_queryset(lat, lng).explain(analyze=True)
        self.stdout.write(f'\nQuery plan ({name}):\n{plan}\n')

        if 'cities_api_city_location' in plan:
            self.stdout.write(self.style.SUCCESS('Spatial (GiST) index used in plan'))
        else:
            self.stdout.write(self.style.WARNING(
                'Spatial (GiST) index NOT used: ORDER BY ST_DistanceSphere() '
                'cannot use the index, and small tables are sequentially scanned'
            ))
