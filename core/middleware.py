"""
Single-login enforcement middleware.

When a user logs in, their current session key is stored on the User model's
last_session_key field.  On every subsequent request the middleware checks
whether the stored key still matches the active session.  If a different device
has logged in with the same credentials, the older session is considered stale
and is expired immediately.

This allows two project sites to be active at the same time while ensuring each
user account can only be authenticated in one browser session at any time.

Requirements:
  - The User model must have a `last_session_key` CharField (see accounts migration).
  - Add 'core.middleware.SingleLoginMiddleware' to settings.MIDDLEWARE after
    'django.contrib.auth.middleware.AuthenticationMiddleware'.

Exemptions:
  - Attendance check-in and check-out POSTs are exempt from the single-session
    kick so that a phone can complete a check-in even when the user is also
    logged in on a desktop.  The session key is refreshed after each login so
    the enforcement still applies to all other pages.
"""

from django.contrib.auth import logout
from django.contrib import messages

# URL paths that must never trigger a forced logout — these are short-lived
# POST requests where kicking the session mid-flight would silently drop the
# attendance record.
_EXEMPT_PATHS = {
    "/attendance/check-in/",
    "/attendance/check-out/",
    "/attendance/geofence-ping/",
    "/attendance/location-status/",
}


class SingleLoginMiddleware:
    """Expire any earlier session when the same user logs in elsewhere.

    Attendance write endpoints are exempted so that a phone check-in is not
    silently discarded when the same user is simultaneously logged in on a
    desktop browser.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip enforcement for attendance write operations so a phone check-in
        # is never silently dropped mid-flight.
        if request.path in _EXEMPT_PATHS:
            return self.get_response(request)

        if (
            request.user.is_authenticated
            and hasattr(request.user, "last_session_key")
            and request.user.last_session_key
            and request.session.session_key
            and request.user.last_session_key != request.session.session_key
        ):
            # A newer session exists for this user — invalidate the current one
            logout(request)
            messages.warning(
                request,
                "You have been signed out because your account was logged in from another device or browser.",
            )
            from django.shortcuts import redirect
            return redirect("login")

        response = self.get_response(request)
        return response
