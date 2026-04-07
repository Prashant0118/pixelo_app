import os
from django.core.management.base import BaseCommand
from django.conf import settings
from myapp.models import Post, Story, Message, Profile

class Command(BaseCommand):
    help = "Upload existing local media files to Cloudinary and update the database."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would be done without uploading.")
        parser.add_argument("--limit", type=int, default=0, help="Limit number of files processed.")
        parser.add_argument("--model", choices=["post", "story", "message", "profile"], help="Limit to specific model.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]
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

        processed = 0
        uploaded = 0

        for model, field in models_to_check:
            qs = model.objects.exclude(**{f"{field}__isnull": True}).exclude(**{field: ""})
            if limit and processed >= limit:
                break
            for obj in qs:
                if limit and processed >= limit:
                    break
                media_field = getattr(obj, field)
                name = media_field.name
                if not name:
                    continue

                # Check if it's already a Cloudinary URL
                if "res.cloudinary.com" in name:
                    continue

                # Check if local file exists
                local_path = os.path.join(settings.MEDIA_ROOT, name)
                if not os.path.exists(local_path):
                    self.stdout.write(f"Local file missing: {local_path}")
                    continue

                processed += 1
                if dry_run:
                    self.stdout.write(f"[dry-run] Would upload {model.__name__}#{obj.pk}: {name}")
                    continue

                try:
                    # Open the file and save it, which will upload to Cloudinary
                    with open(local_path, 'rb') as f:
                        media_field.save(name, File(f), save=True)
                    uploaded += 1
                    self.stdout.write(f"Uploaded {model.__name__}#{obj.pk}: {name}")
                except Exception as e:
                    self.stdout.write(f"Error uploading {model.__name__}#{obj.pk}: {e}")

        self.stdout.write(f"Processed: {processed}, Uploaded: {uploaded}")