

# Create your models here.
from django.contrib.auth.models import User
from django.db import models
from urllib.parse import quote
from django.contrib.auth.hashers import make_password, check_password
from django.urls import reverse
from django.conf import settings
import mimetypes
import os


def _media_debug_enabled():
    try:
        return (os.getenv("MEDIA_DEBUG", "") or "").lower() in ("1", "true", "yes", "on")
    except Exception:
        return False


def _log_missing_media(context, name):
    if not _media_debug_enabled():
        return
    try:
        print(f"[media-debug][missing] {context}: {name}")
    except Exception:
        pass


def _cloudinary_video_url(url):
    if not url:
        return ""
    # Always use HTTPS for Cloudinary resources to avoid mixed content warnings
    if "res.cloudinary.com" in url:
        url = url.replace("http://res.cloudinary.com", "https://res.cloudinary.com", 1)
        if "/image/upload/" in url:
            url = url.replace("/image/upload/", "/video/upload/", 1)
        return url
    return url


def _ensure_https_url(url):
    """Ensure all URLs, especially Cloudinary, use HTTPS to avoid mixed content warnings."""
    if not url:
        return ""
    if "res.cloudinary.com" in url:
        url = url.replace("http://res.cloudinary.com", "https://res.cloudinary.com", 1)
    elif url.startswith("http://") and "cloudinary.com" in url:
        url = url.replace("http://", "https://", 1)
    return url


def _cloudinary_public_id_from_name(name):
    raw = (name or "").strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return ""
    if raw.startswith("/"):
        raw = raw[1:]
    return raw


def _cloudinary_url_for(name, resource_type):
    if not name:
        return ""
    try:
        import cloudinary
        from cloudinary.utils import cloudinary_url
    except Exception:
        return ""
    public_id = _cloudinary_public_id_from_name(name)
    if not public_id:
        return ""
    try:
        url, _options = cloudinary_url(
            public_id,
            resource_type=resource_type or "image",
            secure=True,
        )
        return url or ""
    except Exception:
        return ""


def _can_build_cloudinary_urls():
    return bool(
        getattr(settings, "CAN_USE_CLOUDINARY", False)
        or (
            getattr(settings, "CLOUDINARY_CLOUD_NAME", "")
            and getattr(settings, "CLOUDINARY_API_KEY", "")
            and getattr(settings, "CLOUDINARY_API_SECRET", "")
        )
    )


def _extract_embedded_absolute_url(value):
    raw = (value or "").strip()
    if not raw:
        return ""
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw

    idx_http = raw.find("http://")
    idx_https = raw.find("https://")
    candidates = [i for i in (idx_http, idx_https) if i >= 0]
    if not candidates:
        return ""

    start = min(candidates)
    prefix = raw[:start]
    if "media/" in prefix or "/media/" in prefix:
        return raw[start:]
    return ""


def _normalize_media_name(name):
    if not name:
        return ""
    raw = str(name).strip()
    embedded_url = _extract_embedded_absolute_url(raw)
    if embedded_url:
        return embedded_url
    if raw.startswith("/media/"):
        raw = raw[len("/media/"):]
    elif raw.startswith("media/"):
        raw = raw[len("media/"):]
    return raw.lstrip("/")


def _storage_url(field, name):
    embedded_name_url = _extract_embedded_absolute_url(name)
    if embedded_name_url:
        return _ensure_https_url(embedded_name_url)

    try:
        url = field.storage.url(name)
        if not url:
            return ""
        embedded_storage_url = _extract_embedded_absolute_url(url)
        if embedded_storage_url:
            return _ensure_https_url(embedded_storage_url)
        # Some storage backends can return a plain filename; normalize to MEDIA_URL.
        if not (url.startswith("http://") or url.startswith("https://") or url.startswith("/")):
            base = getattr(settings, "MEDIA_URL", "/media/")
            if not base.endswith("/"):
                base = f"{base}/"
            return f"{base}{url}"
        return url
    except Exception:
        return ""


