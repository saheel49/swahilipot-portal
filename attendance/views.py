from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from datetime import datetime, timedelta
from communication.models import Notification
from core.permissions import role_required
from .forms import ProjectSiteForm
try:
    from django_ratelimit.decorators import ratelimit
except ImportError:
    def ratelimit(*args, **kwargs):
        def decorator(view_func):
            return view_func
        return decorator
from .models import ActivityLog, Attendance, ProjectSite
from .utils import haversine_distance_meters


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return forwarded.split(",")[0] if forwarded else request.META.get("REMOTE_ADDR")


def log_activity(request, action, description=""):
    ActivityLog.objects.create(
        user=request.user if request.user.is_authenticated else None,
        action=action, description=description, ip_address=client_ip(request)
    )


def active_site():
    """Return the single active site (backward-compat). Prefer active_sites() for multi-site support."""
    return ProjectSite.objects.filter(active=True).first()


def active_sites():
    """Return all active project sites."""
    return ProjectSite.objects.filter(active=True)


def inside_site(latitude, longitude, site):
    distance = haversine_distance_meters(latitude, longitude, site.latitude, site.longitude)
    return distance <= site.radius_meters, distance


def scheduled_datetime(day, scheduled_time):
    return timezone.make_aware(datetime.combine(day, scheduled_time), timezone.get_current_timezone())


def arrival_status(actual_time, site):
    expected = scheduled_datetime(timezone.localtime(actual_time).date(), site.expected_check_in_time)
    grace_end = expected + timedelta(minutes=site.grace_minutes)
    if actual_time < expected:
        return Attendance.ArrivalStatus.EARLY
    if actual_time <= grace_end:
        return Attendance.ArrivalStatus.ON_TIME
    return Attendance.ArrivalStatus.LATE


def departure_status(actual_time, site):
    expected = scheduled_datetime(timezone.localtime(actual_time).date(), site.expected_check_out_time)
    grace_end = expected + timedelta(minutes=site.grace_minutes)
    if actual_time < expected:
        return Attendance.DepartureStatus.LEFT_EARLY
    if actual_time <= grace_end:
        return Attendance.DepartureStatus.ON_TIME
    return Attendance.DepartureStatus.LEFT_LATE


def notify_attendance(user, title, message, priority="low", link=""):
    from communication.models import Notification as _N
    _N.objects.create(user=user, title=title, message=message, priority=priority, link=link)


def auto_checkout_stale_sessions():
    """
    Auto-checkout sessions where the expected check-out time + grace period has passed.

    Behaviour:
    - Closes the session at the expected_check_out_time (not the current time).
    - Notifies the user (HIGH priority) that their session was auto-closed.
    - Notifies all admins and program managers (HIGH priority) with the user's name,
      check-in time, auto close time, and total hours recorded.
    - Logs the action in ActivityLog.
    - De-duplicated: once a session is closed it won't be processed again.
    """
    now = timezone.now()
    site = ProjectSite.objects.filter(active=True).first()
    if not site:
        return

    open_sessions = Attendance.objects.filter(
        status=Attendance.Status.CHECKED_IN,
        project_site=site,
    ).select_related("user")

    from accounts.models import User as PortalUser

    for record in open_sessions:
        check_in_local = timezone.localtime(record.check_in_time)
        check_in_date  = check_in_local.date()

        expected_checkout = scheduled_datetime(check_in_date, site.expected_check_out_time)
        grace_deadline    = expected_checkout + timedelta(minutes=site.grace_minutes)

        if now < grace_deadline:
            continue  # Still within the grace window — don't close yet

        # ── Close the session ──────────────────────────────────────────────
        close_time   = expected_checkout + timedelta(minutes=site.grace_minutes)
        # Record at the actual expected checkout (not grace end) for accurate hours
        record_close_time = expected_checkout
        duration     = record_close_time - record.check_in_time
        total_hours  = Decimal(str(round(max(duration.total_seconds(), 0) / 3600, 2)))

        record.check_out_time      = record_close_time
        record.check_out_latitude  = record.check_in_latitude
        record.check_out_longitude = record.check_in_longitude
        record.total_hours         = total_hours
        record.departure_status    = Attendance.DepartureStatus.LEFT_EARLY  # missed checkout = left early
        record.status              = Attendance.Status.CHECKED_OUT
        record.save()

        # Close any dangling LocationLog entries
        from .models import LocationLog as _LocLog
        for open_log in _LocLog.objects.filter(user=record.user, turned_on_at__isnull=True):
            open_log.close()

        user_name    = record.user.get_full_name() or record.user.username
        close_str    = timezone.localtime(record_close_time).strftime("%H:%M")
        date_str     = check_in_local.strftime("%d %b %Y")
        checkin_str  = check_in_local.strftime("%H:%M")
        deadline_str = (
            f"{site.expected_check_out_time.strftime('%H:%M')} + "
            f"{site.grace_minutes} min grace"
        )

        # ── Notify the user ────────────────────────────────────────────────
        notify_attendance(
            record.user,
            "⚠️ Auto Check-Out — You Forgot to Log Out",
            (
                f"You were automatically checked out at {close_str} on {date_str} "
                f"because you did not check out before the end of the attendance period "
                f"({deadline_str}). "
                f"You checked in at {checkin_str}. "
                f"Total hours recorded: {total_hours}h. "
                f"Please remember to check out before leaving next time."
            ),
            priority="high",
            link="/attendance/",
        )

        # ── Notify ALL admins and program managers ─────────────────────────
        managers = PortalUser.objects.filter(
            role__in=["admin", "program_manager"], is_active=True
        ).exclude(pk=record.user.pk)
        for mgr in managers:
            Notification.objects.create(
                user=mgr,
                title=f"⚠️ Auto Check-Out — {user_name}",
                message=(
                    f"{user_name} was automatically checked out at {close_str} on {date_str} "
                    f"because they did not check out before the deadline ({deadline_str}). "
                    f"Check-in time: {checkin_str}. "
                    f"Total hours recorded: {total_hours}h. "
                    f"Site: {site.name}."
                ),
                priority="high",
                link="/attendance/admin/",
            )

        ActivityLog.objects.create(
            user=record.user,
            action="auto_checkout_forgot",
            description=(
                f"Auto-closed after grace period. "
                f"Check-in: {check_in_local:%Y-%m-%d %H:%M}, "
                f"Closed at: {close_str}. Hours: {total_hours}h."
            ),
        )


