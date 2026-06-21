from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from core.permissions import capability_required
from core.notify import notify_user, notify_managers
from .forms import TaskAttachmentForm, TaskCommentForm, TaskForm, TaskUpdateForm
from .access import user_can_access_task, visible_tasks_for
from .models import Task


@login_required
def task_list(request):
    tasks = visible_tasks_for(request.user)
    return render(request, "tasks/list.html", {"tasks": tasks, "today": timezone.localdate()})


@capability_required("can_manage_tasks")
def task_create(request):
    form = TaskForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        task = form.save(commit=False)
        task.assigned_by = request.user
        task.save()
        # Map task priority to notification priority
        _pmap = {"low": "low", "medium": "medium", "high": "high", "critical": "critical"}
        notif_p = _pmap.get(task.priority, "medium")
        # Notify the person the task was assigned to
        if task.assigned_to != request.user:
            notify_user(
                task.assigned_to,
                "New task assigned to you",
                f'{request.user} assigned you a task: "{task.title}" — due {task.due_date}. Priority: {task.get_priority_display()}.',
                priority=notif_p,
                link=f"/tasks/{task.pk}/",
            )
        # Notify managers a task was created
        notify_managers(
            "Task created",
            f'{request.user} created task "{task.title}" assigned to {task.assigned_to}. Priority: {task.get_priority_display()}.',
            exclude_pk=request.user.pk,
            priority="low",
            link=f"/tasks/{task.pk}/",
        )
        messages.success(request, "Task created.")
        return redirect("tasks:list")
    return render(request, "form.html", {"form": form, "title": "Create Task"})


@login_required
def task_detail(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if not user_can_access_task(request.user, task):
        messages.error(request, "You do not have access to that task.")
        return redirect("tasks:list")
    can_update_status = _can_update_status(request.user, task)
    return render(request, "tasks/detail.html", {
        "task":              task,
        "comment_form":      TaskCommentForm(),
        "attachment_form":   TaskAttachmentForm(),
        "update_form":       TaskUpdateForm(instance=task),
        "can_update_status": can_update_status,
    })


@login_required
def task_update(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if not user_can_access_task(request.user, task):
        messages.error(request, "You do not have access to that task.")
        return redirect("tasks:list")

    if "status" in request.POST:
        if not _can_update_status(request.user, task):
            messages.error(request, "You do not have permission to update this task's status.")
            return redirect("tasks:detail", pk=pk)
        old_status = task.get_status_display()
        form = TaskUpdateForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            new_status = task.get_status_display()
            # Notify task creator and assignee
            for recipient in {task.assigned_to, task.assigned_by} - {None, request.user}:
                notify_user(
                    recipient,
                    f"Task status updated: {task.title}",
                    f"{request.user} changed status from {old_status} → {new_status}.",
                    priority="low",
                    link=f"/tasks/{task.pk}/",
                )
            messages.success(request, "Task status updated.")

    elif "comment" in request.POST:
        form = TaskCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.task   = task
            comment.author = request.user
            comment.save()
            # Notify other parties about the new comment
            for recipient in {task.assigned_to, task.assigned_by} - {None, request.user}:
                notify_user(
                    recipient,
                    f"New comment on task: {task.title}",
                   f'{request.user} commented: "{comment.comment[:100]}"',
                   link=f"/tasks/{task.pk}/",
                )

    elif request.FILES:
        form = TaskAttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            attachment = form.save(commit=False)
            attachment.task        = task
            attachment.uploaded_by = request.user
            attachment.save()
            for recipient in {task.assigned_to, task.assigned_by} - {None, request.user}:
                notify_user(
                    recipient,
                    f"Attachment added to task: {task.title}",
                    f"{request.user} uploaded a file to your task.",
                    link=f"/tasks/{task.pk}/",
                )

    return redirect("tasks:detail", pk=pk)


def _can_update_status(user, task):
    if user.is_portal_admin():
        return True
    if user.role in (user.Role.PROGRAM_MANAGER, user.Role.DEPARTMENT_HEAD):
        return True
    return task.assigned_to_id == user.pk
