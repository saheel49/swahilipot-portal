from django.contrib.auth.models import AbstractUser
from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN           = "admin",            "Admin"
        STAFF           = "staff",            "Staff"
        INTERN          = "intern",           "Intern"
        PROGRAM_MANAGER = "program_manager",  "Program Manager"
        DEPARTMENT_HEAD = "department_head",  "Department Head"

    email         = models.EmailField(unique=True)
    phone_number  = models.CharField(max_length=30, blank=True)
    profile_photo = models.FileField(upload_to="profiles/", blank=True, null=True)
    department    = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="users"
    )
    role = models.CharField(max_length=30, choices=Role.choices, default=Role.STAFF)

    # Tracks the most recently active session key for single-login enforcement.
    # Updated by a post_login signal in accounts/apps.py.
    last_session_key = models.CharField(max_length=40, blank=True)

    # ── helpers ───────────────────────────────────────────────────────────
    def is_portal_admin(self):
        return self.is_superuser or self.role == self.Role.ADMIN

    def is_manager(self):
        return self.is_portal_admin() or self.role in {
            self.Role.PROGRAM_MANAGER, self.Role.DEPARTMENT_HEAD
        }

    # ── capability gates ──────────────────────────────────────────────────
    def can_manage_tasks(self):
        """Admin, Program Manager, Department Head can create/assign tasks."""
        return self.is_portal_admin() or self.role in {
            self.Role.PROGRAM_MANAGER, self.Role.DEPARTMENT_HEAD
        }

    def can_manage_events(self):
        """Admin and Program Manager create/manage events."""
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def can_monitor_attendance(self):
        """Admin, PM and Dept Head can see org-level attendance stats."""
        return self.is_portal_admin() or self.role in {
            self.Role.PROGRAM_MANAGER, self.Role.DEPARTMENT_HEAD
        }

    def can_manage_communication(self):
        """Admin, PM and Dept Head can publish announcements & create channels."""
        return self.is_portal_admin() or self.role in {
            self.Role.PROGRAM_MANAGER, self.Role.DEPARTMENT_HEAD
        }

    def can_view_reports(self):
        """Only Admin and Program Manager download full reports."""
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def can_review_suggestions(self):
        """Admin and Program Manager can review/respond to suggestions."""
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def save(self, *args, **kwargs):
        if self.role == self.Role.ADMIN:
            self.is_staff = True
            self.is_superuser = True
        super().save(*args, **kwargs)

    def __str__(self):
        return self.get_full_name() or self.username
