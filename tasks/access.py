from django.db.models import Q
from .models import Task


def visible_tasks_for(user):
    """
    Role-based task visibility:
    - Admin / superuser : all tasks
    - Program Manager   : tasks they created OR are assigned to them
    - Department Head   : tasks in their department + tasks they created or are assigned to
    - Staff / Intern    : only tasks assigned to them
    """
    qs = Task.objects.select_related("assigned_to", "assigned_by", "assigned_to__department")

    if user.is_portal_admin():
        return qs

    if user.role == user.Role.PROGRAM_MANAGER:
        return qs.filter(Q(assigned_by=user) | Q(assigned_to=user))

    if user.role == user.Role.DEPARTMENT_HEAD and user.department_id:
        return qs.filter(
            Q(assigned_to__department=user.department) |
            Q(assigned_by=user) |
            Q(assigned_to=user)
        )

    # Staff / Intern — only assigned tasks
    return qs.filter(assigned_to=user)


def user_can_access_task(user, task):
    """
    Matches the same rules as visible_tasks_for so detail/update
    access is consistent with what appears in the list.
    """
    if user.is_portal_admin():
        return True

    # Directly involved (assigned to or created by)
    if task.assigned_to_id == user.pk or task.assigned_by_id == user.pk:
        return True

    # Department Head can see department tasks
    if user.role == user.Role.DEPARTMENT_HEAD and user.department_id:
        return task.assigned_to.department_id == user.department_id

    return False