@login_required
def attendance_home(request):
    # Run stale-session cleanup on every page visit
    auto_checkout_stale_sessions()
    today = timezone.localdate()
    records = Attendance.objects.filter(user=request.user)[:20]
    current = Attendance.objects.filter(user=request.user, status=Attendance.Status.CHECKED_IN).first()
    hours = Attendance.objects.filter(user=request.user, check_in_time__date=today).aggregate(
        total=Sum("total_hours"))["total"] or 0
    # Once-per-day: check if user already completed attendance today
    already_done_today = (not current) and Attendance.objects.filter(
        user=request.user,
        check_in_time__date=today,
        status=Attendance.Status.CHECKED_OUT,
    ).exists()
    sites = list(active_sites())

    # ── Active event venue hint ───────────────────────────────────────────
    # If the user is registered for an event happening today, find which
    # project site is required so we can highlight it in the template.
    from events.models import EventRegistration
    from attendance.utils import haversine_distance_meters as _hav
    now_dt = timezone.now()
    event_reg = (
        EventRegistration.objects
        .filter(
            participant=request.user,
            event__start_date__date__lte=today,
            event__end_date__gte=now_dt,
        )
        .select_related("event")
        .first()
    )
    required_site = None
    active_event = None
    if event_reg and event_reg.event.venue_latitude and event_reg.event.venue_longitude:
        active_event = event_reg.event
        for ps in ProjectSite.objects.all():
            d = _hav(
                float(active_event.venue_latitude), float(active_event.venue_longitude),
                float(ps.latitude), float(ps.longitude),
            )
            if d < 5:
                required_site = ps
                break

    return render(request, "attendance/home.html", {
        "records": records,
        "current": current,
        "hours_today": hours,
        "site": sites[0] if len(sites) == 1 else (current.project_site if current else None),
        "active_sites": sites,
        "already_done_today": already_done_today,
        "active_event":   active_event,    # event happening today (user is registered)
        "required_site":  required_site,   # the site the event requires
    })


@role_required("admin")
def site_list(request):
    return render(request, "attendance/sites.html", {"sites": ProjectSite.objects.all()})


@role_required("admin")
def site_create(request):
    initial = {
        "name": "Swahilipot Hub",
        "description": "Main Swahilipot project site",
        "latitude": "-4.0435000",
        "longitude": "39.6682000",
        "radius_meters": 100,
        "expected_check_in_time": "09:00",
        "expected_check_out_time": "17:00",
        "grace_minutes": 15,
        "active": True,
    }
    form = ProjectSiteForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        site = form.save()
        messages.success(request, "Project site saved.")
        return redirect("attendance:sites")
    return render(request, "form.html", {"form": form, "title": "Add / Edit Project Site"})


@role_required("admin")
def site_edit(request, pk):
    site = get_object_or_404(ProjectSite, pk=pk)
    form = ProjectSiteForm(request.POST or None, instance=site)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Site updated.")
        return redirect("attendance:sites")
    return render(request, "form.html", {"form": form, "title": f"Edit: {site.name}"})


