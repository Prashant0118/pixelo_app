import os
import struct
import subprocess
import tempfile
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand

from myapp.models import Post


def _ffprobe_duration_seconds(path):
    try:
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except Exception:
        return None
    if probe.returncode != 0:
        return None
    try:
        return float((probe.stdout or "").strip())
    except (TypeError, ValueError):
        return None


def _mp4_duration_seconds(path):
    try:
        filesize = os.path.getsize(path)
        with open(path, "rb") as handle:
            offset = 0
            while offset < filesize:
                handle.seek(offset)
                header = handle.read(8)
                if len(header) < 8:
                    break
                size, atom_type = struct.unpack(">I4s", header)
                header_size = 8
                if size == 1:
                    ext = handle.read(8)
                    if len(ext) < 8:
                        break
                    size = struct.unpack(">Q", ext)[0]
                    header_size = 16
                elif size == 0:
                    size = filesize - offset
                if size < header_size:
                    break

                if atom_type == b"moov":
                    moov_end = offset + size
                    inner_offset = offset + header_size
                    while inner_offset < moov_end:
                        handle.seek(inner_offset)
                        inner_header = handle.read(8)
                        if len(inner_header) < 8:
                            break
                        inner_size, inner_type = struct.unpack(">I4s", inner_header)
                        inner_header_size = 8
                        if inner_size == 1:
                            ext = handle.read(8)
                            if len(ext) < 8:
                                break
                            inner_size = struct.unpack(">Q", ext)[0]
                            inner_header_size = 16
                        elif inner_size == 0:
                            inner_size = moov_end - inner_offset
                        if inner_size < inner_header_size:
                            break

                        if inner_type == b"mvhd":
                            handle.seek(inner_offset + inner_header_size)
                            version_data = handle.read(1)
                            if not version_data:
                                return None
                            version = struct.unpack(">B", version_data)[0]
                            handle.read(3)  # flags
                            if version == 1:
                                handle.read(8 + 8)
                                timescale = struct.unpack(">I", handle.read(4))[0]
                                duration = struct.unpack(">Q", handle.read(8))[0]
                            else:
                                handle.read(4 + 4)
                                timescale = struct.unpack(">I", handle.read(4))[0]
                                duration = struct.unpack(">I", handle.read(4))[0]
                            if not timescale:
                                return None
                            return duration / timescale

                        inner_offset += inner_size

                offset += size
    except Exception:
        return None
    return None


def _duration_seconds_from_path(path):
    if not path or not os.path.exists(path):
        return None
    duration = _ffprobe_duration_seconds(path)
    if duration is not None:
        return duration
    ext = os.path.splitext(path)[1].lower()
    if ext in {".mp4", ".m4v", ".mov"}:
        return _mp4_duration_seconds(path)
    return None


def _fetch_remote_to_temp(url, max_bytes):
    if not url:
        return None
    try:
        req = Request(url, method="HEAD")
        with urlopen(req, timeout=8) as resp:
            length = resp.headers.get("Content-Length")
        if length and int(length) > max_bytes:
            return None
    except Exception:
        # If HEAD fails, try GET but enforce max_bytes while streaming.
        length = None
    tmp_path = None
    try:
        with urlopen(url, timeout=10) as resp:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(url)[1] or ".mp4")
            tmp_path = tmp.name
            remaining = max_bytes
            while True:
                chunk = resp.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                tmp.write(chunk)
                remaining -= len(chunk)
                if remaining <= 0:
                    break
            tmp.close()
        return tmp_path
    except Exception:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return None


class Command(BaseCommand):
    help = "Fix video posts/reels by duration: <=60s => reel, >60s => post."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply changes (default is dry-run).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limit number of items processed.",
        )
        parser.add_argument(
            "--max-download-mb",
            type=int,
            default=60,
            help="Max remote download size in MB when local file is unavailable.",
        )

    def handle(self, *args, **options):
        apply_changes = options.get("apply", False)
        limit = int(options.get("limit") or 0)

        max_download_mb = int(options.get("max_download_mb") or 60)
        max_download_bytes = max_download_mb * 1024 * 1024

        qs = Post.objects.exclude(media="").exclude(media__isnull=True)
        qs = qs.filter(type__in=("post", "reel")).order_by("id")
        if limit > 0:
            qs = qs[:limit]

        scanned = 0
        updated = 0
        unchanged = 0
        skipped_not_video = 0
        skipped_no_path = 0
        skipped_remote_too_large = 0
        skipped_remote_failed = 0
        skipped_no_duration = 0

        for post in qs:
            scanned += 1
            try:
                is_video = bool(getattr(post, "is_video", False))
            except Exception:
                is_video = False

            if not is_video:
                skipped_not_video += 1
                continue

            try:
                path = post.media.path
            except Exception:
                path = ""

            duration = None
            if path and os.path.exists(path):
                duration = _duration_seconds_from_path(path)
            else:
                skipped_no_path += 1
                try:
                    remote_url = post.media_url or post.media.url
                except Exception:
                    remote_url = ""
                if remote_url:
                    temp_path = _fetch_remote_to_temp(remote_url, max_download_bytes)
                    if temp_path:
                        try:
                            duration = _duration_seconds_from_path(temp_path)
                        finally:
                            try:
                                os.remove(temp_path)
                            except Exception:
                                pass
                    else:
                        skipped_remote_too_large += 1
                else:
                    skipped_remote_failed += 1

            if not duration:
                skipped_no_duration += 1
                continue

            target_type = "reel" if duration <= 60 else "post"
            if post.type == target_type:
                unchanged += 1
                continue

            if apply_changes:
                post.type = target_type
                post.save(update_fields=["type"])
            updated += 1

        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write(f"[{mode}] scanned={scanned} updated={updated} unchanged={unchanged}")
        self.stdout.write(
            f"[{mode}] skipped_not_video={skipped_not_video} skipped_no_path={skipped_no_path} "
            f"skipped_remote_too_large={skipped_remote_too_large} skipped_remote_failed={skipped_remote_failed} "
            f"skipped_no_duration={skipped_no_duration}"
        )
