from django.conf import settings
from django.db import models
from django.utils import timezone


class AuditLog(models.Model):
    """
    Comprehensive audit trail for every significant action in the portal.

    Captures: who did it, what they did, which object was affected,
    the HTTP method, URL path, IP address, and timestamp.

    Categories map to different sections of the portal so the admin
    can filter by area (attendance, tasks, users, communication, etc.).
    """

    class Category(models.TextChoices):
        AUTH        = "auth",         "Authentication"
        ATTENDANCE  = "attendance",   "Attendance"
        TASKS       = "tasks",        "Tasks"
        USERS       = "users",        "Users & Accounts"
        DEPARTMENTS = "departments",  "Departments"
        EVENTS      = "events",       "Events"
        COMMUNICATION = "communication", "Communication"
        SUGGESTIONS = "suggestions",  "Suggestions"
        REPORTS     = "reports",      "Reports"
        SYSTEM      = "system",       "System"
        OTHER       = "other",        "Other"

    class Severity(models.TextChoices):
        INFO     = "info",    "Info"
        WARNING  = "warning", "Warning"
        CRITICAL = "critical","Critical"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="audit_logs",
    )
    # Human-readable username snapshot — preserved even if user is deleted
    username_snapshot = models.CharField(max_length=150, blank=True)

    action      = models.CharField(max_length=120)          # e.g. "check_in", "task_created"
    description = models.TextField(blank=True)              # full human-readable detail
    category    = models.CharField(max_length=30, choices=Category.choices, default=Category.OTHER)
    severity    = models.CharField(max_length=10, choices=Severity.choices, default=Severity.INFO)

    # Request metadata
    method      = models.CharField(max_length=10, blank=True)   # GET / POST / etc.
    path        = models.CharField(max_length=500, blank=True)  # URL path
    ip_address  = models.GenericIPAddressField(blank=True, null=True)

    # Optional: which object was affected
    object_type = models.CharField(max_length=80, blank=True)   # e.g. "Task", "User"
    object_id   = models.CharField(max_length=40, blank=True)   # pk of that object
    object_repr = models.CharField(max_length=200, blank=True)  # __str__ of object

    timestamp   = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ("-timestamp",)
        indexes = [
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["category", "-timestamp"]),
            models.Index(fields=["action", "-timestamp"]),
        ]

    def __str__(self):
        who = self.username_snapshot or "anonymous"
        return f"[{self.category}] {who} — {self.action} @ {self.timestamp:%Y-%m-%d %H:%M}"

    def save(self, *args, **kwargs):
        if self.user and not self.username_snapshot:
            self.username_snapshot = self.user.get_full_name() or self.user.username
        super().save(*args, **kwargs)
