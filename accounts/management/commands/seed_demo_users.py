from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User

DEMO_USERS = [
    ("demo_manager", "Manager", "Maria", "Santos"),
    ("demo_cashier", "Cashier", "Carlos", "Reyes"),
    ("demo_recorder", "Recorder", "Rosa", "Garcia"),
]


class Command(BaseCommand):
    help = "Create one demo account per role for local testing (DEBUG only)."

    def add_arguments(self, parser):
        parser.add_argument("--password", default="Demo-Pass-12345", help="Password for the demo accounts.")

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Refusing to create demo accounts while DEBUG is False.")
        for username, role, first, last in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}@example.com", "role": role, "first_name": first, "last_name": last},
            )
            user.set_password(options["password"])  # stored hashed, never plain text
            user.role, user.is_active = role, True
            user.save()
            self.stdout.write(f"{'Created' if created else 'Updated'} {role:<8} -> {username}")
        self.stdout.write(self.style.SUCCESS(f"Demo password: {options['password']}"))
