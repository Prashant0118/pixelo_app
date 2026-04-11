import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from django.core.management.base import BaseCommand
from myapp.models import Post, Story, Message, Profile


DEFAULT_NAMES = {"default.jpg", "default.png"}


def _looks_remote(name):
    lowered = (name or "").lower()
    return lowered.startswith("http://") or lowered.startswith("https://") or "res.cloudinary.com" in lowered


def _remote_url_exists(url):
    if not url or not url.startswith(("http://", "https://")):
        return True
    try:
        request = Request(url, method="HEAD")
        with urlopen(request, timeout=6) as response:
            status = getattr(response, "status", 200)
            return 200 <= status < 400
    except HTTPError as error:
        return 200 <= getattr(error, "code", 0) < 400
    except URLError:
        return False
    except Exception:
        return False


def _looks_invalid_stored_name(name):
    raw = (name or "").strip()
    if not raw:
        return True
    lowered = raw.lower()
    if lowered in DEFAULT_NAMES:
        return False
    if raw.startswith(("http://", "https://", "/media/", "media/")):
        return False
    # Valid uploads in this project are folder-based names (posts/, stories/, etc).
    if "/" not in raw:
        return True
    return False

class Command(BaseCommand):
    help = "Clear media fields for files that do not exist in storage."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would be done without saving.")
        parser.add_argument("--model", choices=["post", "story", "message", "profile"], help="Limit to specific model.")
        parser.add_argument("--check-remote", action="store_true", help="Also test remote URLs with a HEAD request.")
        parser.add_argument("--clear-invalid-names", action="store_true", help="Clear malformed stored names (e.g. bare filename/public_id).")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        model_filter = options["model"]
        check_remote = options["check_remote"]
        clear_invalid_names = options["clear_invalid_names"]

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
                if os.path.basename(name) in DEFAULT_NAMES:
                    continue

                url_attr = {
                    Post: "media_url",
                    Story: "media_url",
                    Message: "media_url",
                    Profile: "avatar_url",
                }.get(model, "")

                rendered_url = ""
                if url_attr:
                    try:
                        rendered_url = getattr(obj, url_attr, "") or ""
                    except Exception:
                        rendered_url = ""

                exists = True

                if clear_invalid_names and _looks_invalid_stored_name(name):
                    exists = False
                elif check_remote and rendered_url.startswith(("http://", "https://")):
                    exists = _remote_url_exists(rendered_url)
                elif _looks_remote(name):
                    if not check_remote:
                        continue
                    try:
                        url = media_field.url
                    except Exception:
                        url = name
                    exists = _remote_url_exists(url)
                else:
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