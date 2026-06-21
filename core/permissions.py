from functools import wraps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


ADMIN_ROLES = {"admin"}
MANAGER_ROLES = {"admin", "program_manager", "department_head"}


def role_required(*roles):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.is_portal_admin() or request.user.role in roles:
                return view_func(request, *args, **kwargs)
            messages.error(request, "You do not have permission to access that page.")
            return redirect("dashboard:home")
        return wrapper
    return decorator


def capability_required(capability):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            allowed = getattr(request.user, capability, None)
            if request.user.is_portal_admin() or (callable(allowed) and allowed()):
                return view_func(request, *args, **kwargs)
            messages.error(request, "You do not have permission to access that page.")
            return redirect("dashboard:home")
        return wrapper
    return decorator
