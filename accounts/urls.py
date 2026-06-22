from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    # ── Profile & password ────────────────────────────────────────────────
    path("profile/",                   views.profile,            name="profile"),
    path("recover/",                   views.password_recover,   name="password_recover"),

    # ── User Directory (Admin full / PM read-only) ────────────────────────
    path("users/",                     views.user_directory,     name="user_directory"),
    path("users/add/",                 views.user_add,           name="user_add"),
    path("users/<int:pk>/edit/",       views.user_edit,          name="user_edit"),
    path("users/<int:pk>/toggle/",     views.user_toggle_active, name="user_toggle"),
    path("users/<int:pk>/reset-password/", views.user_reset_password, name="user_reset_password"),

    # ── Departments ───────────────────────────────────────────────────────
    path("departments/",               views.department_list,    name="departments"),
    path("departments/create/",        views.department_create,  name="department_create"),
    path("departments/<int:pk>/edit/", views.department_edit,    name="department_edit"),
    path("departments/<int:dept_pk>/assign/",               views.department_assign,      name="department_assign"),
    path("departments/<int:dept_pk>/remove/<int:user_pk>/", views.department_remove_user, name="department_remove_user"),
    path("departments/<int:dept_pk>/assign-task/",          views.department_assign_task, name="department_assign_task"),

    # ── Programs (Admin CRUD) ─────────────────────────────────────────────
    path("programs/",                  views.program_list,       name="programs"),
    path("programs/create/",           views.program_create,     name="program_create"),
    path("programs/<int:pk>/edit/",    views.program_edit,       name="program_edit"),
    path("programs/<int:pk>/delete/",  views.program_delete,     name="program_delete"),

    # ── Program Manager Dashboard ─────────────────────────────────────────
    path("pm-dashboard/",              views.program_manager_dashboard, name="pm_dashboard"),

    # ── Custom Roles (Admin CRUD) ─────────────────────────────────────────
    path("roles/",                     views.custom_role_list,   name="custom_roles"),
    path("roles/create/",              views.custom_role_create, name="custom_role_create"),
    path("roles/<int:pk>/edit/",       views.custom_role_edit,   name="custom_role_edit"),
    path("roles/<int:pk>/delete/",     views.custom_role_delete, name="custom_role_delete"),
]
