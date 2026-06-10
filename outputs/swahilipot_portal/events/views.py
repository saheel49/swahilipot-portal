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
from .forms import EventForm
from .models import Event, EventAttendance, EventRegistration, FormResponse


@login_required
def event_list(request):
    now = timezone.now()
    upcoming = Event.objects.filter(end_date__gte=now).order_by("start_date")
    past = Event.objects.filter(end_date__lt=now).order_by("-start_date")
    return render(request, "events/list.html", {"upcoming": upcoming, "past": past})


@capability_required("can_manage_events")
def event_create(request):
    form = EventForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        event = form.save()
        notify_all(
            f"New event: {event.title}",
            f'A new event "{event.title}" has been scheduled at {event.location} on {event.start_date:%b %d, %Y}. Register now!',
            exclude_pk=request.user.pk,
            link=f"/events/{event.pk}/",
        )
        messages.success(request, "Event created.")
        return redirect("events:list")
    return render(request, "form.html", {"form": form, "title": "Create Event"})


@login_required
def event_detail(request, pk):
    event = get_object_or_404(Event, pk=pk)
    registered = EventRegistration.objects.filter(event=event, participant=request.user).exists()
    attended   = EventAttendance.objects.filter(event=event, participant=request.user).exists()
    return render(request, "events/detail.html", {
        "event": event,
        "registered": registered,
        "attended": attended,
        "portal_qr_url": event.get_portal_qr_url(request),
    })


@login_required
def register(request, pk):
    """Portal direct registration has been removed — QR code scan is the only way."""
    messages.info(request, "Please scan the event QR code to register.")
    return redirect("events:detail", pk=pk)


def qr_scan(request, qr_uuid):
    """
    QR-code scan handler — redirects to the pre-filled Google Form.

    The live count increments ONLY when the Apps Script webhook fires
    after the user actually submits the Google Form — not on scan.

    Unauthenticated (phone camera scan):
      → redirect directly to the pre-filled Google Form.

    Authenticated (portal user):
      → record in DB then show confirmation page with form link.
    """
    event = get_object_or_404(Event, qr_uuid=qr_uuid)
    form_url = event.get_registration_url()

    if event.is_past:
        return render(request, "events/qr_closed.html", {"event": event, "reason": "ended"})

    if event.is_full:
        return render(request, "events/qr_closed.html", {"event": event, "reason": "full"})

    if not request.user.is_authenticated:
        # Phone camera scan — go straight to the Google Form immediately
        if form_url:
            return redirect(form_url)
        return render(request, "events/qr_closed.html", {
            "event": event,
            "reason": "no_form",
        })

    # Authenticated portal user — record attendance in DB then show confirmation
    EventRegistration.objects.get_or_create(event=event, participant=request.user)
    _, created = EventAttendance.objects.get_or_create(event=event, participant=request.user)
    if created:
        notify_user(
            request.user,
            f"Attendance recorded: {event.title}",
            f'Your attendance at "{event.title}" has been recorded via QR code. Thank you for joining!',
            link=f"/events/{event.pk}/",
        )
        notify_managers(
            f"Event attendance (QR): {event.title}",
            f'{request.user} scanned in to "{event.title}".',
            link=f"/events/{event.pk}/",
        )

    return render(request, "events/register_redirect.html", {
        "event": event,
        "form_url": form_url,
        "via_qr": True,
    })


@login_required
def registration_count_api(request, pk):
    """
    AJAX endpoint — returns live QR scan / form response count.
    Called by the event detail page every 15 seconds.
    NOTE: no @login_required — this must be publicly accessible so the
    event detail page can poll it even on a phone that is not logged in.
    """
    event = get_object_or_404(Event, pk=pk)
    form_count = event.form_response_count
    return JsonResponse({
        "portal_count":  form_count,
        "form_count":    form_count,
        "capacity":      event.capacity,
        "is_full":       form_count >= event.capacity,
        "is_past":       event.is_past,
        "registration_open": not event.is_past and form_count < event.capacity,
    })


@capability_required("can_manage_events")
def event_delete(request, pk):
    """Admin deletes an event and all its registrations/attendance records."""
    event = get_object_or_404(Event, pk=pk)
    if request.method == "POST":
        title = event.title
        # Delete QR code and banner files from disk
        if event.qr_code:
            try:
                event.qr_code.delete(save=False)
            except Exception:
                pass
        if event.banner:
            try:
                event.banner.delete(save=False)
            except Exception:
                pass
        event.delete()
        messages.success(request, f'Event "{title}" has been deleted.')
        return redirect("events:list")
    # GET — show confirmation page
    return render(request, "events/confirm_delete.html", {"event": event})