@login_required
@ratelimit(key="user", rate="6/m", block=True)
def check_in(request):
    auto_checkout_stale_sessions()
    if request.method != "POST":
        return redirect("attendance:home")

    # Support multiple active sites: user picks via site_id POST param
    site_id = request.POST.get("site_id")
    if site_id:
        site = get_object_or_404(ProjectSite, pk=site_id, active=True)
    else:
        site = active_site()

    if not site:
        messages.error(request, "No active project site configured.")
        return redirect("attendance:home")
    open_record = Attendance.objects.filter(user=request.user, status=Attendance.Status.CHECKED_IN).first()
    if open_record:
        messages.warning(request, "You are already checked in.")
        return redirect("attendance:home")
    # ── Once-per-day enforcement ──────────────────────────────────────────
    today = timezone.localdate()
    already_today = Attendance.objects.filter(
        user=request.user,
        check_in_time__date=today,
    ).exists()
    if already_today:
        messages.warning(request, "You have already checked in today. Only one check-in per day is allowed.")
        return redirect("attendance:home")
    try:
        lat = Decimal(request.POST["latitude"])
        lng = Decimal(request.POST["longitude"])
    except (KeyError, Exception):
        messages.error(request, "Location data missing. Please allow location access.")
        return redirect("attendance:home")

    # ── Event venue validation ────────────────────────────────────────────
    # If the user is registered for an active event today, verify they are
    # checking in at the correct venue site the admin set for that event.
    from events.models import EventRegistration
    from attendance.utils import haversine_distance_meters
    now_dt = timezone.now()
    active_event_reg = (
        EventRegistration.objects
        .filter(
            participant=request.user,
            event__start_date__date__lte=today,
            event__end_date__gte=now_dt,
        )
        .select_related("event")
        .first()
    )
    if active_event_reg:
        event = active_event_reg.event
        if event.venue_latitude and event.venue_longitude:
            # Find the ProjectSite that matches this event's venue coordinates
            # (tolerance: 1 m, since they were set from the site object itself)
            event_site = None
            for ps in ProjectSite.objects.all():
                d = haversine_distance_meters(
                    float(event.venue_latitude), float(event.venue_longitude),
                    float(ps.latitude), float(ps.longitude),
                )
                if d < 5:   # within 5 m → same site
                    event_site = ps
                    break

            if event_site and event_site.pk != site.pk:
                messages.error(
                    request,
                    f'Wrong site! The event "{event.title}" requires check-in at '
                    f'"{event_site.name}", but you selected "{site.name}". '
                    f'Please choose "{event_site.name}" and try again.',
                )
                return redirect("attendance:home")

    ok, distance = inside_site(lat, lng, site)
    if not ok:
        messages.error(request, f"You are {distance:.0f} m from the site (max {site.radius_meters} m). Check-in denied.")
        return redirect("attendance:home")
    arr = arrival_status(now_dt, site)
    record = Attendance.objects.create(
        user=request.user, project_site=site,
        check_in_latitude=lat, check_in_longitude=lng,
        arrival_status=arr,
    )

    # ── Auto-create EventCheckIn if user is registered for an active event ──
    # This links the GPS attendance check-in to the event, so the event
    # report's "Attended?" column shows "Yes" for this user.
    from events.models import EventCheckIn as _EventCheckIn
    if active_event_reg:
        event_for_checkin = active_event_reg.event
        _EventCheckIn.objects.get_or_create(
            event=event_for_checkin,
            participant=request.user,
            defaults={
                "latitude": lat,
                "longitude": lng,
                "distance_meters": Decimal(str(round(float(distance), 2))),
            },
        )

    arr_label = arr.replace("_", " ").title()
    notify_attendance(
        request.user,
        f"Check-in recorded — {arr_label}",
        f"You checked in at {timezone.localtime(now_dt):%H:%M} on {timezone.localtime(now_dt):%d %b %Y}. "
        f"Arrival status: {arr_label}. Remember to check out before {site.expected_check_out_time.strftime('%H:%M')}.",
        priority="low" if arr != Attendance.ArrivalStatus.LATE else "medium",
        link="/attendance/",
    )
    log_activity(request, "check_in", f"Site: {site.name}, status: {arr_label}")
    messages.success(request, f"Checked in successfully ({arr_label}).")
    return redirect("attendance:home")


@login_required
def check_out(request):
    auto_checkout_stale_sessions()
    if request.method != "POST":
        return redirect("attendance:home")
    record = Attendance.objects.filter(user=request.user, status=Attendance.Status.CHECKED_IN).first()
    if not record:
        # Check if user already completed check-in and check-out today
        today = timezone.localdate()
        completed_today = Attendance.objects.filter(
            user=request.user,
            check_in_time__date=today,
            status=Attendance.Status.CHECKED_OUT,
        ).exists()
        if completed_today:
            messages.info(request, "You have already checked in and out today.")
        else:
            messages.error(request, "No active check-in found.")
        return redirect("attendance:home")
    try:
        lat = Decimal(request.POST["latitude"])
        lng = Decimal(request.POST["longitude"])
    except (KeyError, Exception):
        messages.error(request, "Location data missing.")
        return redirect("attendance:home")
    site = record.project_site
    ok, distance = inside_site(lat, lng, site)
    if not ok:
        messages.error(request, f"You are {distance:.0f} m from the site. Check-out denied.")
        return redirect("attendance:home")
    now = timezone.now()
    dep = departure_status(now, site)
    record.close(lat, lng)
    record.departure_status = dep
    record.save(update_fields=["departure_status"])
    dep_label = dep.replace("_", " ").title()
    notify_attendance(
        request.user,
        f"Check-out recorded — {dep_label}",
        f"You checked out at {timezone.localtime(now):%H:%M} on {timezone.localtime(now):%d %b %Y}. "
        f"Total hours: {record.total_hours}h. Departure status: {dep_label}.",
        priority="low",
        link="/attendance/",
    )
    log_activity(request, "check_out", f"Hours: {record.total_hours}, departure: {dep_label}")

    # ── Close any dangling LocationLog entries for this user ───────────────
    # If location was turned off but never restored before checkout, mark as resolved now.
    from .models import LocationLog
    open_logs = LocationLog.objects.filter(user=request.user, turned_on_at__isnull=True)
    for open_log in open_logs:
        open_log.close()

    messages.success(request, f"Checked out. Hours recorded: {record.total_hours}h ({dep_label}).")
    return redirect("attendance:home")


