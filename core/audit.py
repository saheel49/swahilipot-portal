"""
core/audit.py — helpers for writing AuditLog entries.

Usage anywhere in the codebase:

    from core.audit import audit

    audit(
        request,
        action="task_created",
        description=f'Task "{task.title}" assigned to {task.assigned_to}.',
        category="tasks",
        obj=task,           # optional — records object_type / id / repr
        severity="info",    # optional, default "info"
    )
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.http import HttpRequest


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def audit(
    request,
    action: str,
    description: str = "",
    category: str = "other",
    obj=None,
    severity: str = "info",
) -> None:
    """
    Write an AuditLog entry.  Safe to call from any view — never raises.

    Parameters
    ----------
    request     : HttpRequest (or None for background tasks)
    action      : short machine-readable identifier, e.g. "check_in"
    description : human-readable detail string
    category    : one of AuditLog.Category values
    obj         : optional model instance — records type/id/repr
    severity    : "info" | "warning" | "critical"
    """
    try:
        from core.models import AuditLog

        user = getattr(request, "user", None)
        if user is not None and not user.is_authenticated:
            user = None

        entry = AuditLog(
            user=user,
            action=action,
            description=description,
            category=category,
            severity=severity,
            method=getattr(request, "method", ""),
            path=getattr(request, "path", ""),
            ip_address=_client_ip(request) if request else None,
        )

        if obj is not None:
            entry.object_type = type(obj).__name__
            entry.object_id   = str(getattr(obj, "pk", ""))
            entry.object_repr = str(obj)[:200]

        entry.save()
    except Exception:
        # Audit logging must never break the main request
        pass


def audit_login(request, user) -> None:
    """Convenience wrapper for login events."""
    try:
        from core.models import AuditLog
        AuditLog.objects.create(
            user=user,
            username_snapshot=user.get_full_name() or user.username,
            action="login",
            description=f"{user.get_full_name() or user.username} logged in.",
            category=AuditLog.Category.AUTH,
            severity=AuditLog.Severity.INFO,
            method="POST",
            path="/login/",
            ip_address=_client_ip(request),
        )
    except Exception:
        pass


def audit_logout(request, user) -> None:
    """Convenience wrapper for logout events."""
    try:
        from core.models import AuditLog
        name = user.get_full_name() or user.username if user else "unknown"
        AuditLog.objects.create(
            user=user,
            username_snapshot=name,
            action="logout",
            description=f"{name} logged out.",
            category=AuditLog.Category.AUTH,
            severity=AuditLog.Severity.INFO,
            method="POST",
            path="/logout/",
            ip_address=_client_ip(request),
        )
    except Exception:
        pass
