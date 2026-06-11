from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import models as db_models
import json
from core.permissions import capability_required
from core.notify import notify_all, notify_user, notify_managers
from core.reports import excel_response, pdf_response
from attendance.utils import haversine_distance_meters
from .forms import EventForm
from .models import (
    Event, EventAttendance, EventRegistration,
    EventCheckIn, FormResponse,
)


def _extract_field(data, keys):
    """Try multiple key names and return the first non-empty value found."""
    for k in keys:
        v = data.get(k, "")
        if isinstance(v, list):
            v = v[0] if v else ""
        v = str(v).strip()
        if v and v.lower() not in ("none", "null", "undefined", "n/a"):
            return v
    return ""


# ── Event listing ─────────────────────────────────────────────────────────

@login_required
def event_list(request):
    now = timezone.now()
    upcoming = Event.objects.filter(end_date__gte=now).order_by("start_date")
    past = Event.objects.filter(end_date__lt=now).order_by("-start_date")
    reg_event_ids = set(
        EventRegistration.objects
        .filter(participant=request.user)
        .values_list("event_id", flat=True)
    )
    return render(request, "events/list.html", {
        "upcoming": upcoming,
        "past": past,
        "reg_event_ids": reg_event_ids,
    })


@capability_required("can_manage_events")
def event_create(request):
    form = EventForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        event = form.save()
        notify_all(
            f"New event: {event.title}",
            f'A new event "{event.title}" has been scheduled at {event.location} on '
            f'{event.start_date:%b %d, %Y}. Register now!',
            exclude_pk=request.user.pk,
            link=f"/events/{event.pk}/",
        )
        messages.success(request, "Event created.")
        return redirect("events:list")
    return render(request, "form.html", {"form": form, "title": "Create Event"})


@capability_required("can_manage_events")
def event_edit(request, pk):
    """Admin/PM edits an existing event."""
    event = get_object_or_404(Event, pk=pk)
    form = EventForm(request.POST or None, request.FILES or None, instance=event)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f'Event "{event.title}" updated.')
        return redirect("events:detail", pk=pk)
    return render(request, "form.html", {"form": form, "title": f"Edit Event: {event.title}"})


@login_required
def event_detail(request, pk):
    event = get_object_or_404(Event, pk=pk)
    registered   = EventRegistration.objects.filter(event=event, participant=request.user).exists()
    checked_in   = EventCheckIn.objects.filter(event=event, participant=request.user).exists()
    event_started = timezone.now() >= event.start_date
    return render(request, "events/detail.html", {
        "event":         event,
        "registered":    registered,
        "checked_in":    checked_in,
        "event_started": event_started,
    })


# ── Registration ──────────────────────────────────────────────────────────

@login_required
def register(request, pk):
    event = get_object_or_404(Event, pk=pk)

    if event.is_past:
        messages.error(request, "This event has already ended.")
        return redirect("events:detail", pk=pk)

    if event.is_full:
        messages.error(request, "This event is fully booked.")
        return redirect("events:detail", pk=pk)

    if EventRegistration.objects.filter(event=event, participant=request.user).exists():
        messages.info(request, "You are already registered for this event.")
        return redirect("events:detail", pk=pk)

    if request.method == "POST":
        name  = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()

        if not name or not email:
            messages.error(request, "Name and email are required.")
            return render(request, "events/register_form.html", {
                "event": event, "name": name, "email": email, "phone": phone,
            })

        reg, created = EventRegistration.objects.get_or_create(
            event=event, participant=request.user
        )
        if not created:
            messages.info(request, "You are already registered for this event.")
            return redirect("events:detail", pk=pk)

        FormResponse.objects.get_or_create(
            event=event,
            respondent_email=email,
            defaults={
                "respondent_name":  name,
                "respondent_phone": phone,
                "raw_data": {
                    "source":   "portal_registration",
                    "user_pk":  request.user.pk,
                    "username": request.user.username,
                },
            },
        )

        real_count = EventRegistration.objects.filter(event=event).count()
        Event.objects.filter(pk=event.pk).update(form_response_count=real_count)
        event.refresh_from_db(fields=["form_response_count"])

        if event.form_response_count >= event.capacity:
            notify_all(
                f"Event fully booked: {event.title}",
                f'"{event.title}" has reached maximum capacity ({event.capacity} registrations).',
                link=f"/events/{event.pk}/",
            )

        notify_user(
            request.user,
            f"Registration confirmed: {event.title}",
            f'You have successfully registered for "{event.title}" on '
            f'{event.start_date:%b %d, %Y} at {event.location}.',
            link=f"/events/{event.pk}/",
        )
        notify_managers(
            f"New event registration: {event.title}",
            f'{request.user.get_full_name() or request.user.username} registered for "{event.title}".',
            link=f"/events/{event.pk}/",
        )

        messages.success(request, f"You are registered for {event.title}!")
        return redirect("events:detail", pk=pk)

    return render(request, "events/register_form.html", {
        "event": event,
        "name":  request.user.get_full_name() or "",
        "email": request.user.email or "",
        "phone": getattr(request.user, "phone_number", "") or "",
    })


