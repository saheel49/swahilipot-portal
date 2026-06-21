from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .forms import UserAdminCreationForm, UserAdminChangeForm
from .models import Department, User


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    add_form = UserAdminCreationForm
    form = UserAdminChangeForm
    model = User

    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "role",
        "department",
        "is_active",
    )

    list_filter = (
        "role",
        "department",
        "is_active",
        "is_staff",
    )

    search_fields = (
        "username",
        "email",
        "first_name",
        "last_name",
    )

    fieldsets = (
        *UserAdmin.fieldsets,
        (
            "Portal Profile",
            {
                "fields": (
                    "phone_number",
                    "profile_photo",
                    "department",
                    "role",
                )
            },
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "email",
                    "first_name",
                    "last_name",
                    "password1",
                    "password2",
                    "department",
                    "role",
                ),
            },
        ),
    )