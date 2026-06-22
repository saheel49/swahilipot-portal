from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("audit-log/", views.audit_log, name="audit_log"),
    path("audit-log/export/", views.audit_log_export, name="audit_log_export"),
]
