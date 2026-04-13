import os
import sys
import shutil

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
import django

django.setup()

from django.conf import settings
from myapp.models import Post, Story, Message, Profile


def _is_remote(name: str) -> bool:
    lowered = (name or "").lower()
    return lowered.startswith(("http://", "https://")) or "res.cloudinary.com" in lowered


def _normalize_name(name: str) -> str:
    raw = (name or "").strip()
    if raw.startswith("/media/"):
        return raw[len("/media/"):]
    if raw.startswith("media/"):
        return raw[len("media/"):]
    # Collapse duplicated folder prefixes (posts/posts -> posts, etc.)
    for prefix in (
        "posts/",
        "stories/",
        "stories/media/",
        "stories/music/",
        "profile_pics/",
        "chat_media/",
    ):
        double_prefix = f"{prefix}{prefix}"
        if raw.startswith(double_prefix):
            return raw[len(prefix):]
    return raw


def _safe_move(src: str, dst: str) -> bool:
    if not os.path.exists(src):
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.move(src, dst)
    return True


def _process_field(obj, field_name: str, dry_run: bool) -> bool:
    media_field = getattr(obj, field_name, None)
    if not media_field:
        return False
    name = (media_field.name or "").strip()
    if not name or _is_remote(name):
        return False

    normalized = _normalize_name(name)
    if normalized == name:
        return False

    src_path = os.path.join(settings.MEDIA_ROOT, name.lstrip("/"))
    dst_path = os.path.join(settings.MEDIA_ROOT, normalized.lstrip("/"))
    src_exists = os.path.exists(src_path)
    dst_exists = os.path.exists(dst_path)

    if dry_run:
        print(
            f"[dry-run] {obj.__class__.__name__}#{obj.pk} {field_name}: {name!r} -> {normalized!r} "
            f"(src_exists={src_exists}, dst_exists={dst_exists})"
        )
        return True

    moved = False
    if src_exists and not dst_exists:
        moved = _safe_move(src_path, dst_path)
    elif dst_exists:
        moved = True

    if moved:
        setattr(obj, field_name, normalized)
        obj.save(update_fields=[field_name])
        print(f"Updated {obj.__class__.__name__}#{obj.pk} {field_name}: {name!r} -> {normalized!r}")
        return True

    print(
        f"Skipped {obj.__class__.__name__}#{obj.pk} {field_name}: {name!r} "
        f"(missing src and dst)"
    )
    return False


def main(dry_run: bool = False):
    updated = 0
    for model, field in [
        (Post, "media"),
        (Story, "media"),
        (Story, "image"),
        (Message, "media"),
        (Profile, "image"),
    ]:
        qs = model.objects.exclude(**{f"{field}__isnull": True}).exclude(**{field: ""})
        for obj in qs:
            if _process_field(obj, field, dry_run=dry_run):
                updated += 1
    print(f"Done. Updated: {updated}")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    main(dry_run=dry)
