from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone


class ProjectSite(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    radius_meters = models.PositiveIntegerField(default=100)
    expected_check_in_time = models.TimeField(default="09:00")
    expected_check_out_time = models.TimeField(default="17:00")
    grace_minutes = models.PositiveSmallIntegerField(default=15)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Attendance(models.Model):
    class Status(models.TextChoices):
        CHECKED_IN = "checked_in", "Checked In"
        CHECKED_OUT = "checked_out", "Checked Out"

    class ArrivalStatus(models.TextChoices):
        EARLY = "early", "Early"
        ON_TIME = "on_time", "On Time"
        LATE = "late", "Late"

    class DepartureStatus(models.TextChoices):
        LEFT_EARLY = "left_early", "Left Early"
        ON_TIME = "on_time", "On Time"
        LEFT_LATE = "left_late", "Left Late"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attendance_records")
    project_site = models.ForeignKey(ProjectSite, on_delete=models.PROTECT)
    check_in_time = models.DateTimeField(default=timezone.now)
    check_out_time = models.DateTimeField(blank=True, null=True)
    check_in_latitude = models.DecimalField(max_digits=10, decimal_places=7)
    check_in_longitude = models.DecimalField(max_digits=10, decimal_places=7)
    check_out_latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    check_out_longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    total_hours = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CHECKED_IN)
    arrival_status = models.CharField(max_length=20, choices=ArrivalStatus.choices, blank=True)
    departure_status = models.CharField(max_length=20, choices=DepartureStatus.choices, blank=True)

    class Meta:
        ordering = ("-check_in_time",)

    def close(self, latitude, longitude):
        self.check_out_time = timezone.now()
        self.check_out_latitude = latitude
        self.check_out_longitude = longitude
        duration = self.check_out_time - self.check_in_time
        self.total_hours = Decimal(duration.total_seconds() / 3600).quantize(Decimal("0.01"))
        self.status = self.Status.CHECKED_OUT
        self.save()

    def __str__(self):
        return f"{self.user} - {self.check_in_time:%Y-%m-%d}"


class ActivityLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)

    class Meta:
        ordering = ("-timestamp",)

    def __str__(self):
        return f"{self.action} - {self.timestamp:%Y-%m-%d %H:%M}"


class GeofenceViolation(models.Model):
    """Recorded whenever a checked-in user leaves the site radius."""

    class Resolution(models.TextChoices):
        OPEN = "open", "Open"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        DISMISSED = "dismissed", "Dismissed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="geofence_violations"
    )
    attendance = models.ForeignKey(
        "Attendance", on_delete=models.CASCADE, related_name="violations", null=True, blank=True
    )
    project_site = models.ForeignKey(ProjectSite, on_delete=models.PROTECT)
    detected_at = models.DateTimeField(default=timezone.now)
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    distance_meters = models.DecimalField(max_digits=10, decimal_places=2)
    resolution = models.CharField(max_length=20, choices=Resolution.choices, default=Resolution.OPEN)
    management_alerted = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-detected_at",)

    def __str__(self):
        return f"{self.user} — geofence breach at {self.detected_at:%Y-%m-%d %H:%M}"


class LocationLog(models.Model):
    """
    Records every location-permission ON/OFF event for a user.
    When location is turned back ON, turned_on_at is filled in and
    duration_minutes is calculated automatically.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="location_logs"
    )
    turned_off_at = models.DateTimeField(default=timezone.now)
    turned_on_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Minutes location was off (filled when turned back on)"
    )

    class Meta:
        ordering = ("-turned_off_at",)

    def close(self):
        """Mark location as re-enabled and calculate duration."""
        self.turned_on_at = timezone.now()
        delta = self.turned_on_at - self.turned_off_at
        self.duration_minutes = Decimal(str(round(delta.total_seconds() / 60, 2)))
        self.save(update_fields=["turned_on_at", "duration_minutes"])

    @property
    def duration_display(self):
        """Human-friendly duration string."""
        if self.duration_minutes is None:
            return "Still off"
        mins = int(self.duration_minutes)
        if mins < 1:
            return "< 1 min"
        if mins < 60:
            return f"{mins} min"
        h, m = divmod(mins, 60)
        return f"{h}h {m}m" if m else f"{h}h"

    def __str__(self):
        return f"{self.user} — location off at {self.turned_off_at:%Y-%m-%d %H:%M}"