@role_required("admin")
def admin_attendance(request):
    records = Attendance.objects.select_related("user", "project_site").order_by("-check_in_time")[:100]
    return render(request, "attendance/admin.html", {"records": records})


@role_required("admin", "program_manager", "department_head")
def attendance_today(request):
    """Filtered view: all check-ins today."""
    today = timezone.localdate()
    qs = Attendance.objects.filter(
        check_in_time__date=today,
    ).select_related("user", "project_site").order_by("-check_in_time")

    # Dept Head: restrict to their own department members only
    if request.user.role == "department_head" and not request.user.is_portal_admin():
        if request.user.department_id:
            qs = qs.filter(user__department_id=request.user.department_id)
        else:
            qs = qs.none()

    return render(request, "attendance/filtered_list.html", {
        "records": qs,
        "filter_title": "Attendance Today",
        "filter_description": f"All staff who checked in on {today.strftime('%d %b %Y')}.",
    })


@role_required("admin", "program_manager", "department_head")
def attendance_currently_in(request):
    """Filtered view: staff currently checked in."""
    qs = Attendance.objects.filter(
        status=Attendance.Status.CHECKED_IN,
    ).select_related("user", "project_site").order_by("-check_in_time")

    # Dept Head: restrict to their own department only
    if request.user.role == "department_head" and not request.user.is_portal_admin():
        if request.user.department_id:
            qs = qs.filter(user__department_id=request.user.department_id)
        else:
            qs = qs.none()

    return render(request, "attendance/filtered_list.html", {
        "records": qs,
        "filter_title": "Currently In",
        "filter_description": "Staff who are currently checked in at the site.",
    })


@role_required("admin", "program_manager", "department_head")
def attendance_currently_out(request):
    """Filtered view: active users who have NOT checked in today."""
    from accounts.models import User as PortalUser
    today = timezone.localdate()
    checked_in_today_pks = Attendance.objects.filter(
        check_in_time__date=today
    ).values_list("user_id", flat=True)
    users_out = PortalUser.objects.filter(
        is_active=True
    ).exclude(
        pk__in=checked_in_today_pks
    ).select_related("department").order_by("first_name", "username")

    # Dept Head: restrict to their own department only
    if request.user.role == "department_head" and not request.user.is_portal_admin():
        if request.user.department_id:
            users_out = users_out.filter(department_id=request.user.department_id)
        else:
            users_out = users_out.none()

    return render(request, "attendance/currently_out.html", {
        "users_out": users_out,
        "filter_title": "Currently Out",
        "filter_description": f"Active staff who have not checked in today ({today.strftime('%d %b %Y')}).",
        "today": today,
    })


@role_required("admin", "program_manager", "department_head")
def attendance_late_arrivals(request):
    """Filtered view: late arrivals today."""
    today = timezone.localdate()
    qs = Attendance.objects.filter(
        check_in_time__date=today,
        arrival_status=Attendance.ArrivalStatus.LATE,
    ).select_related("user", "project_site").order_by("-check_in_time")

    # Dept Head: restrict to their own department only
    if request.user.role == "department_head" and not request.user.is_portal_admin():
        if request.user.department_id:
            qs = qs.filter(user__department_id=request.user.department_id)
        else:
            qs = qs.none()

    return render(request, "attendance/filtered_list.html", {
        "records": qs,
        "filter_title": "Late Arrivals Today",
        "filter_description": f"Staff who arrived late on {today.strftime('%d %b %Y')}.",
    })


# ---------------------------------------------------------------------------
# Geofence ping — called periodically from the browser (JS) while checked in
# ---------------------------------------------------------------------------

import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from .models import GeofenceViolation


def _notify_management(user, violation):
    """Send an in-app notification to every admin / program-manager."""
    from accounts.models import User as PortalUser
    managers = PortalUser.objects.filter(
        role__in=["admin", "program_manager"]
    ).exclude(pk=user.pk)
    for manager in managers:
        Notification.objects.create(
            user=manager,
            title=f"⚠️ Geofence Alert — {user.get_full_name() or user.username}",
            message=(
                f"{user.get_full_name() or user.username} left the {violation.project_site.name} "
                f"perimeter at {timezone.localtime(violation.detected_at):%H:%M on %d %b %Y}. "
                f"They were {violation.distance_meters:.0f} m from the site centre "
                f"(allowed radius: {violation.project_site.radius_meters} m). "
                f"Violation ID: #{violation.pk}."
            ),
            priority="critical",
            link="/attendance/violations/",
        )
    violation.management_alerted = True
    violation.save(update_fields=["management_alerted"])


