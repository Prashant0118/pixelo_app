import os

import cloudinary.uploader
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
                    # Fallback: try Cloudinary destroy for both image/video.
                    if _looks_cloudinary(name):
                        public_id = name
                        # Trim to public_id if full URL
                        if "res.cloudinary.com" in public_id:
                            parts = public_id.split("/upload/", 1)
                            if len(parts) == 2:
                                public_id = parts[1].split(".", 1)[0]
                        for rtype in ("image", "video", "raw"):
                            try:
                                cloudinary.uploader.destroy(public_id, invalidate=True, resource_type=rtype)
                            except Exception:
                                pass
                        deleted_files += 1
            reel.delete()

        self.stdout.write(f"done. deleted reels={total}, media_deleted={deleted_files}")
