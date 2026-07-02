from django.urls import path

from .views import data_list, data_stats, data_summary, health_check

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("data/", data_list, name="data-list"),
    path("summary/", data_summary, name="data-summary"),
    path("stats/", data_stats, name="data-stats"),
]
