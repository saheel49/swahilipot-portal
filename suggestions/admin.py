from django.contrib import admin
from .models import Suggestion


@admin.register(Suggestion)
class SuggestionAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "status", "anonymous", "submitted_at")
    list_filter = ("category", "status", "anonymous", "submitted_at")
    search_fields = ("title", "message", "response")

