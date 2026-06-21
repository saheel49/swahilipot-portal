from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import Department, User
from attendance.models import ProjectSite
from communication.models import DepartmentChannel, Announcement
from events.models import Event


class Command(BaseCommand):
    help = "Create sample Swahilipot Portal data."

    def handle(self, *args, **options):
        departments = ["Programs", "Technology", "Operations", "Communications"]
        dept_objs = {name: Department.objects.get_or_create(name=name, defaults={"description": f"{name} department"})[0] for name in departments}
        ProjectSite.objects.get_or_create(
            name="Swahilipot Hub",
            defaults={"description": "Main Swahilipot project site", "latitude": -4.0435, "longitude": 39.6682, "radius_meters": 100, "active": True},
        )
        for dept in dept_objs.values():
            DepartmentChannel.objects.get_or_create(department=dept, name=f"{dept.name} Updates")
        admin = User.objects.filter(is_superuser=True).first()
        if admin:
            if admin.role != User.Role.ADMIN:
                admin.role = User.Role.ADMIN
                admin.save(update_fields=["role", "is_staff", "is_superuser"])
        else:
            self.stdout.write(self.style.WARNING("No superuser found. Run createsuperuser, then run seed_data again to mark that account as Admin."))
        Announcement.objects.get_or_create(title="Welcome to Swahilipot Portal", defaults={"content": "Use this portal for attendance, tasks, events, communication, and feedback.", "created_by": admin})
        Event.objects.get_or_create(title="Community Innovation Forum", defaults={"description": "Monthly forum for program updates and community learning.", "location": "Swahilipot Hub", "start_date": timezone.now() + timezone.timedelta(days=7), "end_date": timezone.now() + timezone.timedelta(days=7, hours=3), "capacity": 100})
        self.stdout.write(self.style.SUCCESS("Seed data created. The superuser account is used as the Admin account."))
