from django import forms
from .models import ProjectSite


class ProjectSiteForm(forms.ModelForm):
    class Meta:
        model = ProjectSite
        fields = (
            "name",
            "description",
            "latitude",
            "longitude",
            "radius_meters",
            "expected_check_in_time",
            "expected_check_out_time",
            "grace_minutes",
            "active",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "expected_check_in_time": forms.TimeInput(attrs={"type": "time"}),
            "expected_check_out_time": forms.TimeInput(attrs={"type": "time"}),
        }
