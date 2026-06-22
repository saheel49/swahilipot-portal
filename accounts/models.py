from django.contrib.auth.models import AbstractUser
from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class CustomRole(models.Model):
    """
    Admin-defined roles beyond the 5 built-in ones.
    These appear in the user edit form and user directory as additional options.
    """
    name        = models.CharField(max_length=60, unique=True)
    description = models.TextField(blank=True)
    # Permission level: mirrors the built-in hierarchy
    # 0=staff-level, 1=dept-head-level, 2=pm-level (no admin-level custom roles)
    permission_level = models.PositiveSmallIntegerField(
        default=0,
        choices=[(0, "Staff level"), (1, "Department Head level"), (2, "Program Manager level")],
        help_text="Controls which dashboard capabilities this role inherits.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class Program(models.Model):
    """
    A program managed by a Program Manager.
    Admin creates programs and assigns a PM to each one.
    """
    name        = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    manager     = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="managed_programs",
        limit_choices_to={"role": "program_manager"},
    )
    departments = models.ManyToManyField(
        Department, blank=True, related_name="programs",
        help_text="Departments involved in this program.",
    )
    start_date  = models.DateField(null=True, blank=True)
    end_date    = models.DateField(null=True, blank=True)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class User(AbstractUser):
    BUILTIN_ROLES = [
        ("admin",           "Admin"),
        ("staff",           "Staff"),
        ("intern",          "Intern"),
        ("program_manager", "Program Manager"),
        ("department_head", "Department Head"),
    ]

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
    # Built-in role — always set
    role = models.CharField(max_length=60, choices=Role.choices, default=Role.STAFF)
    # Optional custom role label (overrides display only, not permissions)
    custom_role = models.ForeignKey(
        CustomRole, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="users",
        help_text="Optional additional/custom role label. Permissions follow the built-in role.",
    )

    last_session_key = models.CharField(max_length=40, blank=True)

    # ── helpers ───────────────────────────────────────────────────────────
    def is_portal_admin(self):
        return self.is_superuser or self.role == self.Role.ADMIN

    def is_manager(self):
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def is_dept_head(self):
        return self.role == self.Role.DEPARTMENT_HEAD

    def get_role_display(self):
        """If a custom role is set, show that; otherwise show built-in role label."""
        if self.custom_role_id:
            return self.custom_role.name
        for val, label in self.BUILTIN_ROLES:
            if self.role == val:
                return label
        return self.role

    @property
    def assigned_program(self):
        """Return the first active program this PM manages, or None."""
        if self.role == self.Role.PROGRAM_MANAGER:
            return self.managed_programs.filter(is_active=True).first()
        return None

    # ── capability gates ──────────────────────────────────────────────────

    def can_manage_tasks(self):
        return self.is_portal_admin() or self.role in {
            self.Role.PROGRAM_MANAGER, self.Role.DEPARTMENT_HEAD
        }

    def can_manage_events(self):
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def can_monitor_attendance(self):
        return self.is_portal_admin() or self.role in {
            self.Role.PROGRAM_MANAGER, self.Role.DEPARTMENT_HEAD
        }

    def can_monitor_all_attendance(self):
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def can_manage_communication(self):
        return self.is_portal_admin() or self.role in {
            self.Role.PROGRAM_MANAGER, self.Role.DEPARTMENT_HEAD
        }

    def can_publish_announcements(self):
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def can_view_reports(self):
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def can_review_suggestions(self):
        return self.is_portal_admin() or self.role in {
            self.Role.PROGRAM_MANAGER, self.Role.DEPARTMENT_HEAD
        }

    def can_manage_users(self):
        return self.is_portal_admin()

    def can_view_users(self):
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def can_view_geofence_violations(self):
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def can_view_location_activity(self):
        return self.is_portal_admin() or self.role == self.Role.PROGRAM_MANAGER

    def can_manage_project_sites(self):
        return self.is_portal_admin()

    def can_manage_departments(self):
        return self.is_portal_admin()

    def save(self, *args, **kwargs):
        if self.role == self.Role.ADMIN:
            self.is_staff = True
            self.is_superuser = True
        super().save(*args, **kwargs)

    def __str__(self):
        return self.get_full_name() or self.username
