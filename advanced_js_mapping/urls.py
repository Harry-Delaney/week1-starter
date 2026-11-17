from django.urls import path
from . import views
from .city_api import city_write

app_name = 'advanced_js_mapping'

urlpatterns = [
    # Main application views
    path('', views.index_view, name='index'),
    path('map/', views.map_view, name='map'),
    path('analytics/', views.analytics_view, name='analytics'),

    # API endpoints
    path('api/polygon-search/', views.polygon_search, name='polygon_search'),
    path('api/cities/', views.cities_api, name='cities_api'),
    path('api/distance-search/', views.distance_search, name='distance_search'),

    # Permission-controlled city writes (Lab 10)
    path('api/cities/create/', city_write, name='city_create'),
    path('api/cities/<int:city_id>/', city_write, name='city_update'),
]
