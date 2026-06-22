from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from accounts.models import Department, User
from core.permissions import capability_required, role_required
from core.notify import notify_all, notify_user, notify_dept
from .forms import AnnouncementForm, ChannelForm, ChannelMessageForm, DirectMessageForm
from .models import Announcement, DepartmentChannel, ChannelMessage, DirectMessage, Notification


@login_required
def home(request):
    announcements = Announcement.objects.all()[:10]
    user = request.user
    if user.is_portal_admin():
        channels = DepartmentChannel.objects.select_related("department").all()
    elif user.department_id:
        channels = DepartmentChannel.objects.filter(
            department=user.department
        ).select_related("department")
    else:
        channels = DepartmentChannel.objects.none()

    messages_qs = DirectMessage.objects.filter(
        Q(sender=user) | Q(receiver=user)
    ).select_related("sender", "receiver").order_by("-timestamp")[:20]
    dm_form = DirectMessageForm(receiver_queryset=User.objects.filter(
        is_active=True
    ).exclude(pk=user.pk).order_by("first_name", "username"))
    return render(request, "communication/home.html", {
        "announcements":   announcements,
        "channels":        channels,
        "direct_messages": messages_qs,
        "dm_form":         dm_form,
    })


@capability_required("can_publish_announcements")
def announcement_create(request):
    form = AnnouncementForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        announcement = form.save(commit=False)
        announcement.created_by = request.user
        announcement.save()
        notify_all(
            f"Announcement: {announcement.title}",
            f"{request.user} posted an announcement. Check Communication for details.",
            exclude_pk=request.user.pk,
            link="/communication/",
        )
        from core.audit import audit
        audit(request, "announcement_created",
              f'{request.user} published announcement: "{announcement.title}".',
              category="communication", obj=announcement)
        messages.success(request, "Announcement published.")
        return redirect("communication:home")
    return render(request, "form.html", {"form": form, "title": "New Announcement"})


@login_required
def channel_create(request):
    """
    Admin: can create a channel for any department.
    Department Head: can only create channels for their own department.
    """
    user = request.user
    if not (user.is_portal_admin() or user.role == "department_head"):
        messages.error(request, "You do not have permission to create channels.")
        return redirect("communication:home")

    if user.is_portal_admin():
        dept_qs = Department.objects.all().order_by("name")
    else:
        # Dept head: restrict to their own department only
        if not user.department_id:
            messages.error(request, "You are not assigned to a department yet.")
            return redirect("communication:home")
        dept_qs = Department.objects.filter(pk=user.department_id)

    form = ChannelForm(request.POST or None, dept_queryset=dept_qs)
    if request.method == "POST" and form.is_valid():
        channel_obj = form.save(commit=False)
        # Dept head can only create channels for their own dept — enforce server-side
        if not user.is_portal_admin():
            channel_obj.department_id = user.department_id
        channel_obj.save()

        # Log the action
        from attendance.models import ActivityLog
        ActivityLog.objects.create(
            user=user,
            action="channel_created",
            description=f"Created channel #{channel_obj.name} in {channel_obj.department}.",
        )

        messages.success(request, f"Channel #{channel_obj.name} created.")
        return redirect("communication:home")
    return render(request, "form.html", {"form": form, "title": "Create Department Channel"})


@login_required
def channel_delete(request, pk):
    """Admin deletes any channel. Dept head deletes only their own dept's channels."""
    user = request.user
    ch = get_object_or_404(DepartmentChannel, pk=pk)

    if not user.is_portal_admin():
        if user.role != "department_head" or user.department_id != ch.department_id:
            messages.error(request, "You do not have permission to delete this channel.")
            return redirect("communication:home")

    if request.method == "POST":
        name = ch.name
        ch.delete()
        messages.success(request, f"Channel #{name} deleted.")
    return redirect("communication:home")


