"""
Central notification dispatcher.

Priority levels:
  "low"      — informational (soft click / ping)
  "medium"   — routine alert (gentle chime)
  "high"     — important action needed (attention bell)
  "critical" — urgent / safety alert (loud alarm)

Call notify_all(title, message) to send to every active user.
Call notify_managers(title, message) to send to admins + program managers.
Call notify_user(user, title, message) for a single user.
All functions accept an optional ``priority`` keyword argument.
"""

from communication.models import Notification
from accounts.models import User

# ── priority shortcuts ──────────────────────────────────────────────────────
LOW      = Notification.Priority.LOW
MEDIUM   = Notification.Priority.MEDIUM
HIGH     = Notification.Priority.HIGH
CRITICAL = Notification.Priority.CRITICAL


def notify_user(user, title, message, priority=LOW, link=""):
    Notification.objects.create(user=user, title=title, message=message, priority=priority, link=link)


def notify_all(title, message, exclude_pk=None, priority=LOW, link=""):
    """Send to every active user (optionally excluding one, e.g. the actor)."""
    qs = User.objects.filter(is_active=True)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    bulk = [Notification(user=u, title=title, message=message, priority=priority, link=link) for u in qs]
    Notification.objects.bulk_create(bulk, ignore_conflicts=True)


def notify_managers(title, message, exclude_pk=None, priority=LOW, link=""):
    """Send to admins and program managers only."""
    qs = User.objects.filter(
        is_active=True,
        role__in=["admin", "program_manager"]
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    bulk = [Notification(user=u, title=title, message=message, priority=priority, link=link) for u in qs]
    Notification.objects.bulk_create(bulk, ignore_conflicts=True)


def notify_dept(department, title, message, exclude_pk=None, priority=LOW, link=""):
    """Send to everyone in a specific department."""
    qs = User.objects.filter(is_active=True, department=department)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    bulk = [Notification(user=u, title=title, message=message, priority=priority, link=link) for u in qs]
    Notification.objects.bulk_create(bulk, ignore_conflicts=True)