def _looks_like_video_path(path):
    if not path:
        return False
    raw = str(path)
    if "/video/upload/" in raw:
        return True
    # Strip query params for extension checks.
    clean = raw.split("?", 1)[0]
    ext = os.path.splitext(clean)[1].lower()
    return ext in {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv", ".ogv", ".3gp", ".3gpp"}


def _looks_like_video_name(name):
    if not name:
        return False
    raw = os.path.basename(str(name)).lower()
    if os.path.splitext(raw)[1]:
        return False
    # Heuristic for uploads without extensions (e.g. WhatsApp_Video_*).
    return "video" in raw


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to="profile_pics/", default="default.jpg")
    bio = models.TextField(blank=True)
    upi_id = models.CharField(max_length=120, blank=True)
    interests = models.JSONField(default=list, blank=True)

    def __str__(self):
        return self.user.username

    @property
    def avatar_url(self):
        if self.image and self.image.name:
            if self.image.name not in ("default.jpg", "default.png"):
                try:
                    # If image name is already a URL (e.g., Cloudinary), trust it.
                    if str(self.image.name).startswith(("http://", "https://")):
                        return _ensure_https_url(str(self.image.name))

                    # For Cloudinary storage, avoid exists() checks that can fail.
                    storage_name = self.image.storage.__class__.__name__.lower()
                    if "cloudinary" in storage_name:
                        return self.image.url

                    # Avoid storage.exists() because Cloudinary "auto" delivery URLs
                    # can 400 on HEAD requests. Just return the URL if available.
                    name = _normalize_media_name(self.image.name)
                    if name and name != self.image.name:
                        try:
                            storage = self.image.storage
                            if hasattr(storage, "exists"):
                                if storage.exists(name):
                                    return _storage_url(self.image, name)
                                _log_missing_media("profile.image", name)
                                # Missing file: fall back to generated avatar
                                raise FileNotFoundError
                        except Exception:
                            pass
                    storage = self.image.storage
                    if hasattr(storage, "exists"):
                        if storage.exists(self.image.name):
                            return self.image.url
                        _log_missing_media("profile.image", self.image.name)
                        raise FileNotFoundError
                    return self.image.url
                except ValueError:
                    pass
                except FileNotFoundError:
                    pass

        display_name = self.user.get_full_name().strip() or self.user.username or "User"
        initials = "".join([part[0] for part in display_name.split() if part][:2]).upper() or "U"
        svg = (
            "<svg xmlns='http://www.w3.org/2000/svg' width='256' height='256' viewBox='0 0 256 256'>"
            "<rect width='256' height='256' fill='#2f8dff'/>"
            "<text x='50%' y='54%' dominant-baseline='middle' text-anchor='middle' "
            "font-family='Segoe UI,Arial,sans-serif' font-size='96' font-weight='700' fill='white'>"
            f"{initials}</text></svg>"
        )
        return f"data:image/svg+xml;utf8,{quote(svg)}"