@capability_required("can_manage_events")
def regenerate_qr(request, pk):
    """Force-regenerate the QR code for an event."""
    event = get_object_or_404(Event, pk=pk)
    if request.method == "POST":
        event.qr_code = None  # Force regeneration
        event.regenerate_qr(request)
        if event.qr_code:
            Event.objects.filter(pk=pk).update(qr_code=event.qr_code.name)
        messages.success(request, f'QR code for "{event.title}" regenerated.')
    return redirect("events:detail", pk=pk)


@capability_required("can_manage_events")
def report(request, pk, fmt):
    event = get_object_or_404(Event, pk=pk)

    # Primary: Google Form responses stored by the webhook (form_responses)
    form_rows = list(
        event.form_responses
        .order_by("submitted_at")
        .values_list(
            "respondent_name", "respondent_email",
            "respondent_phone", "submitted_at", "raw_data"
        )
    )

    # Fallback: portal registrations (logged-in users who scanned)
    portal_rows = [
        (
            r.participant.get_full_name() or r.participant.username,
            r.participant.email,
            getattr(r.participant, "phone_number", "") or "",
            r.registration_date,
            {},
        )
        for r in event.registrations.select_related("participant").order_by("registration_date")
    ]

    # Merge — deduplicate by email where possible
    seen_emails = set()
    rows = []

    for name, email, phone, when, raw in form_rows:
        key = (email or "").lower().strip()
        if key:
            seen_emails.add(key)
        source = "Google Form"
        # Try to pull extra fields from raw_data
        if not name and raw:
            name = raw.get("name") or raw.get("respondent_name") or ""
        if not email and raw:
            email = raw.get("email") or raw.get("respondent_email") or ""
        if not phone and raw:
            phone = raw.get("phone") or raw.get("respondent_phone") or ""
        rows.append([
            name or "—",
            email or "—",
            phone or "—",
            when.strftime("%d %b %Y, %H:%M") if hasattr(when, "strftime") else str(when),
            source,
        ])

    for name, email, phone, when, _ in portal_rows:
        key = (email or "").lower().strip()
        if key and key in seen_emails:
            continue  # already counted via form response
        rows.append([
            name or "—",
            email or "—",
            phone or "—",
            when.strftime("%d %b %Y, %H:%M") if hasattr(when, "strftime") else str(when),
            "Portal Login",
        ])

    # If no individual records exist yet, show a summary row with the count
    if not rows:
        rows = [["(No individual data stored)", "", "", "", f"{event.form_response_count} total responses"]]

    headers = ["Name", "Email", "Phone", "Registered At", "Source"]
    filename = f"event-{event.pk}-{event.title[:30]}-registrations"

    if fmt == "xlsx":
        return excel_response(filename, headers, rows)
    return pdf_response(filename, f"Registrations: {event.title}", headers, rows)

@csrf_exempt
@require_POST
def form_response_webhook(request, pk):
    """
    Webhook called by Google Apps Script when a Google Form response is submitted.

    The Apps Script POSTs to /events/<pk>/form-response/ with JSON body:
        { "event_id": "<event pk>", "timestamp": "..." }

    The event_id in the body is matched against the pk in the URL — both must
    agree (the URL pk is the authoritative event, the body event_id is verified
    for extra safety).  If you use one Apps Script for all events, post to the
    correct URL for each event or use the general endpoint below.

    Optional shared secret header for security:
        X-Webhook-Secret: <value matching settings.EVENTS_WEBHOOK_SECRET>

    Google Apps Script to add to your Form's linked spreadsheet:
    ──────────────────────────────────────────────────────────────
    function onFormSubmit(e) {
      var eventId = e.namedValues["Event ID"][0];   // field name in your form
      var url     = "https://<your-domain>/events/" + eventId + "/form-response/";
      var secret  = "<your-EVENTS_WEBHOOK_SECRET>";
      UrlFetchApp.fetch(url, {
        method: "post",
        contentType: "application/json",
        headers: { "X-Webhook-Secret": secret },
        payload: JSON.stringify({
          event_id: eventId,
          timestamp: new Date().toISOString()
        }),
        muteHttpExceptions: true
      });
    }
    // Trigger: Edit > Current project's triggers > onFormSubmit > From spreadsheet > On form submit
    ──────────────────────────────────────────────────────────────
    """
    from django.conf import settings

    secret = getattr(settings, "EVENTS_WEBHOOK_SECRET", "")
    if secret and request.headers.get("X-Webhook-Secret") != secret:
        return JsonResponse({"error": "Forbidden"}, status=403)

    event = get_object_or_404(Event, pk=pk)

    try:
        body = json.loads(request.body) if request.body else {}
    except (ValueError, TypeError):
        body = {}

    # Respect capacity — don't count past the limit
    if event.form_response_count >= event.capacity:
        return JsonResponse({
            "ok": False,
            "reason": "capacity_reached",
            "event_id": event.pk,
            "form_response_count": event.form_response_count,
            "capacity": event.capacity,
        })

    # Save individual response record
    FormResponse.objects.create(
        event=event,
        respondent_name=body.get("name", body.get("respondent_name", "")),
        respondent_email=body.get("email", body.get("respondent_email", "")),
        respondent_phone=body.get("phone", body.get("respondent_phone", "")),
        raw_data=body,
    )

    # Atomically increment the counter
    Event.objects.filter(pk=pk).update(
        form_response_count=db_models.F("form_response_count") + 1
    )
    event.refresh_from_db(fields=["form_response_count"])

    # Notify everyone when the event just became full
    if event.form_response_count >= event.capacity:
        notify_all(
            f"Event fully booked: {event.title}",
            f'"{event.title}" has reached maximum capacity ({event.capacity} registrations). '
            f'The QR code has been automatically disabled.',
            link=f"/events/{event.pk}/",
        )

    return JsonResponse({
        "ok": True,
        "event_id": event.pk,
        "form_response_count": event.form_response_count,
        "capacity": event.capacity,
        "is_full": event.form_response_count >= event.capacity,
    })