@login_required
@require_POST
def geofence_ping(request):
    """
    Endpoint polled by the frontend every 60 s while the user is checked in.
    Expects JSON body: {"latitude": ..., "longitude": ...}
    Returns JSON: {"inside": true/false, "distance": ..., "violation_id": ...}
    """
    try:
        body = json.loads(request.body)
        lat = Decimal(str(body["latitude"]))
        lng = Decimal(str(body["longitude"]))
    except (KeyError, ValueError, Exception):
        return JsonResponse({"error": "Bad payload"}, status=400)

    # Only relevant when user is checked in
    record = Attendance.objects.filter(
        user=request.user, status=Attendance.Status.CHECKED_IN
    ).first()
    if not record:
        return JsonResponse({"inside": True, "checked_in": False})

    site = record.project_site
    ok, distance = inside_site(lat, lng, site)

    if ok:
        return JsonResponse({"inside": True, "checked_in": True, "distance": round(float(distance), 1)})

    # --- User is outside the radius ---

    # Avoid duplicate violations within a 5-minute window
    five_min_ago = timezone.now() - timedelta(minutes=5)
    recent = GeofenceViolation.objects.filter(
        user=request.user, attendance=record, detected_at__gte=five_min_ago
    ).exists()

    violation = None
    if not recent:
        violation = GeofenceViolation.objects.create(
            user=request.user,
            attendance=record,
            project_site=site,
            latitude=lat,
            longitude=lng,
            distance_meters=Decimal(str(round(float(distance), 2))),
        )

        # Notify the user
        notify_attendance(
            request.user,
            "📍 Geofence Warning — You Have Left the Site",
            (
                f"You are currently {distance:.0f} m from {site.name} "
                f"(allowed radius: {site.radius_meters} m). "
                f"Please return to the site or check out if you are leaving. "
                f"Detected at {timezone.localtime(violation.detected_at):%H:%M}."
            ),
            priority="critical",
            link="/attendance/",
        )

        # Log activity
        ActivityLog.objects.create(
            user=request.user,
            action="geofence_violation",
            description=(
                f"Left radius of {site.name}. Distance: {distance:.0f} m, "
                f"allowed: {site.radius_meters} m."
            ),
            ip_address=client_ip(request),
        )

        # Alert management
        _notify_management(request.user, violation)

    return JsonResponse(
        {
            "inside": False,
            "checked_in": True,
            "distance": round(float(distance), 1),
            "radius": site.radius_meters,
            "violation_id": violation.pk if violation else None,
        }
    )


