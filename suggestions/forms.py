from django import forms
from .models import Suggestion


class SuggestionForm(forms.ModelForm):
    class Meta:
        model = Suggestion
        fields = ("title", "message", "category", "anonymous")


class SuggestionReviewForm(forms.ModelForm):
    class Meta:
        model = Suggestion
        fields = ("status", "response")