# ── Geofence check-in for events ─────────────────────────────────────────

@login_required
@require_POST
def event_checkin(request, pk):
    """
    Strict geofence check-in. User must be:
      1. Registered for the event.
      2. On or after the event start date.
      3. Within venue_radius_meters of the GPS coordinates.
    """
    event = get_object_or_404(Event, pk=pk)

    if not EventRegistration.objects.filter(event=event, participant=request.user).exists():
        return JsonResponse({"ok": False, "error": "You are not registered for this event."}, status=403)

    if EventCheckIn.objects.filter(event=event, participant=request.user).exists():
        return JsonResponse({"ok": False, "already": True, "message": "You have already checked in."})

    if event.is_past:
        return JsonResponse({"ok": False, "error": "This event has ended."}, status=400)

    if timezone.now() < event.start_date:
        return JsonResponse({
            "ok": False,
            "error": f"Check-in opens on event day ({event.start_date:%b %d, %Y at %H:%M}). Please come back then.",
        }, status=400)

    try:
        body = json.loads(request.body) if request.body else {}
        lat = Decimal(str(body.get("latitude", "")))
        lng = Decimal(str(body.get("longitude", "")))
        if not (-90 <= float(lat) <= 90) or not (-180 <= float(lng) <= 180):
            raise ValueError("Coordinates out of range")
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid or missing location data."}, status=400)

    if not event.venue_latitude or not event.venue_longitude:
        return JsonResponse({
            "ok": False,
            "error": "Venue GPS coordinates have not been set. An admin must edit the event to enable check-in.",
        }, status=400)

    distance = haversine_distance_meters(
        float(lat), float(lng),
        float(event.venue_latitude), float(event.venue_longitude),
    )
    radius = event.venue_radius_meters or 200

    if distance > radius:
        return JsonResponse({
            "ok": False,
            "error": f"You are {distance:.0f} m from the venue. Must be within {radius} m to check in.",
            "distance_meters": round(float(distance), 1),
            "allowed_radius":  radius,
        }, status=400)

    checkin = EventCheckIn.objects.create(
        event=event,
        participant=request.user,
        latitude=lat,
        longitude=lng,
        distance_meters=Decimal(str(round(float(distance), 2))),
    )

    notify_user(
        request.user,
        f"Event check-in recorded: {event.title}",
        f'Your physical attendance at "{event.title}" has been confirmed. You were {distance:.0f} m from the venue.',
        link=f"/events/{event.pk}/",
    )
    notify_managers(
        f"Event check-in: {event.title}",
        f'{request.user.get_full_name() or request.user.username} checked in ({distance:.0f} m from venue).',
        link=f"/events/{event.pk}/",
    )

    return JsonResponse({
        "ok": True,
        "message": "Check-in confirmed!",
        "checked_in_at": checkin.checked_in_at.strftime("%d %b %Y, %H:%M"),
        "distance_meters": round(float(distance), 1),
    })