@login_required
@require_POST
def location_status(request):
    """
    Called by JS when the user's location permission changes.
    Expects JSON body: {"status": "on" | "off"}
    - Only records LocationLog entries when the user is currently checked in at a site.
    - When location turns OFF and the checkout grace period has already ended,
      triggers an automatic checkout immediately.
    - Sends timestamped notifications to the user AND all admins/program managers.
    """
    try:
        body = json.loads(request.body)
        status = body.get("status", "").strip().lower()
    except Exception:
        return JsonResponse({"error": "Bad payload"}, status=400)

    if status not in ("on", "off"):
        return JsonResponse({"error": "status must be 'on' or 'off'"}, status=400)

    from .models import LocationLog

    # ── Only track location events when the user is checked in ───────────────
    current_record = Attendance.objects.filter(
        user=request.user, status=Attendance.Status.CHECKED_IN
    ).first()

    now = timezone.now()
    now_local = timezone.localtime(now)
    now_str = now_local.strftime("%H:%M on %d %b %Y")
    user_name = request.user.get_full_name() or request.user.username

    if status == "off":
        # If not checked in, silently acknowledge but don't create a log entry
        if not current_record:
            return JsonResponse({"ok": True, "tracked": False})

        # Check if there's already an unresolved LocationLog
        open_log = (
            LocationLog.objects
            .filter(user=request.user, turned_on_at__isnull=True)
            .order_by("-turned_off_at")
            .first()
        )
        if open_log:
            open_log.turned_off_at = now
            open_log.save(update_fields=["turned_off_at"])
        else:
            LocationLog.objects.create(user=request.user, turned_off_at=now)

        # ── Check if grace period has ended → auto-checkout immediately ──────
        site = current_record.project_site
        check_in_local = timezone.localtime(current_record.check_in_time)
        expected_checkout = scheduled_datetime(check_in_local.date(), site.expected_check_out_time)
        grace_deadline = expected_checkout + timedelta(minutes=site.grace_minutes)

        if now >= grace_deadline:
            # Grace period is over and location just went off — auto-checkout now
            record_close_time = expected_checkout  # record at expected checkout for accurate hours
            duration = record_close_time - current_record.check_in_time
            total_hours = Decimal(str(round(max(duration.total_seconds(), 0) / 3600, 2)))

            current_record.check_out_time = record_close_time
            current_record.check_out_latitude = current_record.check_in_latitude
            current_record.check_out_longitude = current_record.check_in_longitude
            current_record.total_hours = total_hours
            current_record.departure_status = Attendance.DepartureStatus.LEFT_EARLY
            current_record.status = Attendance.Status.CHECKED_OUT
            current_record.save()

            checkin_str = check_in_local.strftime("%H:%M")
            close_str = timezone.localtime(record_close_time).strftime("%H:%M")
            date_str = check_in_local.strftime("%d %b %Y")
            deadline_str = (
                f"{site.expected_check_out_time.strftime('%H:%M')} + "
                f"{site.grace_minutes} min grace"
            )

            # Notify the user
            notify_attendance(
                request.user,
                "⚠️ Auto Check-Out — Location Off After Closing Time",
                (
                    f"You were automatically checked out at {close_str} on {date_str} "
                    f"because your location was turned off after the attendance period ended "
                    f"({deadline_str}). "
                    f"You checked in at {checkin_str}. "
                    f"Total hours recorded: {total_hours}h."
                ),
                priority="high",
                link="/attendance/",
            )

            # Notify managers
            from accounts.models import User as PortalUser
            managers = PortalUser.objects.filter(
                role__in=["admin", "program_manager"], is_active=True
            ).exclude(pk=request.user.pk)
            for mgr in managers:
                Notification.objects.create(
                    user=mgr,
                    title=f"⚠️ Auto Check-Out (Location Off) — {user_name}",
                    message=(
                        f"{user_name} was automatically checked out at {close_str} on {date_str} "
                        f"because their location was disabled after the grace period ({deadline_str}). "
                        f"Check-in: {checkin_str}. Hours: {total_hours}h. Site: {site.name}."
                    ),
                    priority="high",
                    link="/attendance/admin/",
                )

            ActivityLog.objects.create(
                user=request.user,
                action="auto_checkout_location_off",
                description=(
                    f"Auto-checked out: location turned off after grace period. "
                    f"Check-in: {check_in_local:%Y-%m-%d %H:%M}, "
                    f"Closed at: {close_str}. Hours: {total_hours}h."
                ),
                ip_address=client_ip(request),
            )

            return JsonResponse({"ok": True, "tracked": True, "auto_checkout": True})

        # Grace period still active — just record the location off event
        user_title   = "📵 Location Turned Off"
        user_message = (
            f"Your device location was turned OFF at {now_str}. "
            f"GPS attendance and geofence monitoring are now inactive. "
            f"Please re-enable location to continue attendance tracking."
        )
        mgr_title   = f"📵 Location Disabled — {user_name}"
        mgr_message = (
            f"{user_name} turned their device location OFF at {now_str}. "
            f"GPS-based attendance and geofence monitoring are inactive until location is re-enabled."
        )
        priority = "high"

    else:  # status == "on"
        # Close the most recent open LocationLog (no turned_on_at yet)
        # Only matters if there was an active session — if not checked in, still close
        # any dangling log from a previous session
        open_log = (
            LocationLog.objects
            .filter(user=request.user, turned_on_at__isnull=True)
            .order_by("-turned_off_at")
            .first()
        )
        duration_str = ""
        off_time_str = ""
        if open_log:
            open_log.close()
            duration_str = open_log.duration_display
            off_time_str = timezone.localtime(open_log.turned_off_at).strftime("%H:%M on %d %b %Y")

        # If not checked in, just close the log silently — no notifications needed
        if not current_record and not open_log:
            return JsonResponse({"ok": True, "tracked": False})

        user_title   = "📍 Location Turned On"
        if off_time_str and duration_str:
            user_message = (
                f"Your device location was turned ON again at {now_str}. "
                f"It had been off since {off_time_str} (duration: {duration_str}). "
                f"GPS attendance and geofence monitoring have resumed."
            )
            mgr_message = (
                f"{user_name} turned their device location ON again at {now_str}. "
                f"Location was off since {off_time_str} (duration off: {duration_str}). "
                f"GPS monitoring has resumed."
            )
        else:
            user_message = (
                f"Your device location was turned ON at {now_str}. "
                f"GPS attendance and geofence monitoring have resumed."
            )
            mgr_message = (
                f"{user_name} turned their device location ON at {now_str}. "
                f"GPS monitoring has resumed."
            )
        mgr_title = f"📍 Location Re-enabled — {user_name}"
        priority  = "medium"

    # Notify the user
    notify_attendance(request.user, user_title, user_message, priority=priority, link="/attendance/")

    # Notify all admins / program managers
    from accounts.models import User as PortalUser
    managers = PortalUser.objects.filter(
        role__in=["admin", "program_manager"], is_active=True
    ).exclude(pk=request.user.pk)
    for manager in managers:
        Notification.objects.create(
            user=manager, title=mgr_title, message=mgr_message, priority=priority,
            link="/attendance/admin/",
        )

    # Log the activity
    ActivityLog.objects.create(
        user=request.user,
        action=f"location_{status}",
        description=f"User location turned {status} at {now_str}.",
        ip_address=client_ip(request),
    )

    return JsonResponse({"ok": True, "tracked": True})


