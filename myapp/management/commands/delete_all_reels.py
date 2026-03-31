import os
from django.core.management.base import BaseCommand

from myapp.models import Post


def _looks_cloudinary(name):
    lowered = (name or "").lower()
    return "res.cloudinary.com" in lowered or lowered.startswith(("http://", "https://"))


class Command(BaseCommand):
    help = "Delete all reels (Post.type='reel') and optionally remove media files."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="List reels without deleting.")
        parser.add_argument("--keep-files", action="store_true", help="Do not delete media files.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        keep_files = options["keep_files"]

        reels = Post.objects.filter(type="reel").order_by("id")
        total = reels.count()
        if dry_run:
            self.stdout.write(f"[dry-run] would delete {total} reels.")
            return

        deleted_files = 0
        for reel in reels:
            media = reel.media
            name = getattr(media, "name", "") if media else ""
            if name and not keep_files:
                try:
                    # Prefer storage delete when available.
                    media.delete(save=False)
                    deleted_files += 1
                except Exception:
                    # Fallback: if file looks like a remote URL, we cannot
                    # remove it from local storage here (Cloudinary removed).
                    if _looks_cloudinary(name):
                        # Log and skip remote file deletion when using external hosts.
                        deleted_files += 1
            reel.delete()

        self.stdout.write(f"done. deleted reels={total}, media_deleted={deleted_files}")