# ── Live count API ────────────────────────────────────────────────────────

def registration_count_api(request, pk):
    """Live registration count — always reads from EventRegistration table."""
    event = get_object_or_404(Event, pk=pk)
    real_count = EventRegistration.objects.filter(event=event).count()
    if event.form_response_count != real_count:
        Event.objects.filter(pk=pk).update(form_response_count=real_count)
    return JsonResponse({
        "portal_count":      real_count,
        "form_count":        real_count,
        "capacity":          event.capacity,
        "is_full":           real_count >= event.capacity,
        "is_past":           event.is_past,
        "registration_open": not event.is_past and real_count < event.capacity,
    })


# ── Admin delete ──────────────────────────────────────────────────────────

@capability_required("can_manage_events")
def event_delete(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if request.method == "POST":
        title = event.title
        if event.banner:
            try:
                event.banner.delete(save=False)
            except Exception:
                pass
        event.delete()
        messages.success(request, f'Event "{title}" has been deleted.')
        return redirect("events:list")
    return render(request, "events/confirm_delete.html", {"event": event})


# ── No-shows overview ─────────────────────────────────────────────────────

@capability_required("can_manage_events")
def all_no_shows(request):
    from accounts.models import User as PortalUser
    total_portal_users = PortalUser.objects.filter(is_active=True).count()
    data = []
    for event in Event.objects.order_by("-start_date"):
        total_reg = EventRegistration.objects.filter(event=event).count()
        total_att = EventCheckIn.objects.filter(event=event).count()
        no_show   = max(total_reg - total_att, 0)
        not_reg   = max(total_portal_users - total_reg, 0)
        data.append({
            "event":      event,
            "registered": total_reg,
            "attended":   total_att,
            "no_show":    no_show,
            "not_reg":    not_reg,
            "rate":       round(no_show / total_reg * 100) if total_reg else 0,
        })
    return render(request, "events/all_no_shows.html", {
        "data": data,
        "total_portal_users": total_portal_users,
    })


@capability_required("can_manage_events")
def no_shows(request, pk):
    event = get_object_or_404(Event, pk=pk)
    registrations = EventRegistration.objects.filter(event=event).select_related("participant")
    checked_in_ids = set(
        EventCheckIn.objects.filter(event=event).values_list("participant_id", flat=True)
    )
    no_show_list = [r for r in registrations if r.participant_id not in checked_in_ids]
    did_attend   = [r for r in registrations if r.participant_id in checked_in_ids]
    return render(request, "events/no_shows.html", {
        "event":            event,
        "no_show_list":     no_show_list,
        "did_attend":       did_attend,
        "total_registered": registrations.count(),
        "total_attended":   len(did_attend),
        "total_no_show":    len(no_show_list),
    })


@capability_required("can_manage_events")
def no_shows_report(request, pk, fmt):
    event = get_object_or_404(Event, pk=pk)
    registrations = EventRegistration.objects.filter(event=event).select_related("participant")
    checked_in_ids = set(
        EventCheckIn.objects.filter(event=event).values_list("participant_id", flat=True)
    )
    headers = ["#", "Name", "Email", "Phone", "Registered At", "Attended?"]
    rows = []
    for i, r in enumerate(registrations.order_by("registration_date"), 1):
        u = r.participant
        rows.append([
            i,
            u.get_full_name() or u.username,
            u.email,
            getattr(u, "phone_number", "") or "—",
            r.registration_date.strftime("%d %b %Y, %H:%M"),
            "Yes" if r.participant_id in checked_in_ids else "No",
        ])
    filename = f"event-{event.pk}-no-shows"
    subtitle = (
        f"Registered: {len(rows)}  ·  "
        f"Attended: {sum(1 for r in rows if r[5]=='Yes')}  ·  "
        f"No-Shows: {sum(1 for r in rows if r[5]=='No')}"
    )
    if fmt == "xlsx":
        return excel_response(filename, headers, rows, subtitle=subtitle)
    return pdf_response(filename, f"No-Shows: {event.title}", headers, rows, subtitle=subtitle)


# ── Not registered ────────────────────────────────────────────────────────

@capability_required("can_manage_events")
def not_registered(request, pk):
    from accounts.models import User as PortalUser
    event = get_object_or_404(Event, pk=pk)
    registered_ids = set(
        EventRegistration.objects.filter(event=event).values_list("participant_id", flat=True)
    )
    total_portal = PortalUser.objects.filter(is_active=True).count()
    users = PortalUser.objects.filter(is_active=True).exclude(
        pk__in=registered_ids
    ).order_by("first_name", "username")
    return render(request, "events/not_registered.html", {
        "event":            event,
        "users":            users,
        "total":            users.count(),
        "total_portal":     total_portal,
        "registered_count": len(registered_ids),
    })


@capability_required("can_manage_events")
def not_registered_report(request, pk, fmt):
    from accounts.models import User as PortalUser
    event = get_object_or_404(Event, pk=pk)
    registered_ids = set(
        EventRegistration.objects.filter(event=event).values_list("participant_id", flat=True)
    )
    users = PortalUser.objects.filter(is_active=True).exclude(
        pk__in=registered_ids
    ).order_by("first_name", "username")
    total_portal = PortalUser.objects.filter(is_active=True).count()
    headers = ["#", "Name", "Email", "Phone", "Role", "Department"]
    rows = [
        [
            i,
            u.get_full_name() or u.username,
            u.email,
            getattr(u, "phone_number", "") or "—",
            u.role,
            str(u.department) if u.department else "—",
        ]
        for i, u in enumerate(users, 1)
    ]
    filename = f"event-{event.pk}-not-registered"
    subtitle = f"Did not register: {len(rows)} of {total_portal} portal users  ·  Event: {event.title}"
    if fmt == "xlsx":
        return excel_response(filename, headers, rows, subtitle=subtitle)
    return pdf_response(filename, f"Not Registered: {event.title}", headers, rows, subtitle=subtitle)


# ── Registration report ───────────────────────────────────────────────────

@capability_required("can_manage_events")
def report(request, pk, fmt):
    event = get_object_or_404(Event, pk=pk)

    checked_in_ids = set(
        EventCheckIn.objects.filter(event=event).values_list("participant_id", flat=True)
    )

    form_rows = list(
        event.form_responses.order_by("submitted_at")
        .values_list("respondent_name", "respondent_email",
                     "respondent_phone", "submitted_at", "raw_data")
    )
    portal_rows = [
        (
            r.participant.get_full_name() or r.participant.username,
            r.participant.email,
            getattr(r.participant, "phone_number", "") or "",
            r.registration_date,
            {"source": "portal_registration", "user_pk": r.participant_id},
        )
        for r in event.registrations.select_related("participant").order_by("registration_date")
    ]

    seen_emails = set()
    rows = []

    for name, email, phone, when, raw in form_rows:
        key = (email or "").lower().strip()
        if key:
            seen_emails.add(key)
        src_tag = (raw or {}).get("source", "")
        if src_tag == "portal_registration":
            source = "Portal"
        elif src_tag in ("portal_qr_scan", "anonymous_qr_scan"):
            source = "QR Scan"
        else:
            source = "Google Form"
        raw_data = raw if raw else {}
        if isinstance(raw_data.get("responses"), dict):
            raw_data = raw_data["responses"]

        def _pull(field, keys):
            if field:
                return field
            for k in keys:
                v = raw_data.get(k, "")
                if isinstance(v, list):
                    v = v[0] if v else ""
                v = str(v).strip()
                if v and v.lower() not in ("", "none", "null"):
                    return v
            return ""

        name  = _pull(name,  ["name", "full_name", "Full Name"])
        email = _pull(email, ["email", "Email Address", "Email"])
        phone = _pull(phone, ["phone", "Phone Number", "Phone"])
        user_pk  = (raw or {}).get("user_pk")
        attended = "Yes" if user_pk and int(user_pk) in checked_in_ids else "—"
        rows.append([name or "—", email or "—", phone or "—",
                     when.strftime("%d %b %Y, %H:%M") if hasattr(when, "strftime") else str(when),
                     source, attended])

    for name, email, phone, when, raw in portal_rows:
        key = (email or "").lower().strip()
        if key and key in seen_emails:
            continue
        user_pk  = (raw or {}).get("user_pk")
        attended = "Yes" if user_pk and int(user_pk) in checked_in_ids else "—"
        rows.append([name or "—", email or "—", phone or "—",
                     when.strftime("%d %b %Y, %H:%M") if hasattr(when, "strftime") else str(when),
                     "Portal", attended])

    gap = event.form_response_count - len(rows)
    for _ in range(max(gap, 0)):
        rows.append(["(pre-history)", "—", "—", "—", "—", "—"])

    if not rows:
        rows = [["(No data)", "", "", "", f"{event.form_response_count} total", ""]]

    headers = ["#", "Name", "Email", "Phone", "Registered At", "Source", "Attended?"]
    numbered = [[i + 1] + r for i, r in enumerate(rows)]
    filename = f"event-{event.pk}-{event.title[:30]}-registrations"
    subtitle = (
        f"{len(rows)} registrant(s)  ·  Capacity: {event.capacity}  ·  "
        f"Attended: {sum(1 for r in rows if r[5] == 'Yes')}"
    )
    if fmt == "xlsx":
        return excel_response(filename, headers, numbered, subtitle=subtitle)
    return pdf_response(filename, f"Registrations: {event.title}", headers, numbered, subtitle=subtitle)


# ── Apps Script webhooks ──────────────────────────────────────────────────

@csrf_exempt
@require_POST
def form_response_webhook(request, pk):
    from django.conf import settings as _s
    secret = getattr(_s, "EVENTS_WEBHOOK_SECRET", "")
    if secret and request.headers.get("X-Webhook-Secret") != secret:
        return JsonResponse({"error": "Forbidden"}, status=403)
    event = get_object_or_404(Event, pk=pk)
    try:
        body = json.loads(request.body) if request.body else {}
    except (ValueError, TypeError):
        body = {}
    if event.form_response_count >= event.capacity:
        return JsonResponse({"ok": False, "reason": "capacity_reached",
                             "form_response_count": event.form_response_count, "capacity": event.capacity})
    nested = body.get("responses", {}) if isinstance(body.get("responses"), dict) else {}
    name  = _extract_field(body, ["name", "full_name", "Full Name", "respondent_name"]) or _extract_field(nested, ["name", "full_name", "Full Name"])
    email = _extract_field(body, ["email", "Email Address", "Email", "respondent_email"]) or _extract_field(nested, ["email", "Email Address", "Email"])
    phone = _extract_field(body, ["phone", "Phone Number", "Phone", "respondent_phone"]) or _extract_field(nested, ["phone", "Phone Number", "Phone"])
    from django.utils import timezone as _tz
    two_hours_ago = _tz.now() - __import__('datetime').timedelta(hours=2)
    anon = (FormResponse.objects.filter(event=event, respondent_name="", respondent_email="",
            raw_data__source="portal_registration", submitted_at__gte=two_hours_ago)
            .order_by("-submitted_at").first())
    if anon:
        anon.respondent_name = name; anon.respondent_email = email
        anon.respondent_phone = phone; anon.raw_data = body
        anon.save(update_fields=["respondent_name", "respondent_email", "respondent_phone", "raw_data"])
        event.refresh_from_db(fields=["form_response_count"])
    else:
        FormResponse.objects.create(event=event, respondent_name=name,
                                    respondent_email=email, respondent_phone=phone, raw_data=body)
        Event.objects.filter(pk=pk).update(form_response_count=db_models.F("form_response_count") + 1)
        event.refresh_from_db(fields=["form_response_count"])
    if event.form_response_count >= event.capacity:
        notify_all(f"Event fully booked: {event.title}",
                   f'"{event.title}" has reached maximum capacity ({event.capacity}).',
                   link=f"/events/{event.pk}/")
    return JsonResponse({"ok": True, "event_id": event.pk,
                         "form_response_count": event.form_response_count,
                         "capacity": event.capacity,
                         "is_full": event.form_response_count >= event.capacity,
                         "saved": {"name": name, "email": email, "phone": phone},
                         "enriched": anon is not None})


@csrf_exempt
@require_POST
def form_response_webhook_byid(request):
    from django.conf import settings as _s
    secret = getattr(_s, "EVENTS_WEBHOOK_SECRET", "")
    if secret and request.headers.get("X-Webhook-Secret") != secret:
        return JsonResponse({"error": "Forbidden"}, status=403)
    try:
        body = json.loads(request.body) if request.body else {}
    except (ValueError, TypeError):
        body = {}
    event_id = body.get("event_id") or body.get("eventId")
    if not event_id:
        return JsonResponse({"error": "event_id required in body"}, status=400)
    event = None
    eid = str(event_id).strip()
    if eid.isdigit():
        try:
            event = Event.objects.get(pk=int(eid))
        except Event.DoesNotExist:
            pass
    if event is None:
        try:
            event = Event.objects.get(title__iexact=eid)
        except Event.DoesNotExist:
            return JsonResponse({"error": f"Event '{eid}' not found"}, status=404)
        except Event.MultipleObjectsReturned:
            event = (Event.objects.filter(title__iexact=eid, end_date__gte=timezone.now())
                     .order_by("start_date").first())
            if not event:
                return JsonResponse({"error": f"No active event named '{eid}'"}, status=404)
    if event.form_response_count >= event.capacity:
        return JsonResponse({"ok": False, "reason": "capacity_reached",
                             "form_response_count": event.form_response_count, "capacity": event.capacity})
    nested = body.get("responses", {}) if isinstance(body.get("responses"), dict) else {}
    name  = _extract_field(body, ["name", "full_name", "Full Name", "respondent_name"]) or _extract_field(nested, ["name", "full_name", "Full Name"])
    email = _extract_field(body, ["email", "Email Address", "Email", "respondent_email"]) or _extract_field(nested, ["email", "Email Address", "Email"])
    phone = _extract_field(body, ["phone", "Phone Number", "Phone", "respondent_phone"]) or _extract_field(nested, ["phone", "Phone Number", "Phone"])
    from django.utils import timezone as _tz
    two_hours_ago = _tz.now() - __import__('datetime').timedelta(hours=2)
    anon = (FormResponse.objects.filter(event=event, respondent_name="", respondent_email="",
            submitted_at__gte=two_hours_ago).order_by("-submitted_at").first())
    if anon:
        anon.respondent_name = name; anon.respondent_email = email
        anon.respondent_phone = phone; anon.raw_data = body
        anon.save(update_fields=["respondent_name", "respondent_email", "respondent_phone", "raw_data"])
        event.refresh_from_db(fields=["form_response_count"])
    else:
        FormResponse.objects.create(event=event, respondent_name=name,
                                    respondent_email=email, respondent_phone=phone, raw_data=body)
        Event.objects.filter(pk=event.pk).update(
            form_response_count=db_models.F("form_response_count") + 1)
        event.refresh_from_db(fields=["form_response_count"])
    if event.form_response_count >= event.capacity:
        notify_all(f"Event fully booked: {event.title}",
                   f'"{event.title}" has reached maximum capacity ({event.capacity}).',
                   link=f"/events/{event.pk}/")
    return JsonResponse({"ok": True, "event_id": event.pk,
                         "form_response_count": event.form_response_count,
                         "capacity": event.capacity,
                         "is_full": event.form_response_count >= event.capacity,
                         "saved": {"name": name, "email": email, "phone": phone},
                         "enriched": anon is not None})
