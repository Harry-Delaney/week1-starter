from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.gis.geos import Point
from cities_api.models import City

class CityAPITestCase(APITestCase):
    """Test cases for Cities API"""

    def setUp(self):
        """Create test data"""
        self.dublin = City.objects.create(
            name='Dublin',
            country='Ireland',
            population=1400000,
            location=Point(-6.2603, 53.3498, srid=4326),
            is_capital=True
        )

        self.london = City.objects.create(
            name='London',
            country='United Kingdom',
            population=9000000,
            location=Point(-0.1278, 51.5074, srid=4326),
            is_capital=True
        )

    def test_city_list(self):
        """Test city list endpoint"""
        url = reverse('cities_api:city-list-create')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        self.assertIn('results', response.data)

    def test_city_detail(self):
        """Test city detail endpoint"""
        url = reverse('cities_api:city-detail', kwargs={'pk': self.dublin.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Dublin')
        self.assertEqual(response.data['country'], 'Ireland')

    def test_city_creation(self):
        """Test creating a new city"""
        url = reverse('cities_api:city-list-create')
        data = {
            'name': 'Paris',
            'country': 'France',
            'population': 11000000,
            'latitude': 48.8566,
            'longitude': 2.3522,
            'is_capital': True
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(City.objects.count(), 3)

    def test_city_filtering(self):
        """Test city filtering"""
        url = reverse('cities_api:city-list-create')
        response = self.client.get(url, {'country': 'Ireland'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['name'], 'Dublin')

    def test_geojson_format(self):
        """Test GeoJSON output"""
        url = reverse('cities_api:city-geojson')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['type'], 'FeatureCollection')
        self.assertIn('features', response.data)

    def test_within_radius_query(self):
        """Test spatial within radius query"""
        url = reverse('cities_api:cities-within-radius')
        data = {
            'latitude': 53.0,
            'longitude': -6.0,
            'radius_km': 100
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('cities', response.data)
        self.assertGreater(response.data['count'], 0)

    def test_statistics_endpoint(self):
        """Test statistics endpoint"""
        url = reverse('cities_api:city-statistics')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_cities'], 2)
        self.assertEqual(response.data['capitals_count'], 2)

class ProximitySearchAPITestCase(APITestCase):
    """Test cases for the nearest-city and radius search endpoints"""

    def setUp(self):
        """Create cities at known distances from Dublin"""
        cities = [
            ('Dublin', 'Ireland', 1400000, -6.2603, 53.3498),
            ('Belfast', 'United Kingdom', 345000, -5.9301, 54.5973),
            ('Cork', 'Ireland', 210000, -8.4756, 51.8985),
            ('Galway', 'Ireland', 80000, -9.0568, 53.2707),
            ('London', 'United Kingdom', 9000000, -0.1278, 51.5074),
            ('Paris', 'France', 2100000, 2.3522, 48.8566),
            ('Berlin', 'Germany', 3600000, 13.4050, 52.5200),
            ('Madrid', 'Spain', 3300000, -3.7038, 40.4168),
            ('Rome', 'Italy', 2800000, 12.4964, 41.9028),
            ('Oslo', 'Norway', 700000, 10.7522, 59.9139),
            ('Athens', 'Greece', 660000, 23.7275, 37.9838),
            ('Tokyo', 'Japan', 14000000, 139.6503, 35.6762),
        ]
        for name, country, population, lng, lat in cities:
            City.objects.create(
                name=name,
                country=country,
                population=population,
                location=Point(lng, lat, srid=4326),
            )
        self.nearest_url = reverse('cities_api:cities-nearest')
        self.radius_url = reverse('cities_api:cities-radius')
        self.dublin = {'lat': 53.3498, 'lng': -6.2603}

    # Nearest-city endpoint

    def test_nearest_returns_ten_ordered_results(self):
        """Valid request returns the ten nearest cities in distance order"""
        response = self.client.post(self.nearest_url, self.dublin, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_found'], 10)
        results = response.data['nearest_cities']
        self.assertEqual(len(results), 10)

        self.assertEqual(results[0]['name'], 'Dublin')
        self.assertEqual(results[0]['distance_km'], 0.0)
        self.assertEqual(
            [city['name'] for city in results[:4]],
            ['Dublin', 'Belfast', 'Galway', 'Cork'],
        )
        self.assertEqual([city['rank'] for city in results], list(range(1, 11)))

        distances = [city['distance_km'] for city in results]
        self.assertEqual(distances, sorted(distances))
        # The two furthest cities are excluded by the limit of ten
        self.assertNotIn('Tokyo', [city['name'] for city in results])
        self.assertNotIn('Athens', [city['name'] for city in results])

    def test_nearest_response_shape(self):
        """Each result contains the expected fields"""
        response = self.client.post(self.nearest_url, self.dublin, format='json')

        self.assertEqual(response.data['search_point'], self.dublin)
        city = response.data['nearest_cities'][1]
        self.assertEqual(
            set(city),
            {'id', 'name', 'country', 'population', 'coordinates', 'distance_km', 'rank'},
        )
        self.assertEqual(city['name'], 'Belfast')
        self.assertAlmostEqual(city['coordinates']['lat'], 54.5973)
        self.assertAlmostEqual(city['coordinates']['lng'], -5.9301)
        self.assertAlmostEqual(city['distance_km'], 141, delta=5)

    def test_nearest_accepts_numeric_strings(self):
        """Numeric strings are converted to floats"""
        response = self.client.post(
            self.nearest_url, {'lat': '53.3498', 'lng': '-6.2603'}, format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['nearest_cities'][0]['name'], 'Dublin')

    # Radius endpoint

    def test_radius_returns_cities_within_radius(self):
        """Valid radius request returns only cities inside the radius, ordered"""
        data = dict(self.dublin, radius_km=300)
        response = self.client.post(self.radius_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['radius_km'], 300)
        names = [city['name'] for city in response.data['cities']]
        self.assertEqual(names, ['Dublin', 'Belfast', 'Galway', 'Cork'])
        self.assertEqual(response.data['total_found'], 4)
        for city in response.data['cities']:
            self.assertLessEqual(city['distance_km'], 300)

    def test_radius_defaults_to_100_km(self):
        """radius_km is optional and defaults to 100"""
        response = self.client.post(self.radius_url, self.dublin, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['radius_km'], 100)
        self.assertEqual([city['name'] for city in response.data['cities']], ['Dublin'])

    def test_radius_with_no_matches(self):
        """A radius with no cities returns an empty list"""
        data = {'lat': 0, 'lng': 0, 'radius_km': 10}
        response = self.client.post(self.radius_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_found'], 0)
        self.assertEqual(response.data['cities'], [])

    # Invalid input

    def test_invalid_coordinate_ranges(self):
        """Out-of-range latitude or longitude is rejected on both endpoints"""
        invalid_points = [
            {'lat': 91, 'lng': 0},
            {'lat': -90.1, 'lng': 0},
            {'lat': 0, 'lng': 180.5},
            {'lat': 0, 'lng': -181},
        ]
        for url in (self.nearest_url, self.radius_url):
            for data in invalid_points:
                with self.subTest(url=url, data=data):
                    response = self.client.post(url, data, format='json')
                    self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                    self.assertIn('Latitude must be between', response.data['error'])

    def test_boundary_coordinates_are_valid(self):
        """Coordinates exactly on the allowed limits are accepted"""
        for data in ({'lat': 90, 'lng': 180}, {'lat': -90, 'lng': -180}):
            with self.subTest(data=data):
                response = self.client.post(self.nearest_url, data, format='json')
                self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_missing_coordinates(self):
        """Missing lat or lng is rejected on both endpoints"""
        for url in (self.nearest_url, self.radius_url):
            for data in ({}, {'lat': 53.3}, {'lng': -6.2}):
                with self.subTest(url=url, data=data):
                    response = self.client.post(url, data, format='json')
                    self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                    self.assertEqual(
                        response.data['error'], 'Provide numeric lat and lng values.'
                    )

    def test_non_numeric_coordinates(self):
        """Non-numeric lat or lng is rejected on both endpoints"""
        invalid = [
            {'lat': 'abc', 'lng': -6.2},
            {'lat': 53.3, 'lng': 'west'},
            {'lat': None, 'lng': -6.2},
            {'lat': [53.3], 'lng': -6.2},
        ]
        for url in (self.nearest_url, self.radius_url):
            for data in invalid:
                with self.subTest(url=url, data=data):
                    response = self.client.post(url, data, format='json')
                    self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                    self.assertEqual(
                        response.data['error'], 'Provide numeric lat and lng values.'
                    )

    def test_invalid_radius(self):
        """Zero, negative, too large, or non-numeric radius is rejected"""
        for radius in (0, -5, 20000.1, 50000):
            with self.subTest(radius=radius):
                data = dict(self.dublin, radius_km=radius)
                response = self.client.post(self.radius_url, data, format='json')
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn('greater than 0', response.data['error'])

        for radius in ('far', None):
            with self.subTest(radius=radius):
                data = dict(self.dublin, radius_km=radius)
                response = self.client.post(self.radius_url, data, format='json')
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(response.data['error'], 'radius_km must be a number.')

    def test_get_not_allowed(self):
        """Endpoints only accept POST"""
        for url in (self.nearest_url, self.radius_url):
            with self.subTest(url=url):
                response = self.client.get(url, self.dublin)
                self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
