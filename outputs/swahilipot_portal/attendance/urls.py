from django.urls import path
from . import views

app_name = "attendance"

urlpatterns = [
    path("", views.attendance_home, name="home"),
    path("sites/", views.site_list, name="sites"),
    path("sites/new/", views.site_create, name="site_create"),
    path("sites/<int:pk>/edit/", views.site_edit, name="site_edit"),
    path("check-in/", views.check_in, name="check_in"),
    path("check-out/", views.check_out, name="check_out"),
    path("geofence-ping/", views.geofence_ping, name="geofence_ping"),
    path("location-status/", views.location_status, name="location_status"),
    path("violations/", views.geofence_violations, name="geofence_violations"),
    path("violations/report/<str:fmt>/", views.geofence_violations_report, name="geofence_violations_report"),
    path("violations/<int:pk>/acknowledge/", views.acknowledge_violation, name="acknowledge_violation"),
    # Filtered views for dashboard metric cards
    path("today/", views.attendance_today, name="today"),
    path("currently-in/", views.attendance_currently_in, name="currently_in"),
    path("currently-out/", views.attendance_currently_out, name="currently_out"),
    path("late-arrivals/", views.attendance_late_arrivals, name="late_arrivals"),
    # Location timeout — per-user self-service view
    path("location-timeout/", views.my_location_timeout, name="my_location_timeout"),
    path("location-timeout/report/<str:fmt>/", views.location_timeout_report, name="location_timeout_report"),
    # Per-user location on/off log (admin/manager)
    path("location-log/<int:user_pk>/", views.user_location_log, name="location_log"),
    path("location-activity/", views.all_location_activity, name="location_activity"),
    path("location-off-status/", views.location_off_status_api, name="location_off_status"),
    # Missed checkout — staff auto-closed sessions
    path("missed-checkout/", views.missed_checkout, name="missed_checkout"),
    path("missed-checkout/report/<str:fmt>/", views.missed_checkout_report, name="missed_checkout_report"),
]
