from django import forms
from .models import Task, TaskAttachment, TaskComment


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ("title", "description", "assigned_to", "priority", "status", "due_date")
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}


class TaskUpdateForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ("status",)


class TaskCommentForm(forms.ModelForm):
    class Meta:
        model = TaskComment
        fields = ("comment", "progress_update")


class TaskAttachmentForm(forms.ModelForm):
    class Meta:
        model = TaskAttachment
        fields = ("file",)

