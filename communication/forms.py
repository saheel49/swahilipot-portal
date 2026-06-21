from django import forms
from accounts.models import User
from .models import Announcement, ChannelMessage, DirectMessage


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model  = Announcement
        fields = ("title", "content", "attachment")


class ChannelMessageForm(forms.ModelForm):
    class Meta:
        model  = ChannelMessage
        fields = ("content", "attachment")


class DirectMessageForm(forms.ModelForm):
    """
    Accepts an optional ``receiver_queryset`` kwarg so the view can
    restrict who appears in the recipient dropdown (active users only,
    never the sender themselves).
    """
    class Meta:
        model  = DirectMessage
        fields = ("receiver", "message", "attachment")

    def __init__(self, *args, receiver_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if receiver_queryset is not None:
            self.fields["receiver"].queryset = receiver_queryset
        self.fields["receiver"].label = "Send to"
        self.fields["message"].widget = forms.Textarea(attrs={"rows": 3})
