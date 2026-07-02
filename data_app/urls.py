from django.urls import path

from .views import chat, data_list, data_stats, data_summary, health_check, upload_excel

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("data/", data_list, name="data-list"),
    path("summary/", data_summary, name="data-summary"),
    path("stats/", data_stats, name="data-stats"),
    path("chat/", chat, name="chat"),
    path("upload/", upload_excel, name="upload-excel"),
]