class Follow(models.Model):
    follower = models.ForeignKey(User, related_name="following", on_delete=models.CASCADE)
    following = models.ForeignKey(User, related_name="followers", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')


class Notification(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_notifications")
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    post = models.ForeignKey("Post", on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications")
    notification_type = models.CharField(max_length=50)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def target_url(self):
        if not self.post_id:
            return ""
        if self.post.type == "reel":
            return reverse("reels") + f"?reel={self.post_id}"
        return reverse("home") + f"#post-{self.post_id}"


class Story(models.Model):
    AUDIENCE_CHOICES = (
        ("story", "Your Story"),
        ("close_friends", "Close Friends"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to="stories/", blank=True, null=True)
    media = models.FileField(upload_to="stories/media/", blank=True, null=True)
    media_type = models.CharField(max_length=10, default="image")
    filter_name = models.CharField(max_length=40, default="none")
    music = models.FileField(upload_to="stories/music/", blank=True, null=True)
    music_suggestion = models.CharField(max_length=80, blank=True)
    music_source_url = models.URLField(blank=True)
    caption = models.CharField(max_length=220, blank=True)
    is_partnership = models.BooleanField(default=False)
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default="story")
    created_at = models.DateTimeField(auto_now_add=True)
    is_highlight = models.BooleanField(default=False)

    @property
    def is_video(self):
        return self.media_type == "video"

    @property
    def preview_url(self):
        if self.image:
            try:
                name = _normalize_media_name(self.image.name or "")
                if name and name != self.image.name:
                    try:
                        storage = self.image.storage
                        if hasattr(storage, "exists") and storage.exists(name):
                            return _storage_url(self.image, name)
                        _log_missing_media("story.image", name)
                    except Exception:
                        pass
                return self.image.url
            except Exception:
                pass
        if self.media:
            try:
                name = _normalize_media_name(self.media.name or "")
                if name and name != self.media.name:
                    try:
                        storage = self.media.storage
                        if hasattr(storage, "exists") and storage.exists(name):
                            return _storage_url(self.media, name)
                        _log_missing_media("story.media", name)
                    except Exception:
                        pass
                return self.media.url
            except Exception:
                pass
        return ""
    @property
    def media_url(self):
        try:
            if not (self.media and getattr(self.media, "name", "")):
                return ""
            name = _normalize_media_name(self.media.name)
            if name and not self.media.storage.exists(name):
                _log_missing_media("story.media", name)
                return ""
            if getattr(settings, "CAN_USE_CLOUDINARY", False) or _can_build_cloudinary_urls():
                resource_type = "video" if self.media_type == "video" else "image"
                url = _cloudinary_url_for(name, resource_type)
                if url:
                    return url
            if name.startswith("http://") or name.startswith("https://"):
                if self.media_type == "video":
                    return _ensure_https_url(_cloudinary_video_url(name))
                return _ensure_https_url(name)
            url = _storage_url(self.media, name) if name else self.media.url
            if self.media_type == "video":
                return _cloudinary_video_url(url)
            return url
        except Exception:
            return ""
        return ""

    @property
    def media_name(self):
        try:
            name = (self.media.name or "")
        except Exception:
            name = ""
        if not name and self.image:
            try:
                name = (self.image.name or "")
            except Exception:
                name = ""
        return (name or "").lower()
    @property
    def music_url(self):
        try:
            if self.music and getattr(self.music, "name", ""):
                return self.music.url
        except Exception:
            return ""
        return ""


class StoryMusic(models.Model):
    SECTION_CHOICES = (
        ("for_you", "For You"),
        ("new", "New"),
        ("trending", "Trending"),
        ("admin", "Admin Picks"),
    )

    title = models.CharField(max_length=140)
    artist = models.CharField(max_length=140, blank=True)
    section = models.CharField(max_length=20, choices=SECTION_CHOICES, default="admin")
    youtube_video_id = models.CharField(max_length=32, blank=True, db_index=True)
    youtube_url = models.URLField(blank=True)
    audio = models.FileField(upload_to="stories/music/library/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="story_music_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        if self.artist:
            return f"{self.title} - {self.artist}"
        return self.title

    @property
    def display_title(self):
        return str(self)


class StoryMusicImport(models.Model):
    query = models.CharField(max_length=160)
    section = models.CharField(
        max_length=20,
        choices=StoryMusic.SECTION_CHOICES,
        default="trending",
    )
    max_results = models.PositiveSmallIntegerField(default=25)
    is_active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_imported_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.query} ({self.section})"


class StorySeen(models.Model):
    viewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="seen_stories")
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="seen_by")
    seen_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("viewer", "story")

class Message(models.Model):
    MESSAGE_TYPE_CHOICES = (
        ("text", "Text"),
        ("image", "Image"),
        ("video", "Video"),
        ("audio", "Audio"),
    )

    sender = models.ForeignKey(User, related_name="sent_messages", on_delete=models.CASCADE)
    receiver = models.ForeignKey(User, related_name="received_messages", on_delete=models.CASCADE)
    content = models.TextField()
    media = models.FileField(upload_to="chat_media/", null=True, blank=True)
    media_type = models.CharField(max_length=10, choices=MESSAGE_TYPE_CHOICES, default="text")
    timestamp = models.DateTimeField(auto_now_add=True)
    is_seen = models.BooleanField(default=False)

    @property
    def media_url(self):
        try:
            if self.media and getattr(self.media, "name", ""):
                name = (self.media.name or "")
                if not getattr(settings, "CAN_USE_CLOUDINARY", False) and not _can_build_cloudinary_urls():
                    try:
                        if not (name.startswith("http://") or name.startswith("https://")):
                            storage = self.media.storage
                            if hasattr(storage, "exists") and not storage.exists(name):
                                _log_missing_media("message.media", name)
                                return ""
                    except Exception:
                        pass
                if getattr(settings, "CAN_USE_CLOUDINARY", False) or _can_build_cloudinary_urls():
                    resource_type = "video" if self.media_type in ("video", "audio") else "image"
                    url = _cloudinary_url_for(name, resource_type)
                    if url:
                        return url
                if name.startswith("http://") or name.startswith("https://"):
                    if self.media_type in ("video", "audio"):
                        return _ensure_https_url(_cloudinary_video_url(name))
                    return _ensure_https_url(name)
                if not getattr(settings, "CAN_USE_CLOUDINARY", False):
                    try:
                        storage = self.media.storage
                        if hasattr(storage, "exists") and not storage.exists(name):
                            _log_missing_media("message.media", name)
                            return ""
                    except Exception:
                        pass
                url = _storage_url(self.media, name) if name else self.media.url
                if self.media_type in ("video", "audio"):
                    return _cloudinary_video_url(url)
                return url
        except Exception:
            return ""
        return ""

    @property
    def media_name(self):
        try:
            return (self.media.name or "").lower()
        except Exception:
            return ""


class ChatLock(models.Model):
    owner = models.ForeignKey(User, related_name="chat_locks", on_delete=models.CASCADE)
    target = models.ForeignKey(User, related_name="locked_for_users", on_delete=models.CASCADE)
    code_hash = models.CharField(max_length=256)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("owner", "target")

    def set_code(self, raw_code):
        self.code_hash = make_password(raw_code)
        self.is_active = True

    def matches_code(self, raw_code):
        return bool(raw_code) and check_password(raw_code, self.code_hash)


class Post(models.Model):

    TYPE_CHOICES = (
        ('post', 'Post'),
        ('reel', 'Reel'),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="posts"
    )

   

    saved_by = models.ManyToManyField(
        User,
        related_name="saved_posts",
        blank=True
    )

    media = models.FileField(
        upload_to="posts/",
        null=True,
        blank=True
    )

    caption = models.TextField(blank=True)

    duration = models.FloatField(null=True, blank=True)  # Duration in seconds for videos

    type = models.CharField(
        max_length=10,
        choices=TYPE_CHOICES,
        default='post'
    )

    is_recommended = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def media_url(self):
        if not (self.media and getattr(self.media, "name", "")):
            return ""

        raw_name = str(getattr(self.media, "name", "") or "")
        name = _normalize_media_name(raw_name)
        is_video = bool(self.type == "reel" or self.is_video or _looks_like_video_name(name))

        try:
            # If DB already stores an absolute URL, return it directly.
            if name.startswith("http://") or name.startswith("https://"):
                resolved = _ensure_https_url(name)
                return _cloudinary_video_url(resolved) if is_video else resolved

            # For local storage only, hide broken files that no longer exist.
            using_cloudinary = bool(getattr(settings, "CAN_USE_CLOUDINARY", False) or _can_build_cloudinary_urls())
            if not using_cloudinary and name:
                try:
                    storage = self.media.storage
                    if hasattr(storage, "exists") and not storage.exists(name):
                        _log_missing_media("post.media", name)
                        return ""
                except Exception:
                    pass

            # Prefer storage URL resolution first (works for both local and cloud backends).
            resolved = _storage_url(self.media, name) if name else ""
            if not resolved:
                try:
                    resolved = self.media.url
                except Exception:
                    resolved = ""

            # Fallback to generated Cloudinary URL when needed.
            if not resolved and name and using_cloudinary:
                resource_type = "video" if is_video else "image"
                resolved = _cloudinary_url_for(name, resource_type)

            resolved = _ensure_https_url(resolved or "")
            if is_video and resolved:
                return _cloudinary_video_url(resolved)
            return resolved
        except Exception:
            return ""

    @property
    def media_name(self):
        try:
            return (self.media.name or "").lower()
        except Exception:
            return ""

    @property
    def is_video(self):
        name = self.media_name
        if _looks_like_video_name(name):
            return True
        if not name:
            # Fall back to URL heuristics when filename lacks extension.
            try:
                if self.media and getattr(self.media, "url", ""):
                    return _looks_like_video_path(self.media.url)
            except Exception:
                return False
            return False
        ext = os.path.splitext(name)[1].lower()
        if ext in {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv", ".ogv", ".3gp", ".3gpp"}:
            return True
        guessed, _ = mimetypes.guess_type(name)
        if guessed and guessed.startswith("video/"):
            return True
        try:
            if self.media and getattr(self.media, "url", ""):
                return _looks_like_video_path(self.media.url)
        except Exception:
            return False
        return False

    def __str__(self):
        return f"{self.user.username} - {self.type}"

    # 🔥 Like count method
    def total_likes(self):
        return self.likes.count()

    



class Reel(Post):
    class Meta:
        proxy = True
        verbose_name = 'Reel'
        verbose_name_plural = 'Reels'


class ReelWatch(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reel_watches")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="watch_stats")
    views = models.PositiveIntegerField(default=0)
    watch_seconds = models.FloatField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "post")


class Like(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="likes"
    )

    class Meta:
        unique_together = ('user', 'post')
class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="comments"
    )

    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
