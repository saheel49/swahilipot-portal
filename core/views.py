from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.contrib import messages
from django.db.models import Q
from .models import AuditLog


@login_required
def audit_log(request):
    """
    Admin-only comprehensive audit log view.
    Supports filtering by category, severity, user, action keyword, and date range.
    """
    if not request.user.is_portal_admin():
        messages.error(request, "Only admins can access the audit log.")
        return redirect("dashboard:home")

    qs = AuditLog.objects.select_related("user").order_by("-timestamp")

    # ── Filters ──────────────────────────────────────────────────────────
    category  = request.GET.get("category", "").strip()
    severity  = request.GET.get("severity", "").strip()
    user_q    = request.GET.get("user", "").strip()
    action_q  = request.GET.get("action", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to   = request.GET.get("date_to", "").strip()

    if category:
        qs = qs.filter(category=category)
    if severity:
        qs = qs.filter(severity=severity)
    if user_q:
        qs = qs.filter(
            Q(username_snapshot__icontains=user_q) |
            Q(user__first_name__icontains=user_q) |
            Q(user__last_name__icontains=user_q) |
            Q(user__username__icontains=user_q)
        )
    if action_q:
        qs = qs.filter(
            Q(action__icontains=action_q) |
            Q(description__icontains=action_q)
        )
    if date_from:
        qs = qs.filter(timestamp__date__gte=date_from)
    if date_to:
        qs = qs.filter(timestamp__date__lte=date_to)

    # Cap at 500 rows for performance; export for full data
    total_count = qs.count()
    logs = qs[:500]

    return render(request, "core/audit_log.html", {
        "logs":        logs,
        "total_count": total_count,
        "categories":  AuditLog.Category.choices,
        "severities":  AuditLog.Severity.choices,
        # Pass back filter values to repopulate form
        "f_category":  category,
        "f_severity":  severity,
        "f_user":      user_q,
        "f_action":    action_q,
        "f_date_from": date_from,
        "f_date_to":   date_to,
    })


@login_required
def audit_log_export(request):
    """Export filtered audit log as Excel or PDF."""
    if not request.user.is_portal_admin():
        messages.error(request, "Only admins can export the audit log.")
        return redirect("dashboard:home")

    from core.reports import excel_response, pdf_response
    from django.utils import timezone

    fmt = request.GET.get("fmt", "xlsx").strip().lower()

    qs = AuditLog.objects.select_related("user").order_by("-timestamp")

    category  = request.GET.get("category", "").strip()
    severity  = request.GET.get("severity", "").strip()
    user_q    = request.GET.get("user", "").strip()
    action_q  = request.GET.get("action", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to   = request.GET.get("date_to", "").strip()

    if category:  qs = qs.filter(category=category)
    if severity:  qs = qs.filter(severity=severity)
    if user_q:
        qs = qs.filter(
            Q(username_snapshot__icontains=user_q) |
            Q(user__username__icontains=user_q)
        )
    if action_q:
        qs = qs.filter(Q(action__icontains=action_q) | Q(description__icontains=action_q))
    if date_from: qs = qs.filter(timestamp__date__gte=date_from)
    if date_to:   qs = qs.filter(timestamp__date__lte=date_to)

    headers = ["Timestamp", "User", "Category", "Severity", "Action",
               "Description", "Object Type", "Object", "Method", "Path", "IP"]
    rows = []
    for log in qs:
        rows.append([
            timezone.localtime(log.timestamp).strftime("%d %b %Y %H:%M:%S"),
            log.username_snapshot or "—",
            log.get_category_display(),
            log.get_severity_display(),
            log.action,
            log.description,
            f"{log.object_type} #{log.object_id}" if log.object_type else "—",
            log.object_repr or "—",
            log.method or "—",
            log.path or "—",
            log.ip_address or "—",
        ])

    if fmt == "pdf":
        return pdf_response(
            "audit-log-report",
            "System Audit Log",
            headers, rows,
            subtitle=f"Exported by {request.user} on {timezone.localdate()}",
        )
    return excel_response("audit-log-export", headers, rows)
