import uuid
from io import BytesIO
import urllib.parse
try:
    import qrcode
except ImportError:
    qrcode = None
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models
from django.utils import timezone


def _get_form_setting(key, default=""):
    """Read a Google Form setting from Django settings (loaded from .env)."""
    return getattr(settings, key, default) or default


def build_form_url(event):
    """
    Return the Google Form URL pre-filled with this event's title as the
    Event ID value, so every scan is automatically tagged with the event name.

    The event TITLE is used as the pre-fill value (not the numeric PK) so
    Google Sheets responses are human-readable without needing to look up IDs.

    Config (set in .env):
        GOOGLE_FORM_BASE_URL  — the /viewform URL of your Google Form
        GOOGLE_FORM_EVENT_ID_FIELD  — entry.XXXXXXXXX for the Event ID question
        GOOGLE_FORM_EVENT_NAME_FIELD — entry.YYYYYYYYY for an Event Name question (optional)
    """
    base_url = _get_form_setting("GOOGLE_FORM_BASE_URL")
    if not base_url:
        return ""

    event_id_field   = _get_form_setting("GOOGLE_FORM_EVENT_ID_FIELD")
    event_name_field = _get_form_setting("GOOGLE_FORM_EVENT_NAME_FIELD")

    params = {}
    if event_id_field:
        # Use the numeric PK as the Event ID — matches what Apps Script sends back
        params[event_id_field] = str(event.pk)
    if event_name_field:
        # Use the title for the Event Name field — human-readable in Sheets
        params[event_name_field] = event.title

    if params:
        return base_url + "?" + urllib.parse.urlencode(params)
    return base_url


class Event(models.Model):
    title = models.CharField(max_length=220)
    description = models.TextField()
    location = models.CharField(max_length=220)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    capacity = models.PositiveIntegerField(default=50)
    banner = models.FileField(upload_to="event_banners/", blank=True, null=True)
    qr_code = models.FileField(upload_to="event_qr/", blank=True, null=True)

    # Unique ID embedded in the portal QR code — survives regeneration
    qr_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    # Stored pre-filled Google Form URL for this event (updated on every save)
    google_form_url = models.URLField(
        blank=True,
        help_text="Pre-filled Google Form URL for this event. Auto-updated when the event is saved.",
    )

    # Incremented on every QR scan (and optionally by the Apps Script webhook)
    form_response_count = models.PositiveIntegerField(
        default=0,
        help_text="QR scans / form responses for this event. Auto-updated.",
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
        return self.attendance.count()

    def get_portal_qr_url(self, request=None):
        """
        Absolute URL that the QR code encodes — points to the portal's own
        /events/qr/<uuid>/ handler which increments the counter then redirects
        to the pre-filled Google Form.

        Uses request.build_absolute_uri when available (handles any domain/port),
        otherwise falls back to settings.SITE_BASE_URL from .env.
        """
        path = f"/events/qr/{self.qr_uuid}/"
        if request:
            return request.build_absolute_uri(path)
        base = getattr(settings, "SITE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
        return f"{base}{path}"

    def get_registration_url(self):
        """Pre-filled Google Form URL for this event."""
        return build_form_url(self) or _get_form_setting("GOOGLE_FORM_BASE_URL", "")

    def regenerate_qr(self, request=None):
        """
        (Re)generate the QR code PNG. Called automatically on every save so
        the QR always reflects the current SITE_BASE_URL and event UUID.
        """
        if not qrcode:
            return
        url = self.get_portal_qr_url(request)
        if not url:
            return
        img = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=12,
            border=4,
        )
        img.add_data(url)
        img.make(fit=True)
        qr_img = img.make_image(fill_color="#1e40af", back_color="white")
        buffer = BytesIO()
        qr_img.save(buffer, format="PNG")
        filename = f"event-{self.pk}-{str(self.qr_uuid)[:8]}.png"
        # Delete old file first to avoid stale media files piling up
        if self.qr_code:
            try:
                self.qr_code.delete(save=False)
            except Exception:
                pass
        self.qr_code.save(filename, ContentFile(buffer.getvalue()), save=False)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        # Build the pre-filled form URL AFTER save so self.pk is always a real number
        new_form_url = build_form_url(self)
        if new_form_url:
            self.google_form_url = new_form_url

        needs_regen = is_new or not self.qr_code
        if not needs_regen and new_form_url:
            needs_regen = (self.google_form_url != new_form_url)

        if qrcode and needs_regen:
            self.regenerate_qr()
            Event.objects.filter(pk=self.pk).update(
                qr_code=self.qr_code.name if self.qr_code else "",
                google_form_url=self.google_form_url,
            )


class FormResponse(models.Model):
    """
    Stores individual Google Form submission data received via the Apps Script webhook.
    Each row = one person who registered via Google Form.
    This is the authoritative registration record for all form-based signups.
    """
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="form_responses"
    )
    submitted_at = models.DateTimeField(default=timezone.now)
    # Fields sent by Apps Script — all optional so the webhook never fails
    respondent_name  = models.CharField(max_length=220, blank=True)
    respondent_email = models.CharField(max_length=254, blank=True)
    respondent_phone = models.CharField(max_length=50, blank=True)
    raw_data = models.JSONField(
        default=dict, blank=True,
        help_text="Full form submission payload from Apps Script."
    )

    class Meta:
        ordering = ("-submitted_at",)

    def __str__(self):
        label = self.respondent_name or self.respondent_email or f"Response #{self.pk}"
        return f"{self.event.title} — {label}"


class EventRegistration(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="registrations")
    participant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="event_registrations"
    )
    registration_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("event", "participant")


class EventAttendance(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="attendance")
    participant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="event_attendance"
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("event", "participant")
