import os

from django.core.management.base import BaseCommand

from myapp.models import Post, Profile, Story, Message


def _normalize_name(name):
    if not name:
        return ""
    raw = str(name).strip()
    if raw.startswith("/media/"):
        raw = raw[len("/media/"):]
    elif raw.startswith("media/"):
        raw = raw[len("media/"):]
    # Collapse duplicate posts/posts
    if raw.startswith("posts/posts/"):
        raw = raw[len("posts/"):]
    return raw.lstrip("/")


class Command(BaseCommand):
    help = "Normalize media field names (strip leading media/ and duplicate posts/)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show changes without saving.")
        parser.add_argument("--limit", type=int, default=0, help="Limit total records processed.")

    def _maybe_update(self, obj, field, dry_run):
        current = getattr(obj, field).name if getattr(obj, field) else ""
        if not current:
            return False
        normalized = _normalize_name(current)
        if not normalized or normalized == current:
            return False
        if dry_run:
            self.stdout.write(f"[dry-run] {obj.__class__.__name__}#{obj.pk} {field}: {current} -> {normalized}")
            return True
        setattr(obj, field, normalized)
        obj.save(update_fields=[field])
        self.stdout.write(f"updated {obj.__class__.__name__}#{obj.pk} {field}")
        return True

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]
        updated = 0
        scanned = 0

        def maybe_stop():
            return limit and scanned >= limit

        for profile in Profile.objects.exclude(image="").exclude(image__isnull=True).order_by("id"):
            if maybe_stop():
                break
            scanned += 1
            if self._maybe_update(profile, "image", dry_run):
                updated += 1

        for post in Post.objects.exclude(media="").exclude(media__isnull=True).order_by("id"):
            if maybe_stop():
                break
            scanned += 1
            if self._maybe_update(post, "media", dry_run):
                updated += 1

        for story in Story.objects.all().order_by("id"):
            if maybe_stop():
                break
            scanned += 1
            if story.image and self._maybe_update(story, "image", dry_run):
                updated += 1
            if story.media and self._maybe_update(story, "media", dry_run):
                updated += 1

        for msg in Message.objects.exclude(media="").exclude(media__isnull=True).order_by("id"):
            if maybe_stop():
                break
            scanned += 1
            if self._maybe_update(msg, "media", dry_run):
                updated += 1

        self.stdout.write(f"done. scanned={scanned}, updated={updated}")
