from django.contrib import admin
from .models import ActivityLog, Attendance, ProjectSite


@admin.register(ProjectSite)
class ProjectSiteAdmin(admin.ModelAdmin):
    list_display = ("name", "latitude", "longitude", "radius_meters", "active")
    list_filter = ("active",)
    search_fields = ("name",)


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("user", "project_site", "check_in_time", "check_out_time", "total_hours", "status")
    list_filter = ("status", "project_site", "check_in_time")
    search_fields = ("user__username", "user__first_name", "user__last_name")


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("user", "action", "timestamp", "ip_address")
    list_filter = ("action", "timestamp")
    search_fields = ("user__username", "description", "ip_address")

from .models import GeofenceViolation


@admin.register(GeofenceViolation)
class GeofenceViolationAdmin(admin.ModelAdmin):
    list_display = ("user", "project_site", "detected_at", "distance_meters", "resolution", "management_alerted")
    list_filter = ("resolution", "management_alerted", "project_site", "detected_at")
    search_fields = ("user__username", "user__first_name", "user__last_name")
    readonly_fields = ("user", "attendance", "project_site", "detected_at", "latitude", "longitude",
                       "distance_meters", "management_alerted")
    ordering = ("-detected_at",)
