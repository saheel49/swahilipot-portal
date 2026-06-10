from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum as db_Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from accounts.models import User
from attendance.models import Attendance
from communication.models import Announcement
from core.permissions import capability_required
from core.reports import excel_response, pdf_response
from events.models import Event
from suggestions.models import Suggestion
from tasks.access import visible_tasks_for
import json as _json


@login_required
def home(request):
    today = timezone.localdate()
    user_records = Attendance.objects.filter(user=request.user)[:5]
    visible_tasks = visible_tasks_for(request.user)

    upcoming_tasks = visible_tasks.exclude(
        status__in=["completed"]
    ).order_by("due_date")[:30]

    upcoming_events = Event.objects.filter(
        start_date__date__gte=today
    ).order_by("start_date")[:20]

    cal_items = []
    for t in upcoming_tasks:
        cal_items.append({
            "title": t.title,
            "date": t.due_date.isoformat(),
            "type": "task",
            "priority": t.priority,
            "url": f"/tasks/{t.pk}/",
        })
    for e in upcoming_events:
        cal_items.append({
            "title": e.title,
            "date": e.start_date.date().isoformat(),
            "type": "event",
            "priority": "medium",
            "url": f"/events/{e.pk}/",
        })

    # Event scans: sum form_response_count across all active (not yet ended) events
    event_scans_today = (
        Event.objects
        .filter(end_date__gte=timezone.now())
        .aggregate(total=db_Sum("form_response_count"))["total"] or 0
    )

    context = {
        "announcements": Announcement.objects.all()[:5],
        "my_tasks": visible_tasks[:5],
        "my_attendance": user_records,
        "events": Event.objects.filter(end_date__gte=timezone.now()).order_by("start_date")[:5],
        "total_staff": User.objects.filter(is_active=True).count(),
        "attendance_today": Attendance.objects.filter(check_in_time__date=today).count(),
        "checked_in_now": Attendance.objects.filter(status=Attendance.Status.CHECKED_IN).count(),
        "late_arrivals": Attendance.objects.filter(
            check_in_time__date=today,
            arrival_status=Attendance.ArrivalStatus.LATE,
        ).count(),
        "not_checked_in": User.objects.filter(is_active=True).exclude(
            attendance_records__check_in_time__date=today
        ).count(),
        "event_scans_today": event_scans_today,
        "task_status": list(visible_tasks.values("status").annotate(count=Count("id"))),
        "task_status_total": max(visible_tasks.values("status").annotate(count=Count("id")).aggregate(t=Count("id"))["t"] or 1, 1),
        "suggestion_categories": list(Suggestion.objects.values("category").annotate(count=Count("id"))),
        "suggestion_categories_total": max(Suggestion.objects.count() or 1, 1),
        "event_stats": list(
            Event.objects.annotate(
                reg_count=Count("registrations"),
                att_count=Count("attendance")
            ).values("title", "reg_count", "att_count")[:8]
        ),
        "cal_items_json": _json.dumps(cal_items),
        "today_iso": today.isoformat(),
    }
    return render(request, "dashboard/home.html", context)


def live_stats(request):
    """Lightweight JSON endpoint polled by the dashboard every 15 s.
    No @login_required so it works from any tab including unauthenticated scans.
    """
    today = timezone.localdate()
    # Sum QR scans across ALL non-past events — removes date-filter bugs where
    # timezone mismatches or past end_dates cause the count to show 0.
    event_scans_today = (
        Event.objects
        .filter(end_date__gte=timezone.now())
        .aggregate(total=db_Sum("form_response_count"))["total"] or 0
    )
    return JsonResponse({
        "checked_in_now": Attendance.objects.filter(status=Attendance.Status.CHECKED_IN).count(),
        "attendance_today": Attendance.objects.filter(check_in_time__date=today).count(),
        "not_checked_in": User.objects.filter(is_active=True).exclude(
            attendance_records__check_in_time__date=today
        ).count(),
        "late_arrivals": Attendance.objects.filter(
            check_in_time__date=today,
            arrival_status=Attendance.ArrivalStatus.LATE,
        ).count(),
        "event_scans_today": event_scans_today,
    })


@login_required
def event_scan_debug(request):
    """
    Debug endpoint — open in browser to verify QR scan counts are being saved.
    Visit: /dashboard/event-scan-debug/
    Shows every event's form_response_count, google_form_url, and QR status.
    """
    events = Event.objects.all().order_by("-start_date").values(
        "pk", "title", "form_response_count", "google_form_url",
        "start_date", "end_date", "capacity",
    )
    data = []
    for e in events:
        data.append({
            "id": e["pk"],
            "title": e["title"],
            "scans": e["form_response_count"],
            "capacity": e["capacity"],
            "google_form_url": e["google_form_url"] or "NOT SET",
            "start_date": str(e["start_date"]),
            "end_date": str(e["end_date"]),
            "is_past": e["end_date"] < timezone.now(),
        })
    total_scans = sum(d["scans"] for d in data)
    return JsonResponse({
        "total_scans_all_events": total_scans,
        "now": str(timezone.now()),
        "events": data,
    }, json_dumps_params={"indent": 2})