@login_required
def my_location_timeout(request):
    """Every user can see their own location on/off history with durations.
    Only meaningful when the user is checked in at a site — show a notice otherwise.
    """
    from .models import LocationLog
    # Check if user is currently checked in
    current_session = Attendance.objects.filter(
        user=request.user, status=Attendance.Status.CHECKED_IN
    ).first()
    # Check if user has ever been checked in (has any attendance record)
    has_any_attendance = Attendance.objects.filter(user=request.user).exists()

    logs = LocationLog.objects.filter(user=request.user).order_by("-turned_off_at")[:60]
    # Summary stats
    total_events = logs.count()
    resolved = [l for l in logs if l.turned_on_at is not None]
    avg_mins = (
        sum(float(l.duration_minutes) for l in resolved) / len(resolved)
        if resolved else 0
    )
    return render(request, "attendance/my_location_timeout.html", {
        "logs": logs,
        "total_events": total_events,
        "resolved_count": len(resolved),
        "avg_mins": round(avg_mins, 1),
        "current_session": current_session,
        "has_any_attendance": has_any_attendance,
    })


@login_required
def location_timeout_report(request, fmt):
    """Download own location timeout history as PDF or Excel."""
    from .models import LocationLog
    from core.reports import excel_response, pdf_response
    logs = LocationLog.objects.filter(user=request.user).order_by("-turned_off_at")
    headers = ["Turned Off At", "Turned On At", "Duration Off", "Status"]
    rows = []
    for log in logs:
        rows.append([
            timezone.localtime(log.turned_off_at).strftime("%d %b %Y %H:%M"),
            timezone.localtime(log.turned_on_at).strftime("%d %b %Y %H:%M") if log.turned_on_at else "Still Off",
            log.duration_display,
            "Resolved" if log.turned_on_at else "Location Still Off",
        ])
    fname = f"location-timeout-{request.user.username}"
    title = f"Location Timeout Report — {request.user.get_full_name() or request.user.username}"
    if fmt == "xlsx":
        return excel_response(fname, headers, rows)
    return pdf_response(fname, title, headers, rows)


@role_required("admin", "program_manager")
def geofence_violations(request):
    """Management view: list all geofence violations."""
    violations = GeofenceViolation.objects.select_related("user", "project_site", "attendance").order_by("-detected_at")[:200]
    return render(request, "attendance/geofence_violations.html", {"violations": violations})


@role_required("admin", "program_manager")
def geofence_violations_report(request, fmt):
    """Download all geofence violations as PDF or Excel."""
    from core.reports import excel_response, pdf_response
    violations = GeofenceViolation.objects.select_related("user", "project_site").order_by("-detected_at")
    headers = ["#", "Staff Member", "Email", "Site", "Detected At", "Distance (m)", "Allowed (m)", "Status", "Mgmt Alerted", "Notes"]
    rows = []
    for v in violations:
        rows.append([
            v.pk,
            v.user.get_full_name() or v.user.username,
            v.user.email,
            v.project_site.name,
            timezone.localtime(v.detected_at).strftime("%d %b %Y %H:%M"),
            f"{v.distance_meters:.0f}",
            v.project_site.radius_meters,
            v.get_resolution_display(),
            "Yes" if v.management_alerted else "No",
            v.notes or "—",
        ])
    fname = "geofence-violations-report"
    title = "Geofence Violations Report"
    if fmt == "xlsx":
        return excel_response(fname, headers, rows)
    return pdf_response(fname, title, headers, rows)


@role_required("admin", "program_manager")
def user_location_log(request, user_pk):
    """Per-user location on/off history — Admin and PM only."""
    from accounts.models import User as PortalUser
    from .models import LocationLog
    target = get_object_or_404(PortalUser, pk=user_pk)
    logs = LocationLog.objects.filter(user=target).order_by("-turned_off_at")[:60]
    unresolved_count = LocationLog.objects.filter(user=target, turned_on_at__isnull=True).count()
    return render(request, "attendance/location_log.html", {
        "target": target,
        "logs": logs,
        "unresolved_count": unresolved_count,
    })


@role_required("admin", "program_manager")
def all_location_activity(request):
    """
    Manager view — all users' recent location on/off events, newest first.
    Admin and PM only — Dept Head cannot view org-wide location activity.
    """
    from .models import LocationLog
    logs = (
        LocationLog.objects
        .select_related("user")
        .order_by("-turned_off_at")[:200]
    )
    unresolved_count = LocationLog.objects.filter(turned_on_at__isnull=True).count()
    return render(request, "attendance/all_location_activity.html", {
        "logs": logs,
        "unresolved_count": unresolved_count,
    })


@login_required
def location_off_status_api(request):
    """
    Lightweight JSON endpoint — returns list of users with location currently off.
    Called by base.html every 30 s to update the sidebar badge.
    Restricted to Admin and PM only; Dept Head and below get empty list.
    """
    from .models import LocationLog
    if not request.user.can_view_location_activity():
        return JsonResponse({"count": 0, "users": []})
    logs = (
        LocationLog.objects
        .filter(turned_on_at__isnull=True)
        .select_related("user")
        .order_by("-turned_off_at")
    )
    users = [
        {
            "name": log.user.get_full_name() or log.user.username,
            "off_since": log.turned_off_at.strftime("%H:%M"),
        }
        for log in logs
    ]
    return JsonResponse({"count": len(users), "users": users})


