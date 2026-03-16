

# Create your models here.
from django.contrib.auth.models import User
from django.db import models
from urllib.parse import quote
from django.contrib.auth.hashers import make_password, check_password
from django.urls import reverse
from django.conf import settings


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
            if self.image.name in ("default.jpg", "default.png"):
                return f"{settings.STATIC_URL}images/default.png"
            try:
                # Avoid storage.exists() because Cloudinary "auto" delivery URLs
                # can 400 on HEAD requests. Just return the URL if available.
                return self.image.url
            except ValueError:
                pass
        return f"{settings.STATIC_URL}images/default.png"

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
            return self.image.url
        if self.media:
            return self.media.url
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

    type = models.CharField(
        max_length=10,
        choices=TYPE_CHOICES,
        default='post'
    )

    is_recommended = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.type}"

    # 🔥 Like count method
    def total_likes(self):
        return self.likes.count()

    def __str__(self):
        return f"{self.user.username} - {self.type}"
    



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