@login_required
def channel(request, pk):
    channel_obj = get_object_or_404(DepartmentChannel, pk=pk)
    user = request.user
    # Access: admin sees all; others must belong to the channel's department
    if not user.is_portal_admin() and user.department_id != channel_obj.department_id:
        messages.error(request, "You do not have access to this channel.")
        return redirect("communication:home")

    # Paginate messages — show last 100
    channel_messages = channel_obj.messages.select_related("sender").order_by("timestamp")[:100]

    form = ChannelMessageForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        msg = form.save(commit=False)
        msg.channel = channel_obj
        msg.sender  = user
        msg.save()
        if channel_obj.department:
            notify_dept(
                channel_obj.department,
                f"New message in #{channel_obj.name}",
                f'{user.get_full_name() or user.username} posted in #{channel_obj.name}: "{msg.content[:80]}"',
                exclude_pk=user.pk,
                link=f"/communication/channels/{channel_obj.pk}/",
            )
        return redirect("communication:channel", pk=pk)

    return render(request, "communication/channel.html", {
        "channel": channel_obj,
        "channel_messages": channel_messages,
        "form": form,
    })


@login_required
def send_direct(request):
    user = request.user
    form = DirectMessageForm(
        request.POST or None,
        request.FILES or None,
        receiver_queryset=User.objects.filter(is_active=True).exclude(pk=user.pk),
    )
    if request.method == "POST" and form.is_valid():
        dm = form.save(commit=False)
        dm.sender = user
        dm.save()
        notify_user(
            dm.receiver,
            f"New message from {user.get_full_name() or user.username}",
           f'{user} sent you a message: "{dm.message[:100]}"',
            link="/communication/",
        )
        messages.success(request, "Message sent.")
    return redirect("communication:home")


@login_required
def notification_redirect(request, pk):
    """
    Mark a single notification as read and redirect to its link.
    Called when the user clicks a notification row.

    If ``notif.link`` is empty (older notifications), we infer a sensible
    destination from the notification title so clicking always navigates
    somewhere meaningful rather than looping back to the notifications page.
    """
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.read = True
    notif.save(update_fields=["read"])

    destination = notif.link

    # ── Infer destination from title when link is blank ──────────────────
    if not destination:
        title_lower = notif.title.lower()
        if any(w in title_lower for w in ("event", "registered for", "attendance recorded")):
            destination = "/events/"
        elif any(w in title_lower for w in ("task", "comment on task", "attachment")):
            destination = "/tasks/"
        elif any(w in title_lower for w in ("check-in", "check-out", "check in", "check out",
                                             "auto check", "geofence", "location")):
            destination = "/attendance/"
        elif any(w in title_lower for w in ("message", "announcement", "channel")):
            destination = "/communication/"
        elif any(w in title_lower for w in ("suggestion",)):
            destination = "/suggestions/"
        elif any(w in title_lower for w in ("violation",)):
            destination = "/attendance/violations/"
        elif any(w in title_lower for w in ("welcome", "password", "profile")):
            destination = "/accounts/profile/"
        else:
            destination = "/communication/notifications/"

    return redirect(destination)


@login_required
def notifications(request):
    """
    Shows the current user's personal notifications.
    Supports ?count_only=1 for AJAX polling (returns JSON with total count).
    Marks all as read on POST.
    """
    user_notifs = request.user.notifications.all()

    # AJAX count-only endpoint for live polling
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        unread_qs = user_notifs.filter(read=False)
        # Determine highest priority among unread notifications for sound cue
        priority_order = ["critical", "high", "medium", "low"]
        highest = "low"
        priorities_present = set(unread_qs.values_list("priority", flat=True))
        for p in priority_order:
            if p in priorities_present:
                highest = p
                break

        # Determine notification type for distinct sounds
        # Newest unread notification drives the type; fall back to "general"
        newest_unread = unread_qs.order_by("-timestamp").first()
        notif_type = "general"
        if newest_unread:
            link = newest_unread.link or ""
            if "/tasks/" in link:
                notif_type = "task"
            elif "/events/" in link:
                notif_type = "event"
            elif "/attendance/" in link:
                notif_type = "location"

        return JsonResponse({
            "total": user_notifs.count(),
            "unread": unread_qs.count(),
            "highest_priority": highest,
            "notification_type": notif_type,
        })

    if request.method == "POST":
        user_notifs.update(read=True)

    notif_list = user_notifs[:50]
    unread_count = user_notifs.filter(read=False).count()

    return render(request, "communication/notifications.html", {
        "notifications": notif_list,
        "unread_count": unread_count,
    })
