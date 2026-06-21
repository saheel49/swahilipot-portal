from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User


class UserAdminCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "role", "department")


class UserAdminChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone_number", "profile_photo")



class UserEditForm(forms.ModelForm):
    """Admin-facing form to edit any user's role, department and status."""
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone_number",
                  "role", "department", "is_active")


class AddUserForm(UserCreationForm):
    """Admin form to create a new portal user without going to the DB/admin."""
    class Meta:
        model = User
        fields = (
            "username", "first_name", "last_name", "email",
            "phone_number", "role", "department",
            "password1", "password2",
        )
