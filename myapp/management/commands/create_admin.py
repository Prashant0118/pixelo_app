from __future__ import annotations

import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Create or update a superuser from ADMIN_* environment variables."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            dest="username",
            default=os.getenv("ADMIN_USERNAME"),
            help="Username for the admin user (env: ADMIN_USERNAME)",
        )
        parser.add_argument(
            "--email",
            dest="email",
            default=os.getenv("ADMIN_EMAIL"),
            help="Email for the admin user (env: ADMIN_EMAIL)",
        )
        parser.add_argument(
            "--password",
            dest="password",
            default=os.getenv("ADMIN_PASSWORD"),
            help="Password for the admin user (env: ADMIN_PASSWORD)",
        )

    def handle(self, *args, **options):
        username = options.get("username") or "admin"
        email = options.get("email") or "admin@example.com"
        password = options.get("password")

        if not password:
            self.stdout.write(self.style.ERROR("ADMIN_PASSWORD not provided; aborting."))
            return

        User = get_user_model()
        user = User.objects.filter(username=username).first()
        if user:
            user.set_password(password)
            user.email = email
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Updated existing user '{username}'."))
        else:
            User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f"Created superuser '{username}'."))