@role_required("admin", "program_manager")
def acknowledge_violation(request, pk):
    """Mark a violation as acknowledged."""
    if request.method == "POST":
        violation = get_object_or_404(GeofenceViolation, pk=pk)
        violation.resolution = GeofenceViolation.Resolution.ACKNOWLEDGED
        violation.notes = request.POST.get("notes", "")
        violation.save(update_fields=["resolution", "notes"])
        messages.success(request, f"Violation #{pk} acknowledged.")
    return redirect("attendance:geofence_violations")


@role_required("admin")
def admin_resolve_location_log(request, user_pk, log_pk):
    """
    Admin-only: manually resolve a 'still off' LocationLog entry.
    Used when a user's location shows as unresolved but they have turned it back on
    (e.g. GPS took time to reconnect, or the browser did not fire the 'on' event).
    Sets turned_on_at to now and calculates duration.
    """
    from .models import LocationLog
    from accounts.models import User as PortalUser

    # Verify the user exists
    target = get_object_or_404(PortalUser, pk=user_pk)

    if request.method == "POST":
        # Fetch log — allow already-resolved ones gracefully
        try:
            log = LocationLog.objects.get(pk=log_pk, user=target)
        except LocationLog.DoesNotExist:
            messages.error(request, f"Location log #{log_pk} not found for this user.")
            return redirect("attendance:location_log", user_pk=user_pk)

        if log.turned_on_at is not None:
            messages.info(request, f"Location log #{log_pk} was already resolved.")
        else:
            log.close()
            messages.success(
                request,
                f"Location log #{log_pk} resolved — duration was {log.duration_display}."
            )
        return redirect("attendance:location_log", user_pk=user_pk)

    # GET — just redirect back (should always be POST from the form)
    return redirect("attendance:location_log", user_pk=user_pk)




@role_required("admin", "program_manager", "department_head")
def missed_checkout(request):
    """
    Shows ONLY sessions that were auto-closed (staff forgot to check out).
    Identified by matching Attendance records using ActivityLog entries
    with action=auto_checkout_forgot, keyed by user+date from description.
    """
    import re
    from django.utils import timezone as _tz
    from django.db.models import Q

    # Collect (user_id, check_in_date) from activity log entries
    auto_log_qs = (
        ActivityLog.objects
        .filter(action="auto_checkout_forgot")
        .select_related("user")
        .order_by("-timestamp")[:500]
    )
    auto_keys = set()
    for log in auto_log_qs:
        if log.user_id:
            m = re.search(r"Check-in:\s*(\d{4}-\d{2}-\d{2})", log.description)
            if m:
                auto_keys.add((log.user_id, m.group(1)))

    if auto_keys:
        q = Q()
        for user_id, date_str in auto_keys:
            q |= Q(user_id=user_id, check_in_time__date=date_str)
        records = (
            Attendance.objects
            .filter(q)
            .select_related("user", "project_site")
            .order_by("-check_in_time")[:200]
        )
    else:
        records = Attendance.objects.none()

    today = _tz.localdate()
    month_start = today.replace(day=1)
    monthly_count = ActivityLog.objects.filter(
        action="auto_checkout_forgot",
        timestamp__date__gte=month_start,
    ).count()
    total_count = ActivityLog.objects.filter(action="auto_checkout_forgot").count()

    return render(request, "attendance/missed_checkout.html", {
        "records": records,
        "monthly_count": monthly_count,
        "total_count": total_count,
        "filter_title": "Missed Checkout",
        "filter_description": "Staff who forgot to check out and were automatically logged out at the site deadline.",
    })


@role_required("admin", "program_manager", "department_head")
def missed_checkout_report(request, fmt):
    """Download missed-checkout records as PDF or Excel."""
    import re
    from django.db.models import Q
    from core.reports import excel_response, pdf_response

    auto_log_qs = (
        ActivityLog.objects
        .filter(action="auto_checkout_forgot")
        .select_related("user")
        .order_by("-timestamp")[:500]
    )
    auto_keys = set()
    for log in auto_log_qs:
        if log.user_id:
            m = re.search(r"Check-in:\s*(\d{4}-\d{2}-\d{2})", log.description)
            if m:
                auto_keys.add((log.user_id, m.group(1)))

    if auto_keys:
        q = Q()
        for user_id, date_str in auto_keys:
            q |= Q(user_id=user_id, check_in_time__date=date_str)
        records = (
            Attendance.objects
            .filter(q)
            .select_related("user", "project_site")
            .order_by("-check_in_time")
        )
    else:
        records = Attendance.objects.none()

    headers = ["Staff Member", "Email", "Date", "Check In", "Auto Check-Out", "Hours", "Site"]
    rows = []
    for rec in records:
        rows.append([
            rec.user.get_full_name() or rec.user.username,
            rec.user.email,
            rec.check_in_time.strftime("%d %b %Y"),
            timezone.localtime(rec.check_in_time).strftime("%H:%M"),
            timezone.localtime(rec.check_out_time).strftime("%H:%M") if rec.check_out_time else "—",
            str(rec.total_hours) + "h" if rec.total_hours else "—",
            rec.project_site.name,
        ])

    fname = "missed-checkout-report"
    title = "Missed Checkout Report"
    if fmt == "xlsx":
        return excel_response(fname, headers, rows)
    return pdf_response(fname, title, headers, rows)
