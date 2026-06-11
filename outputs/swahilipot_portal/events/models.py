import uuid
import urllib.parse
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone


def _get_form_setting(key, default=""):
    """Read a Google Form setting from Django settings (loaded from .env)."""
    return getattr(settings, key, default) or default


def build_form_url(event):
    """
    Return the Google Form URL pre-filled with event ID and title so every
    registration is automatically tagged with the event.

    Config (set in .env):
        GOOGLE_FORM_BASE_URL          — the /viewform URL of your Google Form
        GOOGLE_FORM_EVENT_ID_FIELD    — entry.XXXXXXXXX for the Event ID question
        GOOGLE_FORM_EVENT_NAME_FIELD  — entry.YYYYYYYYY for an Event Name question (optional)
    """
    base_url = _get_form_setting("GOOGLE_FORM_BASE_URL")
    if not base_url:
        return ""

    event_id_field   = _get_form_setting("GOOGLE_FORM_EVENT_ID_FIELD")
    event_name_field = _get_form_setting("GOOGLE_FORM_EVENT_NAME_FIELD")

    # Strip any existing query string from the base URL so we always build cleanly
    clean_base = base_url.split("?")[0]

    params = {"usp": "pp_url"}  # Required for Google to honour pre-fill values
    if event_id_field:
        params[event_id_field] = str(event.pk)
    if event_name_field:
        params[event_name_field] = event.title

    return clean_base + "?" + urllib.parse.urlencode(params)


class Event(models.Model):
    title = models.CharField(max_length=220)
    description = models.TextField()
    location = models.CharField(max_length=220)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    capacity = models.PositiveIntegerField(default=50)
    banner = models.FileField(upload_to="event_banners/", blank=True, null=True)

    # Venue GPS coordinates — set when creating the event so geofence check-in works.
    venue_latitude  = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True,
        help_text="Venue GPS latitude — required for geofence check-in enforcement.",
    )
    venue_longitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True,
        help_text="Venue GPS longitude — required for geofence check-in enforcement.",
    )
    venue_radius_meters = models.PositiveIntegerField(
        default=200,
        help_text="Allowed radius from venue centre for geofence check-in (metres).",
    )

    # Legacy QR fields — kept so existing DB data / migrations are not broken.
    qr_code  = models.FileField(upload_to="event_qr/", blank=True, null=True)
    qr_uuid  = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    # Stored pre-filled Google Form URL (updated on every save if configured)
    google_form_url = models.URLField(
        blank=True,
        help_text="Pre-filled Google Form URL for this event. Auto-updated on save.",
    )

    # Incremented on every portal registration (and optionally by Apps Script webhook)
    form_response_count = models.PositiveIntegerField(
        default=0,
        help_text="Total registrations for this event. Auto-updated.",
    )

    class Meta:
        ordering = ("start_date",)

    def __str__(self):
        return self.title

    @property
    def is_past(self):
        return timezone.now() > self.end_date

    @property
    def is_upcoming(self):
        return timezone.now() <= self.end_date

    @property
    def is_full(self):
        return self.form_response_count >= self.capacity

    @property
    def registration_open(self):
        return self.is_upcoming and not self.is_full

    def registration_count(self):
        return self.registrations.count()

    def attendance_count(self):
        """Count of people who physically checked in via geofence."""
        return self.event_checkins.count()

    def get_registration_url(self):
        """Pre-filled Google Form URL for this event (used by Apps Script enrichment)."""
        return build_form_url(self) or _get_form_setting("GOOGLE_FORM_BASE_URL", "")

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        # Rebuild pre-filled URL after save (so self.pk is a real number)
        new_url = build_form_url(self)
        if new_url and new_url != self.google_form_url:
            self.google_form_url = new_url
            Event.objects.filter(pk=self.pk).update(google_form_url=self.google_form_url)


class FormResponse(models.Model):
    """
    Stores individual registration data — one row per registrant.
    Created when a user submits the portal registration form, or when
    the Google Apps Script webhook fires after a Google Form submission.
    """
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="form_responses"
    )
    submitted_at = models.DateTimeField(default=timezone.now)
    respondent_name  = models.CharField(max_length=220, blank=True)
    respondent_email = models.CharField(max_length=254, blank=True)
    respondent_phone = models.CharField(max_length=50, blank=True)
    raw_data = models.JSONField(
        default=dict, blank=True,
        help_text="Full submission payload."
    )

    class Meta:
        ordering = ("-submitted_at",)

    def __str__(self):
        label = self.respondent_name or self.respondent_email or f"Response #{self.pk}"
        return f"{self.event.title} — {label}"


class EventRegistration(models.Model):
    """Portal-user registration record (one per user per event, permanent)."""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="registrations")
    participant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="event_registrations"
    )
    registration_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("event", "participant")


class EventAttendance(models.Model):
    """Legacy model — kept for backward-compat with existing data."""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="attendance")
    participant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="event_attendance"
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("event", "participant")


class EventCheckIn(models.Model):
    """
    Records a portal user physically checking in to an event via geofence.
    Created when the user is at the event location and taps 'Check In'.
    This is the attendance record — separate from registration.
    """
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="event_checkins"
    )
    participant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="event_checkins"
    )
    checked_in_at   = models.DateTimeField(default=timezone.now)
    latitude        = models.DecimalField(max_digits=10, decimal_places=7)
    longitude       = models.DecimalField(max_digits=10, decimal_places=7)
    distance_meters = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))

    class Meta:
        unique_together = ("event", "participant")
        ordering = ("-checked_in_at",)

    def __str__(self):
        return f"{self.participant} → {self.event.title} @ {self.checked_in_at:%Y-%m-%d %H:%M}"
