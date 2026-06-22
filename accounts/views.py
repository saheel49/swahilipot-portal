from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404, render, redirect
from core.permissions import role_required
from .forms import ProfileForm, UserEditForm
from .models import User, Department


@login_required
def profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            from core.audit import audit
            audit(request, "profile_updated",
                  f"{request.user} updated their own profile.",
                  category="users", obj=request.user)
            messages.success(request, "Profile updated.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/profile.html", {"form": form})


@login_required
def user_directory(request):
    """
    Admin: full user directory with edit/deactivate/reset-password actions.
    Program Manager: read-only view — can see all users but cannot modify them.
    """
    if not (request.user.is_portal_admin() or request.user.can_view_users()):
        from django.contrib import messages as _msg
        _msg.error(request, "You do not have permission to access that page.")
        return redirect("dashboard:home")

    roles = [
        ("admin",           "Admin",           "danger"),
        ("program_manager", "Program Manager", "primary"),
        ("department_head", "Department Head", "purple"),
        ("staff",           "Staff",           "success"),
        ("intern",          "Intern",          "warning"),
    ]
    groups = []
    all_users = (
        User.objects
        .select_related("department")
        .order_by("role", "first_name", "username")
    )
    for role_key, role_label, colour in roles:
        members = [u for u in all_users if u.role == role_key]
        groups.append({
            "key":    role_key,
            "label":  role_label,
            "colour": colour,
            "users":  members,
        })

    # Summary counts for the top cards
    total       = all_users.count()
    active      = all_users.filter(is_active=True).count()
    departments = Department.objects.all()

    return render(request, "accounts/user_directory.html", {
        "groups":      groups,
        "total":       total,
        "active":      active,
        "inactive":    total - active,
        "departments": departments,
        # PM gets read-only: hide edit/deactivate/reset-password actions
        "readonly_view": not request.user.is_portal_admin(),
    })


@role_required("admin")
def user_edit(request, pk):
    """Admin edits another user's role / department / status."""
    target = get_object_or_404(User, pk=pk)
    form = UserEditForm(request.POST or None, instance=target)
    if request.method == "POST" and form.is_valid():
        form.save()
        from core.audit import audit
        audit(request, "user_updated",
              f'{request.user} updated user account: {target} (role: {target.role}, dept: {target.department}).',
              category="users", obj=target, severity="warning")
        messages.success(request, f"{target} updated successfully.")
        return redirect("accounts:user_directory")
    return render(request, "accounts/user_edit.html", {"form": form, "target": target})


@role_required("admin")
def user_toggle_active(request, pk):
    """Quick-toggle a user's active status."""
    if request.method == "POST":
        target = get_object_or_404(User, pk=pk)
        if target == request.user:
            messages.error(request, "You cannot deactivate your own account.")
        else:
            target.is_active = not target.is_active
            target.save()
            state = "activated" if target.is_active else "deactivated"
            from core.audit import audit
            audit(request, f"user_{state}",
                  f'{request.user} {state} user account: {target}.',
                  category="users", obj=target, severity="warning")
            messages.success(request, f"{target} has been {state}.")
    return redirect("accounts:user_directory")


