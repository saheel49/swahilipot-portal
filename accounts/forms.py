from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User, CustomRole, Program, Department


class UserAdminCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "role", "department", "custom_role")


class UserAdminChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


class ProfileForm(forms.ModelForm):
    username = forms.CharField(max_length=150, help_text="Letters, digits and @/./+/-/_ only.")

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone_number", "profile_photo")

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("That username is already taken.")
        return username


class UserEditForm(forms.ModelForm):
    """Admin-facing form to edit any user's role, department, custom role and status."""
    username = forms.CharField(max_length=150, help_text="Letters, digits and @/./+/-/_ only.")

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone_number",
                  "role", "custom_role", "department", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["custom_role"].required = False
        self.fields["custom_role"].empty_label = "— No custom role —"
        self.fields["custom_role"].help_text = (
            "Optional additional role label. Permissions still follow the built-in role above."
        )
        self.fields["department"].required = False
        self.fields["department"].empty_label = "— Unassigned —"

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("That username is already taken.")
        return username


class AddUserForm(UserCreationForm):
    """Admin form to create a new portal user."""
    class Meta:
        model = User
        fields = (
            "username", "first_name", "last_name", "email",
            "phone_number", "role", "custom_role", "department",
            "password1", "password2",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["custom_role"].required = False
        self.fields["custom_role"].empty_label = "— No custom role —"
        self.fields["department"].required = False
        self.fields["department"].empty_label = "— Unassigned —"


class CustomRoleForm(forms.ModelForm):
    class Meta:
        model = CustomRole
        fields = ("name", "description", "permission_level")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class ProgramForm(forms.ModelForm):
    class Meta:
        model = Program
        fields = ("name", "description", "manager", "departments", "start_date", "end_date", "is_active")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "start_date":  forms.DateInput(attrs={"type": "date"}),
            "end_date":    forms.DateInput(attrs={"type": "date"}),
            "departments": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["manager"].queryset = User.objects.filter(
            role="program_manager", is_active=True
        ).order_by("first_name", "username")
        self.fields["manager"].empty_label = "— Unassigned —"
        self.fields["manager"].required = False
        self.fields["departments"].required = False
