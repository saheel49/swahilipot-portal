from django.urls import path
from . import views

app_name = "events"

urlpatterns = [
    path("", views.event_list, name="list"),
    path("new/", views.event_create, name="create"),
    path("<int:pk>/", views.event_detail, name="detail"),
    path("<int:pk>/delete/", views.event_delete, name="delete"),
    path("<int:pk>/register/", views.register, name="register"),
    path("qr/<uuid:qr_uuid>/", views.qr_scan, name="qr_scan"),
    path("<int:pk>/regenerate-qr/", views.regenerate_qr, name="regenerate_qr"),
    path("<int:pk>/report/<str:fmt>/", views.report, name="report"),
    path("<int:pk>/registration-count/", views.registration_count_api, name="registration_count"),
    path("<int:pk>/form-response/", views.form_response_webhook, name="form_response_webhook"),
    path("form-response/", views.form_response_webhook_byid, name="form_response_webhook_byid"),
]
