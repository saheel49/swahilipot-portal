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
    username = forms.CharField(
        max_length=150,
        help_text="Letters, digits and @/./+/-/_ only.",
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone_number", "profile_photo")

    def clean_username(self):
        username = self.cleaned_data["username"]
        qs = User.objects.filter(username=username).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("That username is already taken.")
        return username


class UserEditForm(forms.ModelForm):
    """Admin-facing form to edit any user's role, department, username and status."""
    username = forms.CharField(
        max_length=150,
        help_text="Letters, digits and @/./+/-/_ only.",
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone_number",
                  "role", "department", "is_active")

    def clean_username(self):
        username = self.cleaned_data["username"]
        qs = User.objects.filter(username=username).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("That username is already taken.")
        return username


class AddUserForm(UserCreationForm):
    """Admin form to create a new portal user without going to the DB/admin."""
    class Meta:
        model = User
        fields = (
            "username", "first_name", "last_name", "email",
            "phone_number", "role", "department",
            "password1", "password2",
        )
