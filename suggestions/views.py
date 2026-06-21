from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from core.permissions import capability_required
from core.notify import notify_managers, notify_user
from .forms import SuggestionForm, SuggestionReviewForm
from .models import Suggestion


@login_required
def suggestion_list(request):
    user = request.user
    if user.is_portal_admin() or user.role == user.Role.PROGRAM_MANAGER:
        suggestions = Suggestion.objects.all()
    elif user.role == user.Role.DEPARTMENT_HEAD and user.department_id:
        suggestions = Suggestion.objects.filter(
            Q(submitted_by__department=user.department) | Q(submitted_by=user)
        ).distinct()
    else:
        suggestions = Suggestion.objects.filter(submitted_by=user)

    return render(request, "suggestions/list.html", {"suggestions": suggestions})


@login_required
def suggestion_create(request):
    form = SuggestionForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        suggestion = form.save(commit=False)

        if not suggestion.anonymous:
            suggestion.submitted_by = request.user

        suggestion.save()

        author = "Anonymous" if suggestion.anonymous else request.user

        notify_managers(
            "New suggestion submitted",
            f'{author} submitted a suggestion: "{suggestion.title}" ({suggestion.get_category_display()}).',
            link="/suggestions/",
        )

        messages.success(request, "Suggestion submitted.")
        return redirect("suggestions:list")

    return render(request, "form.html", {"form": form, "title": "Submit Suggestion"})


@capability_required("can_review_suggestions")
def review(request, pk):
    suggestion = get_object_or_404(Suggestion, pk=pk)
    form = SuggestionReviewForm(request.POST or None, instance=suggestion)

    if request.method == "POST" and form.is_valid():
        form.save()

        # Notify the submitter that their suggestion was reviewed
        if suggestion.submitted_by:
            notify_user(
                suggestion.submitted_by,
                f"Your suggestion was {suggestion.get_status_display().lower()}",
                f'Your suggestion "{suggestion.title}" has been reviewed.'
                + (f" Response: {suggestion.response}" if suggestion.response else ""),
                link="/suggestions/",
            )

        messages.success(request, "Suggestion updated.")
        return redirect("suggestions:list")

    return render(request, "form.html", {"form": form, "title": "Review Suggestion"})
