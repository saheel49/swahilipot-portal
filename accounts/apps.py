from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        """Wire up the user_logged_in signal to track the active session key."""
        from django.contrib.auth.signals import user_logged_in, user_logged_out

        def _store_session_key(sender, request, user, **kwargs):
            """
            Store the new session key on the user so SingleLoginMiddleware can
            detect and expire stale sessions from other devices.
            """
            key = request.session.session_key
            if key:
                type(user).objects.filter(pk=user.pk).update(last_session_key=key)
                user.last_session_key = key
            # Audit log
            from core.audit import audit_login
            audit_login(request, user)

        def _on_logout(sender, request, user, **kwargs):
            if user:
                from core.audit import audit_logout
                audit_logout(request, user)

        user_logged_in.connect(_store_session_key, dispatch_uid="accounts_single_login")
        user_logged_out.connect(_on_logout, dispatch_uid="accounts_audit_logout")
