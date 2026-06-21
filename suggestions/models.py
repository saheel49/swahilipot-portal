from django.conf import settings
from django.db import models


class Suggestion(models.Model):
    class Category(models.TextChoices):
        IMPROVEMENT = "improvement", "Improvement"
        COMPLAINT = "complaint", "Complaint"
        IDEA = "idea", "Idea"
        FEEDBACK = "feedback", "Feedback"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        REVIEWED = "reviewed", "Reviewed"
        RESOLVED = "resolved", "Resolved"

    title = models.CharField(max_length=200)
    message = models.TextField()
    category = models.CharField(max_length=30, choices=Category.choices)
    anonymous = models.BooleanField(default=False)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    response = models.TextField(blank=True)

    class Meta:
        ordering = ("-submitted_at",)

    def display_user(self):
        return "Anonymous" if self.anonymous else (self.submitted_by or "Unknown")

    def __str__(self):
        return self.title