@csrf_exempt
@require_POST
def form_response_webhook_byid(request):
    """
    Alternative webhook — event ID comes from the JSON body, not the URL.
    Useful when one Apps Script handles all events.

    POST to /events/form-response/  with body:
        { "event_id": "42", "timestamp": "..." }
    """
    from django.conf import settings

    secret = getattr(settings, "EVENTS_WEBHOOK_SECRET", "")
    if secret and request.headers.get("X-Webhook-Secret") != secret:
        return JsonResponse({"error": "Forbidden"}, status=403)

    try:
        body = json.loads(request.body) if request.body else {}
    except (ValueError, TypeError):
        body = {}

    event_id = body.get("event_id") or body.get("eventId")
    if not event_id:
        return JsonResponse({"error": "event_id required in body"}, status=400)

    # Support lookup by numeric PK or by event title
    event = None
    event_id_str = str(event_id).strip()
    if event_id_str.isdigit():
        try:
            event = Event.objects.get(pk=int(event_id_str))
        except Event.DoesNotExist:
            pass
    if event is None:
        # Try by title (case-insensitive) — used when Apps Script sends the event title
        try:
            event = Event.objects.get(title__iexact=event_id_str)
        except Event.DoesNotExist:
            return JsonResponse({"error": f"Event '{event_id_str}' not found"}, status=404)
        except Event.MultipleObjectsReturned:
            # If multiple events share the same title, pick the most recent active one
            event = (
                Event.objects
                .filter(title__iexact=event_id_str, end_date__gte=timezone.now())
                .order_by("start_date")
                .first()
            )
            if not event:
                return JsonResponse({"error": f"Multiple events named '{event_id_str}', none active"}, status=404)

    # Respect capacity — don't count past the limit
    if event.form_response_count >= event.capacity:
        return JsonResponse({
            "ok": False,
            "reason": "capacity_reached",
            "event_id": event.pk,
            "form_response_count": event.form_response_count,
            "capacity": event.capacity,
        })

    # Save individual response record
    FormResponse.objects.create(
        event=event,
        respondent_name=body.get("name", body.get("respondent_name", "")),
        respondent_email=body.get("email", body.get("respondent_email", "")),
        respondent_phone=body.get("phone", body.get("respondent_phone", "")),
        raw_data=body,
    )

    Event.objects.filter(pk=event.pk).update(
        form_response_count=db_models.F("form_response_count") + 1
    )
    event.refresh_from_db(fields=["form_response_count"])

    if event.form_response_count >= event.capacity:
        notify_all(
            f"Event fully booked: {event.title}",
            f'"{event.title}" has reached maximum capacity ({event.capacity} registrations). '
            f'The QR code has been automatically disabled.',
            link=f"/events/{event.pk}/",
        )

    return JsonResponse({
        "ok": True,
        "event_id": event.pk,
        "form_response_count": event.form_response_count,
        "capacity": event.capacity,
        "is_full": event.form_response_count >= event.capacity,
    })
