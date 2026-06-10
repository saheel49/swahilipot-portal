from django.contrib import admin
from django.contrib import messages
from .models import Event, EventAttendance, EventRegistration, FormResponse


def regenerate_qr_codes(modeladmin, request, queryset):
    """Admin action: regenerate QR codes for selected events."""
    count = 0
    for event in queryset:
        event.google_form_url = ""
        event.save()
        count += 1
    modeladmin.message_user(
        request,
        f"QR codes regenerated for {count} event(s). They now point to the real Google Form.",
        messages.SUCCESS,
    )

regenerate_qr_codes.short_description = "Regenerate QR codes (point to Google Form)"


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display  = ("title", "location", "start_date", "form_response_count", "capacity")
    actions       = [regenerate_qr_codes]
    readonly_fields = ("qr_code", "form_response_count")


@admin.register(FormResponse)
class FormResponseAdmin(admin.ModelAdmin):
    list_display  = ("event", "respondent_name", "respondent_email", "respondent_phone", "submitted_at")
    list_filter   = ("event",)
    search_fields = ("respondent_name", "respondent_email", "respondent_phone")
    readonly_fields = ("submitted_at", "raw_data")
    ordering      = ("-submitted_at",)


admin.site.register(EventRegistration)
admin.site.register(EventAttendance)
