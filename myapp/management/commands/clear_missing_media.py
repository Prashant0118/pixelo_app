import os
from django.core.management.base import BaseCommand
from myapp.models import Post, Story, Message, Profile

class Command(BaseCommand):
    help = "Clear media fields for files that do not exist in storage."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would be done without saving.")
        parser.add_argument("--model", choices=["post", "story", "message", "profile"], help="Limit to specific model.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        model_filter = options["model"]

        models_to_check = []
        if model_filter:
            if model_filter == "post":
                models_to_check = [(Post, "media")]
            elif model_filter == "story":
                models_to_check = [(Story, "media")]
            elif model_filter == "message":
                models_to_check = [(Message, "media")]
            elif model_filter == "profile":
                models_to_check = [(Profile, "image")]
        else:
            models_to_check = [
                (Post, "media"),
                (Story, "media"),
                (Message, "media"),
                (Profile, "image"),
            ]

        cleared = 0

        for model, field in models_to_check:
            qs = model.objects.exclude(**{f"{field}__isnull": True}).exclude(**{field: ""})
            for obj in qs:
                media_field = getattr(obj, field)
                name = media_field.name
                if not name:
                    continue
                try:
                    exists = media_field.storage.exists(name)
                except Exception:
                    exists = False
                if not exists:
                    if dry_run:
                        self.stdout.write(f"[dry-run] Clear {model.__name__}#{obj.pk} {field}: {name}")
                    else:
                        setattr(obj, field, None)
                        obj.save(update_fields=[field])
                        self.stdout.write(f"Cleared {model.__name__}#{obj.pk} {field}: {name}")
                    cleared += 1

        self.stdout.write(f"Cleared: {cleared}")