def filtered_dates(request, qs, field):
    start = request.GET.get("start")
    end = request.GET.get("end")
    if start:
        qs = qs.filter(**{f"{field}__date__gte": start})
    if end:
        qs = qs.filter(**{f"{field}__date__lte": end})
    return qs


@capability_required("can_view_reports")
def reports(request):
    return render(request, "dashboard/reports.html")


@login_required
def reminders(request):
    """Full-page calendar + reminders view for all users."""
    today = timezone.localdate()
    visible_tasks = visible_tasks_for(request.user)

    upcoming_tasks = visible_tasks.exclude(status="completed").order_by("due_date")[:50]
    upcoming_events = Event.objects.filter(start_date__date__gte=today).order_by("start_date")[:30]

    cal_items = []
    for t in upcoming_tasks:
        cal_items.append({
            "title": t.title,
            "date": t.due_date.isoformat(),
            "type": "task",
            "priority": t.priority,
            "url": f"/tasks/{t.pk}/",
            "status": t.status,
        })
    for e in upcoming_events:
        cal_items.append({
            "title": e.title,
            "date": e.start_date.date().isoformat(),
            "type": "event",
            "priority": "medium",
            "url": f"/events/{e.pk}/",
            "status": "upcoming",
        })

    return render(request, "dashboard/reminders.html", {
        "cal_items_json": _json.dumps(cal_items),
        "today_iso": today.isoformat(),
        "upcoming_tasks": upcoming_tasks,
        "upcoming_events": upcoming_events,
    })


@capability_required("can_view_reports")
def report_download(request, kind, fmt):
    if kind == "attendance":
        qs = filtered_dates(request, Attendance.objects.select_related("user", "project_site"), "check_in_time")
        headers = ["User", "Site", "Check In", "Check Out", "Hours", "Arrival Status", "Departure Status"]
        rows = [
            [
                r.user.username,
                r.project_site.name,
                r.check_in_time,
                r.check_out_time or "",
                r.total_hours,
                r.get_arrival_status_display(),
                r.get_departure_status_display(),
            ]
            for r in qs
        ]
    elif kind == "tasks":
        # Task reports respect role-based visibility
        qs = filtered_dates(request, visible_tasks_for(request.user), "created_at")
        headers = ["Title", "Assigned To", "Assigned By", "Priority", "Status", "Due Date"]
        rows = [
            [
                t.title,
                t.assigned_to.username,
                t.assigned_by.username if t.assigned_by else "",
                t.get_priority_display(),
                t.get_status_display(),
                t.due_date,
            ]
            for t in qs
        ]
    elif kind == "events":
        qs = filtered_dates(request, Event.objects.all(), "start_date")
        headers = ["Title", "Location", "Start", "Registrations", "Attendance"]
        rows = [[e.title, e.location, e.start_date, e.registration_count(), e.attendance_count()] for e in qs]
    elif kind == "location_timeout":
        from attendance.models import LocationLog
        qs = LocationLog.objects.select_related("user").order_by("-turned_off_at")
        start = request.GET.get("start")
        end = request.GET.get("end")
        if start:
            qs = qs.filter(turned_off_at__date__gte=start)
        if end:
            qs = qs.filter(turned_off_at__date__lte=end)
        from django.utils import timezone as _tz
        headers = ["User", "Location Off At", "Location On At", "Duration Off", "Status"]
        rows = [
            [
                log.user.get_full_name() or log.user.username,
                _tz.localtime(log.turned_off_at).strftime("%d %b %Y %H:%M") if log.turned_off_at else "",
                _tz.localtime(log.turned_on_at).strftime("%d %b %Y %H:%M") if log.turned_on_at else "—",
                log.duration_display,
                "Closed" if log.turned_on_at else "Still Off",
            ]
            for log in qs
        ]
    else:
        qs = filtered_dates(request, Suggestion.objects.all(), "submitted_at")
        headers = ["Title", "Category", "Status", "Anonymous", "Submitted At"]
        rows = [[s.title, s.get_category_display(), s.get_status_display(), s.anonymous, s.submitted_at] for s in qs]

    filename = f"{kind}-report"
    if fmt == "xlsx":
        return excel_response(filename, headers, rows)
    return pdf_response(filename, filename.replace("-", " ").title(), headers, rows)
