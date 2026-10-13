from django.contrib.staticfiles import finders
from django.test import TestCase, Client
from django.urls import reverse

class MapViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_map_view_loads(self):
        """Test that the map page loads successfully"""
        response = self.client.get('/map/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Leaflet', response.content.decode())

    def test_static_files_served(self):
        """Test that static files are accessible"""
        # The test runner sets DEBUG=False, so /static/ URLs are not served
        # here; check the files resolve through the staticfiles finders instead.
        self.assertIsNotNone(finders.find('js/map.js'))
        self.assertIsNotNone(finders.find('css/styles.css'))