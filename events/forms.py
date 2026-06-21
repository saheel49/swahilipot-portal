from django import forms
from attendance.models import ProjectSite
from .models import Event


class EventForm(forms.ModelForm):
    """
    Event create/edit form.
    Venue location is chosen from active ProjectSites so the admin never
    has to manually type GPS coordinates.  The site's lat/lng/radius are
    copied to the event's venue_* fields on save.
    If no active sites exist, the admin is prompted to create one first.
    """

    venue_site = forms.ModelChoiceField(
        queryset=ProjectSite.objects.filter(active=True),
        required=False,
        label="Venue (from Project Sites)",
        empty_label="— Select an active project site —",
        help_text=(
            "Choose the project site where this event will be held. "
            "Its GPS coordinates and radius will be used for geofence check-in. "
            "If the venue is not listed, ask an admin to add it under Project Sites first."
        ),
    )

    class Meta:
        model = Event
        fields = (
            "title", "description", "location",
            "start_date", "end_date", "capacity", "banner",
        )
        widgets = {
            "start_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_date":   forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-select the site if the event already has venue coordinates
        if self.instance and self.instance.pk and self.instance.venue_latitude:
            # Try to match an existing site by coordinates
            try:
                site = ProjectSite.objects.get(
                    latitude=self.instance.venue_latitude,
                    longitude=self.instance.venue_longitude,
                )
                self.fields["venue_site"].initial = site
            except (ProjectSite.DoesNotExist, ProjectSite.MultipleObjectsReturned):
                pass

        # Warn if no active sites exist
        if not ProjectSite.objects.filter(active=True).exists():
            self.fields["venue_site"].help_text = (
                "⚠ No active project sites found. "
                "Please ask an admin to add a project site under "
                "Attendance → Project Sites before creating events with geofence check-in."
            )

    def save(self, commit=True):
        event = super().save(commit=False)
        site = self.cleaned_data.get("venue_site")
        if site:
            event.venue_latitude     = site.latitude
            event.venue_longitude    = site.longitude
            event.venue_radius_meters = site.radius_meters
        if commit:
            event.save()
        return event
