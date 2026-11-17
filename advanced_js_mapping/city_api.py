import json

from django.contrib.gis.geos import Point
from django.http import HttpResponseNotAllowed, JsonResponse
from django.views.decorators.http import require_http_methods

from .forms import CityAttributesForm, CityCreateForm
from .models import AdvancedCity


@require_http_methods(["POST", "PUT"])
def city_write(request, city_id=None):
    # Each URL has exactly one supported operation.
    if city_id is None and request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if city_id is not None and request.method != "PUT":
        return HttpResponseNotAllowed(["PUT"])

    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required."}, status=401)
    permission = (
        "advanced_js_mapping.add_advancedcity" if city_id is None
        else "advanced_js_mapping.change_advancedcity"
    )
    if not request.user.has_perm(permission):
        return JsonResponse({"error": "You do not have permission for this action."}, status=403)

    city = None
    if city_id is not None:
        city = AdvancedCity.objects.filter(pk=city_id, is_active=True).first()
        if city is None:
            return JsonResponse({"error": "City not found."}, status=404)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON."}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({"error": "Expected a JSON object."}, status=400)

    form = (CityCreateForm if city_id is None else CityAttributesForm)(data)
    if set(data) != set(form.fields):
        return JsonResponse({"error": "Provide exactly the required fields."}, status=400)
    if not form.is_valid():
        return JsonResponse({"error": "Invalid city data.", "fields": form.errors.get_json_data()}, status=400)

    values = form.cleaned_data
    if city_id is None:
        city = AdvancedCity(
            location=Point(values["longitude"], values["latitude"], srid=4326)
        )
    city.name = values["name"]
    city.country = values["country"]
    city.population = values["population"]
    city.save()
    return JsonResponse({
        "id": city.pk,
        "name": city.name,
        "country": city.country,
        "population": city.population,
    }, status=201 if city_id is None else 200)
