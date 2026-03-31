import os

from django.conf import settings
from django.core.files import File
from django.core.files.storage import storages
from django.core.management.base import BaseCommand

from myapp.models import Post


def _is_cloudinary_name(name):
    lowered = (name or "").lower()
    return lowered.startswith("http://") or lowered.startswith("https://") or "res.cloudinary.com" in lowered


def _normalize_local_path(name):
    raw = (name or "").lstrip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return ""

    if raw.startswith("/media/"):
        raw = raw[len("/media/"):]
    elif raw.startswith("media/"):
        raw = raw[len("media/"):]
    return os.path.join(settings.MEDIA_ROOT, raw)


def _normalize_dest_name(name):
    raw = (name or "").lstrip()
    if raw.startswith("/media/"):
        raw = raw[len("/media/"):]
    elif raw.startswith("media/"):
        raw = raw[len("media/"):]
    return raw or ""


class Command(BaseCommand):
    help = "Migrate old local reel media files to configured storage (no Cloudinary)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Scan only, do not upload.")
        parser.add_argument("--limit", type=int, default=0, help="Limit number of posts processed.")
        parser.add_argument("--delete-missing", action="store_true", help="Clear media for missing files.")
        parser.add_argument("--all-posts", action="store_true", help="Process all post types (not just reels).")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]
        delete_missing = options["delete_missing"]
        all_posts = options["all_posts"]

        qs = Post.objects.all()
        if not all_posts:
            qs = qs.filter(type="reel")
        qs = qs.exclude(media="").exclude(media__isnull=True).order_by("id")
        if limit and limit > 0:
            qs = qs[:limit]

        storage = storages["default"]
        migrated = 0
        missing = 0
        skipped = 0

        for post in qs:
            name = getattr(post.media, "name", "") or ""
            if not name:
                skipped += 1
                continue
            if _is_cloudinary_name(name):
                skipped += 1
                continue

            local_path = _normalize_local_path(name)
            if not local_path or not os.path.exists(local_path):
                missing += 1
                if delete_missing and not dry_run:
                    post.media = None
                    post.save(update_fields=["media"])
                continue

            dest_name = _normalize_dest_name(name)
            if not dest_name:
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(f"[dry-run] would upload: post #{post.id} -> {dest_name}")
                continue

            with open(local_path, "rb") as handle:
                saved_name = storage.save(dest_name, File(handle))
            post.media.name = saved_name
            post.save(update_fields=["media"])
            migrated += 1
            self.stdout.write(f"migrated post #{post.id} -> {saved_name}")

        self.stdout.write(
            f"done. migrated={migrated}, missing={missing}, skipped={skipped}"
        )
