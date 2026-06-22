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
    #
    # Role hierarchy (highest → lowest authority):
    #   Admin          — full control over everything, head of portal
    #   Program Manager — broad access; cannot manage users/departments/sites
    #   Department Head — scoped to own department only; limited org-wide access
    #   Staff / Intern  — self-service only
    #

    def can_manage_tasks(self):
        """
        Admin and PM can create/assign tasks to anyone.
        Dept Head can create tasks but only for their own department members.
        Staff/Intern cannot create tasks.
        """
        return self.is_portal_admin() or self.role in {
            self.Role.PROGRAM_MANAGER, self.Role.DEPARTMENT_HEAD
        }

    def can_manage_events(self):
        """
        Admin has full event control (create, edit, delete any event).
        PM can create and manage events but cannot delete Admin-created events.
        Dept Head can view events only — cannot create or manage.
        """
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def can_monitor_attendance(self):
        """
        Admin and PM see org-wide attendance stats.
        Dept Head sees attendance restricted to their own department only.
        """
        return self.is_portal_admin() or self.role in {
            self.Role.PROGRAM_MANAGER, self.Role.DEPARTMENT_HEAD
        }

    def can_monitor_all_attendance(self):
        """
        Admin and PM — unrestricted org-wide attendance access.
        Dept Head is excluded (use can_monitor_attendance for dept-scoped access).
        """
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def can_manage_communication(self):
        """
        Admin and PM can publish org-wide announcements and manage channels.
        Dept Head can post only in their department channel.
        """
        return self.is_portal_admin() or self.role in {
            self.Role.PROGRAM_MANAGER, self.Role.DEPARTMENT_HEAD
        }

    def can_publish_announcements(self):
        """
        Admin can publish announcements visible to the entire org.
        PM can also publish org-wide announcements.
        Dept Head cannot publish org-wide — dept channel only.
        """
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def can_view_reports(self):
        """
        Admin can view and download all org reports including system/audit logs.
        PM can download standard org reports (attendance, tasks, events).
        Dept Head has no access to the reports section.
        """
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def can_review_suggestions(self):
        """
        Admin and PM can review all suggestions across the org.
        Dept Head can review suggestions from their own department members only.
        """
        return self.is_portal_admin() or self.role in {
            self.Role.PROGRAM_MANAGER, self.Role.DEPARTMENT_HEAD
        }

    def can_manage_users(self):
        """
        Only Admin can add, edit, deactivate users and manage departments.
        PM and Dept Head cannot modify user accounts or department membership.
        """
        return self.is_portal_admin()

    def can_view_users(self):
        """
        Admin has full edit access to the user directory.
        PM can view the user directory in read-only mode.
        Dept Head cannot access the user directory.
        """
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def can_view_geofence_violations(self):
        """
        Admin and PM can view geofence violations for the whole org.
        Dept Head cannot — violations are an org-wide security concern.
        """
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def can_view_location_activity(self):
        """
        Admin and PM can monitor real-time location activity.
        Dept Head cannot view org-wide location activity.
        """
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def can_manage_project_sites(self):
        """
        Only Admin can create or edit project sites (GPS boundaries).
        PM and Dept Head cannot modify site configuration.
        """
        return self.is_portal_admin()

    def can_manage_departments(self):
        """
        Only Admin can create, edit departments and assign users to them.
        PM and Dept Head cannot modify department structure.
        """
        return self.is_portal_admin()

    def save(self, *args, **kwargs):
        if self.role == self.Role.ADMIN:
            self.is_staff = True
            self.is_superuser = True
        super().save(*args, **kwargs)

    def __str__(self):
        return self.get_full_name() or self.username
