from django.contrib import admin
from django.contrib import messages
from .models import Event, EventAttendance, EventRegistration, EventCheckIn, FormResponse


def regenerate_form_urls(modeladmin, request, queryset):
    """Admin action: refresh pre-filled Google Form URLs for selected events."""
    from .models import build_form_url
    count = 0
    for event in queryset:
        new_url = build_form_url(event)
        if new_url:
            Event.objects.filter(pk=event.pk).update(google_form_url=new_url)
            count += 1
    modeladmin.message_user(request, f"Form URLs refreshed for {count} event(s).", messages.SUCCESS)

regenerate_form_urls.short_description = "Refresh pre-filled Google Form URLs"


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display  = ("title", "location", "start_date", "form_response_count", "capacity")
    actions       = [regenerate_form_urls]
    readonly_fields = ("form_response_count",)


@admin.register(FormResponse)
class FormResponseAdmin(admin.ModelAdmin):
    list_display  = ("event", "respondent_name", "respondent_email", "respondent_phone", "submitted_at")
    list_filter   = ("event",)
    search_fields = ("respondent_name", "respondent_email", "respondent_phone")
    readonly_fields = ("submitted_at", "raw_data")
    ordering      = ("-submitted_at",)


@admin.register(EventCheckIn)
class EventCheckInAdmin(admin.ModelAdmin):
    list_display  = ("event", "participant", "checked_in_at", "distance_meters")
    list_filter   = ("event",)
    search_fields = ("participant__username", "participant__first_name", "participant__last_name")
    readonly_fields = ("checked_in_at", "latitude", "longitude", "distance_meters")
    ordering      = ("-checked_in_at",)


admin.site.register(EventRegistration)
admin.site.register(EventAttendance)
