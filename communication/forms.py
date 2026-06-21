from django import forms
from accounts.models import Department, User
from .models import Announcement, ChannelMessage, DepartmentChannel, DirectMessage


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model  = Announcement
        fields = ("title", "content", "attachment")


class ChannelForm(forms.ModelForm):
    class Meta:
        model  = DepartmentChannel
        fields = ("department", "name")

    def __init__(self, *args, dept_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if dept_queryset is not None:
            self.fields["department"].queryset = dept_queryset
        self.fields["name"].label = "Channel name"
        self.fields["department"].label = "Department"


class ChannelMessageForm(forms.ModelForm):
    class Meta:
        model  = ChannelMessage
        fields = ("content", "attachment")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["content"].widget = forms.Textarea(attrs={"rows": 2, "placeholder": "Write a message…"})
        self.fields["content"].label = ""


class DirectMessageForm(forms.ModelForm):
    class Meta:
        model  = DirectMessage
        fields = ("receiver", "message", "attachment")

    def __init__(self, *args, receiver_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if receiver_queryset is not None:
            self.fields["receiver"].queryset = receiver_queryset
        self.fields["receiver"].label = "Send to"
        self.fields["message"].widget = forms.Textarea(attrs={"rows": 3})
