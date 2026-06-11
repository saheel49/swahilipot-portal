from django.urls import path
from . import views

app_name = "events"

urlpatterns = [
    path("", views.event_list, name="list"),
    path("new/", views.event_create, name="create"),
    path("<int:pk>/", views.event_detail, name="detail"),
    path("<int:pk>/edit/", views.event_edit, name="edit"),
    path("<int:pk>/delete/", views.event_delete, name="delete"),

    # Registration — portal form
    path("<int:pk>/register/", views.register, name="register"),

    # Geofence check-in (POST only, AJAX)
    path("<int:pk>/checkin/", views.event_checkin, name="checkin"),

    # Live count polling
    path("<int:pk>/registration-count/", views.registration_count_api, name="registration_count"),

    # Per-event reports
    path("<int:pk>/report/<str:fmt>/", views.report, name="report"),

    # No-shows — registered but didn't attend
    path("no-shows/", views.all_no_shows, name="all_no_shows"),
    path("<int:pk>/no-shows/", views.no_shows, name="no_shows"),
    path("<int:pk>/no-shows/report/<str:fmt>/", views.no_shows_report, name="no_shows_report"),

    # Not registered — portal users who never signed up
    path("<int:pk>/not-registered/", views.not_registered, name="not_registered"),
    path("<int:pk>/not-registered/report/<str:fmt>/", views.not_registered_report, name="not_registered_report"),

    # Apps Script webhook (optional enrichment)
    path("<int:pk>/form-response/", views.form_response_webhook, name="form_response_webhook"),
    path("form-response/", views.form_response_webhook_byid, name="form_response_webhook_byid"),
]
