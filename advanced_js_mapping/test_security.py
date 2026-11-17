import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.gis.geos import Point
from django.test import Client, TestCase
from django.urls import reverse

from .models import AdvancedCity


class CitySecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.city = AdvancedCity.objects.create(
            name="Dublin", country="Ireland", population=592000,
            location=Point(-6.26, 53.35, srid=4326),
        )
        cls.viewer = get_user_model().objects.create_user(username="viewer", password="viewer-pass")
        cls.editor = get_user_model().objects.create_user(username="editor", password="editor-pass")
        cls.editor.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="advanced_js_mapping",
            codename__in=["add_advancedcity", "change_advancedcity"],
        ))

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.get(reverse("advanced_js_mapping:map"))
        self.create = reverse("advanced_js_mapping:city_create")
        self.update = reverse("advanced_js_mapping:city_update", args=[self.city.pk])
        self.attrs = {"name": "Dublin", "country": "Ireland", "population": 600000}
        self.new = {**self.attrs, "latitude": 53.35, "longitude": -6.26}

    def send(self, method, url, data, csrf=True):
        headers = {}
        if csrf:
            headers["HTTP_X_CSRFTOKEN"] = self.client.cookies["csrftoken"].value
        return getattr(self.client, method)(
            url, data=json.dumps(data), content_type="application/json", **headers
        )

    def test_public_read_and_anonymous_write_denial(self):
        self.assertEqual(self.client.get(reverse("advanced_js_mapping:cities_api")).status_code, 200)
        self.assertEqual(self.send("post", self.create, self.new).status_code, 401)
        self.assertEqual(self.send("put", self.update, self.attrs).status_code, 401)
        for route in ("polygon_search", "distance_search"):
            self.assertEqual(self.send("post", reverse(f"advanced_js_mapping:{route}"), {}).status_code, 401)
        self.city.refresh_from_db()
        self.assertEqual(self.city.population, 592000)

    def test_viewer_can_search_but_cannot_write(self):
        self.client.force_login(self.viewer)
        polygon = {"coordinates": [[-7, 53], [-5, 53], [-5, 54], [-7, 54]]}
        self.assertEqual(self.send("post", reverse("advanced_js_mapping:polygon_search"), polygon).status_code, 200)
        self.assertEqual(self.send("post", self.create, self.new).status_code, 403)
        self.assertEqual(self.send("put", self.update, self.attrs).status_code, 403)
        self.city.refresh_from_db()
        self.assertEqual(self.city.population, 592000)

    def test_editor_writes_validated_data(self):
        self.client.force_login(self.editor)
        self.assertEqual(self.send("put", self.update, self.attrs).status_code, 200)
        self.city.refresh_from_db()
        self.assertEqual(self.city.population, 600000)
        self.assertEqual(self.send("post", self.create, self.new).status_code, 201)
        self.assertEqual(self.send("put", self.update, {**self.attrs, "is_active": False}).status_code, 400)
        self.assertEqual(self.send("put", self.update, {**self.attrs, "population": -1}).status_code, 400)
        self.assertEqual(self.send("post", self.create, {**self.new, "latitude": 91}).status_code, 400)
        self.assertEqual(self.send("put", reverse("advanced_js_mapping:city_update", args=[999999]), self.attrs).status_code, 404)

    def test_csrf_and_method_restrictions(self):
        self.client.force_login(self.editor)
        self.assertEqual(self.send("post", self.create, self.new, csrf=False).status_code, 403)
        self.assertEqual(self.send("put", self.update, self.attrs, csrf=False).status_code, 403)
        self.assertEqual(self.send("post", reverse("advanced_js_mapping:polygon_search"), {}, csrf=False).status_code, 403)
        self.assertEqual(self.send("post", reverse("advanced_js_mapping:distance_search"), {}, csrf=False).status_code, 403)
        self.assertEqual(self.send("post", reverse("advanced_js_mapping:cities_api"), {}).status_code, 405)
        self.assertEqual(self.send("put", self.create, self.new).status_code, 405)
        self.assertEqual(self.send("post", self.update, self.attrs).status_code, 405)
        self.assertEqual(self.client.get(self.update).status_code, 405)
        self.assertEqual(self.send("patch", self.update, self.attrs).status_code, 405)
        self.assertEqual(self.send("delete", self.update, self.attrs).status_code, 405)
        self.city.refresh_from_db()
        self.assertEqual(self.city.population, 592000)

    def test_real_login_and_editor_visibility(self):
        map_url = reverse("advanced_js_mapping:map")
        self.assertNotContains(self.client.get(map_url), 'id="city-editor"')
        response = self.client.post(reverse("login"), {
            "username": "editor",
            "password": "editor-pass",
            "csrfmiddlewaretoken": self.client.cookies["csrftoken"].value,
        })
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get(map_url), 'id="city-editor"')
        self.assertEqual(self.send("put", self.update, self.attrs).status_code, 200)

    def test_logout_ends_write_access(self):
        self.client.force_login(self.editor)
        response = self.client.post(reverse("logout"), HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.send("put", self.update, self.attrs).status_code, 401)
