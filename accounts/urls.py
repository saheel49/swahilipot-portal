from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("profile/",                              views.profile,               name="profile"),
    path("users/",                                views.user_directory,        name="user_directory"),
    path("users/<int:pk>/edit/",                  views.user_edit,             name="user_edit"),
    path("users/<int:pk>/toggle/",                views.user_toggle_active,    name="user_toggle"),
    path("departments/",                          views.department_list,       name="departments"),
    path("departments/create/",                   views.department_create,     name="department_create"),
    path("departments/<int:pk>/edit/",            views.department_edit,       name="department_edit"),
    path("departments/<int:dept_pk>/assign/",     views.department_assign,     name="department_assign"),
    path("departments/<int:dept_pk>/remove/<int:user_pk>/", views.department_remove_user, name="department_remove_user"),
    path("users/add/",                                views.user_add,              name="user_add"),
    path("users/<int:pk>/reset-password/",            views.user_reset_password,   name="user_reset_password"),
    path("departments/<int:dept_pk>/assign-task/",    views.department_assign_task, name="department_assign_task"),
    # Custom password recovery — no email needed
    path("recover/", views.password_recover, name="password_recover"),
]