@role_required("admin")
def user_reset_password(request, pk):
    """Admin sets a new password for any user — no email required."""
    from django.contrib.auth.forms import SetPasswordForm
    target = get_object_or_404(User, pk=pk)
    form = SetPasswordForm(target, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        from core.notify import notify_user as _notify
        _notify(
            target,
            "Your password has been reset",
            f"An administrator ({request.user.get_full_name() or request.user.username}) "
            f"has reset your portal password. Please sign in with your new password.",
            priority="high",
            link="/accounts/profile/",
        )
        from core.audit import audit
        audit(request, "password_reset",
              f'{request.user} reset password for {target}.',
              category="users", obj=target, severity="warning")
        messages.success(request, f"Password for {target} has been reset.")
        return redirect("accounts:user_directory")
    return render(request, "accounts/reset_password.html", {
        "form": form,
        "target": target,
        "title": f"Reset Password — {target}",
    })


# ── Department management ─────────────────────────────────────────────────

from django import forms as django_forms


class DepartmentForm(django_forms.ModelForm):
    class Meta:
        model  = Department
        fields = ("name", "description")


@login_required
def department_list(request):
    """
    Admin: sees all departments with full management.
    Department Head: sees their own professional dept dashboard.
    """
    if request.user.is_portal_admin():
        departments = Department.objects.prefetch_related("users").all()
        all_unassigned = User.objects.filter(is_active=True, department__isnull=True).order_by("first_name", "username")
        return render(request, "accounts/departments.html", {
            "departments":    departments,
            "all_unassigned": all_unassigned,
        })

    elif request.user.role == "department_head" and request.user.department_id:
        from django.utils import timezone
        from attendance.models import Attendance
        from tasks.access import visible_tasks_for
        from communication.models import DepartmentChannel

        dept = get_object_or_404(Department, pk=request.user.department_id)
        today = timezone.localdate()
        members = dept.users.filter(is_active=True).order_by("first_name", "username")
        all_members = dept.users.all().order_by("first_name", "username")

        # ── Attendance stats for this department ──────────────────────────
        dept_filter = {"user__department_id": dept.pk}
        checked_in_pks = Attendance.objects.filter(
            check_in_time__date=today, **dept_filter
        ).values_list("user_id", flat=True)

        attendance_today  = len(checked_in_pks)
        checked_in_now    = Attendance.objects.filter(status=Attendance.Status.CHECKED_IN, **dept_filter).count()
        currently_out     = members.exclude(pk__in=checked_in_pks).count()
        late_arrivals     = Attendance.objects.filter(
            check_in_time__date=today,
            arrival_status=Attendance.ArrivalStatus.LATE,
            **dept_filter
        ).count()

        # ── Recent attendance records for this dept ───────────────────────
        recent_attendance = Attendance.objects.filter(
            **dept_filter
        ).select_related("user", "project_site").order_by("-check_in_time")[:20]

        # ── Tasks for this dept ────────────────────────────────────────────
        dept_tasks = visible_tasks_for(request.user).order_by("due_date")[:20]
        pending_tasks   = dept_tasks.filter(status="pending").count()
        inprogress_tasks = dept_tasks.filter(status="in_progress").count()
        completed_tasks = dept_tasks.filter(status="completed").count()

        # ── Dept channels ─────────────────────────────────────────────────
        channels = DepartmentChannel.objects.filter(department=dept)

        return render(request, "accounts/department_head.html", {
            "dept":               dept,
            "members":            members,
            "all_members":        all_members,
            "total_members":      all_members.count(),
            "active_members":     members.count(),
            "attendance_today":   attendance_today,
            "checked_in_now":     checked_in_now,
            "currently_out":      currently_out,
            "late_arrivals":      late_arrivals,
            "recent_attendance":  recent_attendance,
            "dept_tasks":         dept_tasks,
            "pending_tasks":      pending_tasks,
            "inprogress_tasks":   inprogress_tasks,
            "completed_tasks":    completed_tasks,
            "channels":           channels,
            "today":              today,
        })

    else:
        messages.error(request, "You are not assigned to a department.")
        return redirect("dashboard:home")


@role_required("admin")
def department_create(request):
    form = DepartmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Department created.")
        return redirect("accounts:departments")
    return render(request, "form.html", {"form": form, "title": "Create Department"})


@role_required("admin")
def department_edit(request, pk):
    dept = get_object_or_404(Department, pk=pk)
    form = DepartmentForm(request.POST or None, instance=dept)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Department updated.")
        return redirect("accounts:departments")
    return render(request, "form.html", {"form": form, "title": f"Edit: {dept.name}"})


@role_required("admin")
def department_assign(request, dept_pk):
    """Bulk-assign selected users to a department."""
    dept = get_object_or_404(Department, pk=dept_pk)
    if request.method == "POST":
        user_pks = request.POST.getlist("user_pks")
        User.objects.filter(pk__in=user_pks).update(department=dept)
        messages.success(request, f"Users assigned to {dept.name}.")
    return redirect("accounts:departments")


@role_required("admin")
def department_remove_user(request, dept_pk, user_pk):
    """Remove a single user from a department."""
    if request.method == "POST":
        target = get_object_or_404(User, pk=user_pk)
        if target.department_id == dept_pk:
            target.department = None
            target.save()
            messages.success(request, f"{target} removed from department.")
    return redirect("accounts:departments")


# ── Add User ─────────────────────────────────────────────────────────────

from .forms import AddUserForm


@role_required("admin")
def user_add(request):
    """Admin creates a new user directly in the portal (no DB/admin needed)."""
    form = AddUserForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.is_active = True
        user.save()
        from core.notify import notify_user
        notify_user(
            user,
            "Welcome to Swahilipot Hub Portal!",
            f"Your portal account has been created by {request.user.get_full_name() or request.user.username}. "
            f"You can now log in with your username: {user.username}. "
            f"Your role is: {user.get_role_display()}.",
            link="/accounts/profile/",
        )
        messages.success(request, f"User '{user.username}' created successfully.")
        from core.audit import audit as _audit
        _audit(request, "user_created",
               f'{request.user} created new user: {user.username} (role: {user.role}).',
               category="users", obj=user, severity="warning")
        return redirect("accounts:user_directory")
    return render(request, "accounts/add_user.html", {"form": form, "title": "Add New User"})


# ── Department Task Assignment ────────────────────────────────────────────

@login_required
def department_assign_task(request, dept_pk):
    """
    Assign a task to the whole department or specific members.
    Admin: any department.
    Department Head: their own department only.
    """
    from tasks.models import Task
    dept = get_object_or_404(Department, pk=dept_pk)

    # Permission check: admin can assign to any dept, dept head only to their own
    if not request.user.is_portal_admin():
        if not request.user.can_manage_tasks():
            messages.error(request, "You do not have permission to assign tasks.")
            return redirect("accounts:departments")
        if request.user.role == "department_head" and request.user.department_id != dept.pk:
            messages.error(request, "You can only assign tasks to your own department.")
            return redirect("dashboard:home")

    if request.method != "POST":
        return redirect("accounts:departments")

    title       = request.POST.get("title", "").strip()
    description = request.POST.get("description", "").strip()
    priority    = request.POST.get("priority", Task.Priority.MEDIUM)
    due_date    = request.POST.get("due_date", "")
    assign_mode = request.POST.get("assign_mode", "whole")

    if not title or not description or not due_date:
        messages.error(request, "Title, description and due date are required.")
        return redirect("accounts:departments")

    valid_priorities = {choice[0] for choice in Task.Priority.choices}
    if priority not in valid_priorities:
        priority = Task.Priority.MEDIUM

    if assign_mode == "whole":
        recipients = dept.users.filter(is_active=True)
    elif assign_mode == "specific":
        member_pks = request.POST.getlist("member_pks")
        if not member_pks:
            messages.error(request, "Please select at least one member.")
            return redirect("accounts:departments")
        recipients = dept.users.filter(pk__in=member_pks, is_active=True)
    else:
        messages.error(request, "Invalid task assignment mode.")
        return redirect("accounts:departments")

    recipients = list(recipients)
    if not recipients:
        messages.error(request, "No active department member matched your selection.")
        return redirect("accounts:departments")

    from core.notify import notify_user as _notify_user
    count = 0
    # Map task priority to notification priority
    _priority_map = {
        "low": "low", "medium": "medium", "high": "high", "critical": "critical"
    }
    notif_priority = _priority_map.get(priority, "medium")
    for member in recipients:
        Task.objects.create(
            title=title,
            description=description,
            assigned_to=member,
            assigned_by=request.user,
            priority=priority,
            due_date=due_date,
            status=Task.Status.PENDING,
        )
        _notify_user(
            member,
            f"New task assigned: {title}",
            f"{request.user.get_full_name() or request.user.username} assigned you a task "
            f"via the {dept.name} department: \"{title}\" — due {due_date}. "
            f"Priority: {priority.title()}.",
            priority=notif_priority,
            link="/tasks/",
        )
        count += 1

    messages.success(request, f"Task assigned to {count} member{'s' if count != 1 else ''} in {dept.name}.")
    return redirect("accounts:departments")



# ── Self-service password recovery (no email) ─────────────────────────────────

def password_recover(request):
    """
    Custom password recovery that needs no email.
    Step 1 (GET / invalid POST): show form asking for username, email, old password.
    Step 2 (valid POST, credentials match): show set-new-password form.
    Step 3 (new password POST): save and redirect to login.

    Security: the user must supply their username, the email on their account,
    AND a password they previously used (authenticate() checks the current hash).
    All three must match before they can set a new password.
    """
    from django.contrib.auth.forms import SetPasswordForm

    # ── Phase 2: set new password after identity verified ────────────────
    if request.method == "POST" and "new_password1" in request.POST:
        # Re-verify the hidden token (username stored in session)
        recover_username = request.session.get("recover_username")
        if not recover_username:
            messages.error(request, "Session expired. Please start again.")
            return redirect("accounts:password_recover")

        try:
            target = User.objects.get(username=recover_username)
        except User.DoesNotExist:
            messages.error(request, "Invalid session. Please start again.")
            return redirect("accounts:password_recover")

        form = SetPasswordForm(target, request.POST)
        if form.is_valid():
            form.save()
            del request.session["recover_username"]
            messages.success(request, "Password changed successfully. Please log in with your new password.")
            return redirect("login")
        return render(request, "registration/password_recover_set.html", {"form": form})

    # ── Phase 1: verify identity ──────────────────────────────────────────
    error = None
    if request.method == "POST":
        username    = request.POST.get("username", "").strip()
        email       = request.POST.get("email", "").strip().lower()
        old_password = request.POST.get("old_password", "")

        # All three fields must be provided
        if not username or not email or not old_password:
            error = "All fields are required."
        else:
            # Check username + old password via Django auth
            user = authenticate(request, username=username, password=old_password)
            if user is None:
                error = "Incorrect username or password."
            elif user.email.lower() != email:
                error = "The email address does not match our records for that account."
            elif not user.is_active:
                error = "This account is inactive. Contact an administrator."
            else:
                # Identity confirmed — store username in session, show new-password form
                request.session["recover_username"] = user.username
                set_form = SetPasswordForm(user)
                return render(request, "registration/password_recover_set.html", {"form": set_form})

    return render(request, "registration/password_recover.html", {"error": error})


# ── Program Manager Dashboard ─────────────────────────────────────────────

@login_required
def program_manager_dashboard(request):
    """
    Professional PM dashboard — org-wide stats with program context.
    Accessible only by Program Managers (and Admin for preview).
    """
    from django.utils import timezone
    from attendance.models import Attendance
    from tasks.access import visible_tasks_for
    from communication.models import DepartmentChannel
    from .models import Program

    if not (request.user.role == "program_manager" or request.user.is_portal_admin()):
        messages.error(request, "Access restricted to Program Managers.")
        return redirect("dashboard:home")

    today = timezone.localdate()

    # ── Programs this PM manages ──────────────────────────────────────────
    if request.user.is_portal_admin():
        programs = Program.objects.filter(is_active=True).prefetch_related("departments")
    else:
        programs = Program.objects.filter(
            manager=request.user, is_active=True
        ).prefetch_related("departments")

    # ── Org-wide attendance stats ──────────────────────────────────────────
    checked_in_pks = Attendance.objects.filter(
        check_in_time__date=today
    ).values_list("user_id", flat=True)
    total_staff     = User.objects.filter(is_active=True).count()
    attendance_today= len(set(checked_in_pks))
    checked_in_now  = Attendance.objects.filter(status=Attendance.Status.CHECKED_IN).count()
    currently_out   = User.objects.filter(is_active=True).exclude(pk__in=checked_in_pks).count()
    late_arrivals   = Attendance.objects.filter(
        check_in_time__date=today,
        arrival_status=Attendance.ArrivalStatus.LATE,
    ).count()

    # ── Recent attendance ─────────────────────────────────────────────────
    recent_attendance = Attendance.objects.select_related(
        "user", "project_site"
    ).order_by("-check_in_time")[:25]

    # ── Tasks ─────────────────────────────────────────────────────────────
    all_tasks = visible_tasks_for(request.user)
    pending_tasks    = all_tasks.filter(status="pending").count()
    inprogress_tasks = all_tasks.filter(status="in_progress").count()
    completed_tasks  = all_tasks.filter(status="completed").count()
    recent_tasks     = all_tasks.order_by("due_date")[:10]

    # ── All departments ───────────────────────────────────────────────────
    departments = Department.objects.prefetch_related("users").all()

    # ── Channels ──────────────────────────────────────────────────────────
    channels = DepartmentChannel.objects.select_related("department").all()

    return render(request, "accounts/program_manager.html", {
        "programs":          programs,
        "total_staff":       total_staff,
        "attendance_today":  attendance_today,
        "checked_in_now":    checked_in_now,
        "currently_out":     currently_out,
        "late_arrivals":     late_arrivals,
        "recent_attendance": recent_attendance,
        "all_tasks":         all_tasks,
        "pending_tasks":     pending_tasks,
        "inprogress_tasks":  inprogress_tasks,
        "completed_tasks":   completed_tasks,
        "recent_tasks":      recent_tasks,
        "departments":       departments,
        "channels":          channels,
        "today":             today,
    })


# ── Programs (Admin CRUD) ─────────────────────────────────────────────────

@role_required("admin")
def program_list(request):
    from .models import Program
    programs = Program.objects.select_related("manager").prefetch_related("departments").order_by("-is_active", "name")
    return render(request, "accounts/programs.html", {"programs": programs})


@role_required("admin")
def program_create(request):
    from .forms import ProgramForm
    form = ProgramForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        prog = form.save()
        from core.audit import audit
        audit(request, "program_created",
              f'{request.user} created program: {prog.name}.',
              category="system", obj=prog)
        messages.success(request, f"Program '{prog.name}' created.")
        return redirect("accounts:programs")
    return render(request, "form.html", {"form": form, "title": "Create Program"})


@role_required("admin")
def program_edit(request, pk):
    from .models import Program
    from .forms import ProgramForm
    prog = get_object_or_404(Program, pk=pk)
    form = ProgramForm(request.POST or None, instance=prog)
    if request.method == "POST" and form.is_valid():
        form.save()
        from core.audit import audit
        audit(request, "program_updated",
              f'{request.user} updated program: {prog.name}.',
              category="system", obj=prog)
        messages.success(request, f"Program '{prog.name}' updated.")
        return redirect("accounts:programs")
    return render(request, "form.html", {"form": form, "title": f"Edit Program: {prog.name}"})


@role_required("admin")
def program_delete(request, pk):
    from .models import Program
    prog = get_object_or_404(Program, pk=pk)
    if request.method == "POST":
        name = prog.name
        prog.delete()
        messages.success(request, f"Program '{name}' deleted.")
    return redirect("accounts:programs")


# ── Custom Roles (Admin CRUD) ─────────────────────────────────────────────

@role_required("admin")
def custom_role_list(request):
    from .models import CustomRole
    roles = CustomRole.objects.prefetch_related("users").all()
    return render(request, "accounts/custom_roles.html", {"roles": roles})


@role_required("admin")
def custom_role_create(request):
    from .forms import CustomRoleForm
    form = CustomRoleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        role = form.save()
        from core.audit import audit
        audit(request, "custom_role_created",
              f'{request.user} created custom role: {role.name}.',
              category="users", obj=role)
        messages.success(request, f"Role '{role.name}' created.")
        return redirect("accounts:custom_roles")
    return render(request, "form.html", {"form": form, "title": "Create Custom Role"})


@role_required("admin")
def custom_role_edit(request, pk):
    from .models import CustomRole
    from .forms import CustomRoleForm
    role = get_object_or_404(CustomRole, pk=pk)
    form = CustomRoleForm(request.POST or None, instance=role)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Role '{role.name}' updated.")
        return redirect("accounts:custom_roles")
    return render(request, "form.html", {"form": form, "title": f"Edit Role: {role.name}"})


@role_required("admin")
def custom_role_delete(request, pk):
    from .models import CustomRole
    role = get_object_or_404(CustomRole, pk=pk)
    if request.method == "POST":
        name = role.name
        role.delete()
        messages.success(request, f"Role '{name}' deleted.")
    return redirect("accounts:custom_roles")
