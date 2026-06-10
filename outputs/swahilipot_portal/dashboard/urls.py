from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("live-stats/", views.live_stats, name="live_stats"),
    path("event-scan-debug/", views.event_scan_debug, name="event_scan_debug"),
    path("reminders/", views.reminders, name="reminders"),
    path("reports/", views.reports, name="reports"),
    path("reports/<str:kind>/<str:fmt>/", views.report_download, name="report_download"),
]
