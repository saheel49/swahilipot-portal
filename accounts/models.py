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
        """True for Admin and Program Manager only (not Dept Head)."""
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def is_dept_head(self):
        """True only for Department Head role."""
        return self.role == self.Role.DEPARTMENT_HEAD

    # ── capability gates ──────────────────────────────────────────────────

    def can_manage_tasks(self):
        """
        Admin and PM can create/assign tasks to anyone.
        Dept Head can only create tasks for their own department members.
        Staff/Intern cannot create tasks.
        """
        return self.is_portal_admin() or self.role in {
            self.Role.PROGRAM_MANAGER, self.Role.DEPARTMENT_HEAD
        }

    def can_manage_events(self):
        """Only Admin and Program Manager create/manage events."""
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def can_monitor_attendance(self):
        """
        Admin and PM see org-wide attendance stats.
        Dept Head sees attendance but only for their own department.
        """
        return self.is_portal_admin() or self.role in {
            self.Role.PROGRAM_MANAGER, self.Role.DEPARTMENT_HEAD
        }

    def can_monitor_all_attendance(self):
        """Admin and PM only — org-wide attendance access, not dept-restricted."""
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def can_manage_communication(self):
        """
        Admin and PM can publish org-wide announcements.
        Dept Head can only post in their department channel.
        """
        return self.is_portal_admin() or self.role in {
            self.Role.PROGRAM_MANAGER, self.Role.DEPARTMENT_HEAD
        }

    def can_publish_announcements(self):
        """Only Admin and PM can create org-wide announcements."""
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def can_view_reports(self):
        """Only Admin and Program Manager download full org reports."""
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def can_review_suggestions(self):
        """
        Admin and PM review all suggestions.
        Dept Head can review suggestions from their own department members.
        """
        return self.is_portal_admin() or self.role in {
            self.Role.PROGRAM_MANAGER, self.Role.DEPARTMENT_HEAD
        }

    def can_manage_users(self):
        """Only Admin can add/edit/deactivate users and manage departments."""
        return self.is_portal_admin()

    def can_view_geofence_violations(self):
        """Admin and PM see all geofence violations. Dept Head cannot."""
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def can_view_location_activity(self):
        """Admin and PM see location activity. Dept Head cannot."""
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def save(self, *args, **kwargs):
        if self.role == self.Role.ADMIN:
            self.is_staff = True
            self.is_superuser = True
        super().save(*args, **kwargs)

    def __str__(self):
        return self.get_full_name() or self.username
