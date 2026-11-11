import requests
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render

from .models import City

XWEATHERMAP_URL = "https://data.api.xweather.com/conditions/closest"
XWEATHER_FORECAST_URL = "https://data.api.xweather.com/forecasts/{location}"

CACHE_SECONDS = 600  # Enhancement 2: cache weather data for 10 minutes
FORECAST_DAYS = 3    # Enhancement 1: 3-day forecast


class WeatherServiceError(Exception):
    """A failure with a fixed message that is safe to send to the browser."""

    def __init__(self, message, status):
        super().__init__(message)
        self.message = message
        self.status = status


def map_view(request):
    """Render the main map page"""
    return render(request, 'weathermap/map.html')


def get_cities_json(request):
    """Return all cities as JSON"""
    cities = City.objects.all().values('id', 'name', 'country', 'latitude', 'longitude')
    return JsonResponse(list(cities), safe=False)


def fetch_periods(url, extra_params):
    """Call an XWeather endpoint and return its list of periods.

    The request is made server-side, so the credentials stay secret.
    get_weather and get_forecast share this function so that both use the
    same error handling. Every failure becomes a WeatherServiceError with a
    fixed message.
    """
    # Use the exact variable names defined in settings.py
    client_id = getattr(settings, 'XWEATHER_CLIENT_ID', None)
    client_secret = getattr(settings, 'XWEATHER_CLIENT_SECRET', None)

    if not client_id or not client_secret:
        raise WeatherServiceError(
            'XWeather API credentials (XWEATHER_CLIENT_ID and XWEATHER_CLIENT_SECRET) are not configured',
            503,
        )

    params = {
        'client_id': client_id,
        'client_secret': client_secret,
        'units': 'metric',  # Metric units for Celsius, m/s, etc.
        **extra_params,
    }

    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        weather_data = response.json()

        # XWeather returns data nested inside response -> periods
        periods = weather_data['response'][0]['periods']
        if not periods:
            raise IndexError('XWeather returned no periods')
        return periods

    except requests.exceptions.HTTPError as e:
        # Never return str(e): it contains the request URL, including sensitive credentials
        status = e.response.status_code
        if status == 401:
            message = 'XWeather rejected the API credentials'
        else:
            message = f'XWeather returned HTTP {status}'
        raise WeatherServiceError(message, 502)
    except requests.exceptions.RequestException:
        raise WeatherServiceError('Could not get a response from XWeather', 502)
    except (KeyError, IndexError, TypeError):
        raise WeatherServiceError('Unexpected response format from XWeather', 502)


def get_weather(request, city_id):
    """Fetch current weather for a city from XWeather API (server-side, so credentials stay secret)"""
    try:
        city = City.objects.get(id=city_id)
    except City.DoesNotExist:
        return JsonResponse({'error': 'City not found'}, status=404)

    # Enhancement 2: answer from the cache when we fetched this city recently
    cache_key = f'weather_{city_id}'
    cached_data = cache.get(cache_key)
    if cached_data:
        return JsonResponse(cached_data)

    try:
        periods = fetch_periods(XWEATHERMAP_URL, {'p': f"{city.latitude},{city.longitude}"})
    except WeatherServiceError as e:
        return JsonResponse({'error': e.message}, status=e.status)

    period = periods[0]
    result = {
        'city': city.name,
        'country': city.country,
        'temperature': period.get('tempC'),
        'feels_like': period.get('feelslikeC'),
        'humidity': period.get('humidity'),
        'pressure': period.get('pressureMB'),
        'wind_speed': period.get('windSpeedMPS'),
        'description': period.get('weather'),
        'icon': period.get('icon'),
    }

    cache.set(cache_key, result, CACHE_SECONDS)  # Only successful results are cached
    return JsonResponse(result)


def get_forecast(request, city_id):
    """Enhancement 1: fetch a 3-day forecast (one entry per day) for a city from XWeather"""
    try:
        city = City.objects.get(id=city_id)
    except City.DoesNotExist:
        return JsonResponse({'error': 'City not found'}, status=404)

    cache_key = f'forecast_{city_id}'
    cached_data = cache.get(cache_key)
    if cached_data:
        return JsonResponse(cached_data)

    url = XWEATHER_FORECAST_URL.format(location=f"{city.latitude},{city.longitude}")
    try:
        # filter=day asks XWeather for one period per day, so we do not have
        # to pick one entry per day out of a list of 3-hour entries
        periods = fetch_periods(url, {'filter': 'day', 'limit': FORECAST_DAYS})
    except WeatherServiceError as e:
        return JsonResponse({'error': e.message}, status=e.status)

    result = {
        'city': city.name,
        'country': city.country,
        'days': [
            {
                'date': (period.get('dateTimeISO') or '')[:10],
                'max_temp': period.get('maxTempC'),
                'min_temp': period.get('minTempC'),
                'description': period.get('weather'),
                'icon': period.get('icon'),
            }
            for period in periods[:FORECAST_DAYS]
        ],
    }

    cache.set(cache_key, result, CACHE_SECONDS)
    return JsonResponse(result)
