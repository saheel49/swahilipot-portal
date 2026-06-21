from django.conf import settings
from django.db import models
from accounts.models import Department


class Announcement(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    attachment = models.FileField(upload_to="announcements/", blank=True, null=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.title


class DepartmentChannel(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="channels")
    name = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.department}: {self.name}"


class ChannelMessage(models.Model):
    channel = models.ForeignKey(DepartmentChannel, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    attachment = models.FileField(upload_to="channel_messages/", blank=True, null=True)

    class Meta:
        ordering = ("timestamp",)


class DirectMessage(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages")
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_messages")
    message = models.TextField()
    attachment = models.FileField(upload_to="direct_messages/", blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    read_status = models.BooleanField(default=False)

    class Meta:
        ordering = ("-timestamp",)


class Notification(models.Model):
    class Priority(models.TextChoices):
        LOW      = "low",      "Low"
        MEDIUM   = "medium",   "Medium"
        HIGH     = "high",     "High"
        CRITICAL = "critical", "Critical"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=160)
    message = models.TextField()
    read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.LOW,
    )
    link = models.CharField(
        max_length=500,
        blank=True,
        help_text="Optional URL this notification links to. If set, clicking the notification navigates there.",
    )

    class Meta:
        ordering = ("-timestamp",)

    def __str__(self):
        return self.title

