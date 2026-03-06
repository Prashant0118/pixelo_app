import json
from urllib.parse import urlencode
from urllib.request import urlopen

from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from myapp.models import (
    Comment,
    Follow,
    Like,
    Message,
    Notification,
    Post,
    Profile,
    Reel,
    Story,
    StoryMusic,
    StoryMusicImport,
    StorySeen,
)


@admin.action(description="Mark selected reels as recommended")
def make_recommended(modeladmin, request, queryset):
    reels = queryset.filter(type="reel")
    updated = reels.update(is_recommended=True)
    skipped = queryset.exclude(type="reel").count()
    if skipped:
        messages.warning(request, f"{skipped} non-reel post(s) skipped.")
    messages.success(request, f"{updated} reel(s) marked as recommended.")


@admin.action(description="Remove selected posts from recommended")
def remove_recommended(modeladmin, request, queryset):
    updated = queryset.update(is_recommended=False)
    messages.success(request, f"{updated} post(s) unmarked from recommended.")


def _youtube_music_search(query, max_results=25):
    api_key = getattr(settings, "YOUTUBE_API_KEY", "")
    if not api_key or not query:
        return []
    params = urlencode({
        "part": "snippet",
        "maxResults": min(max(1, int(max_results or 25)), 50),
        "q": query,
        "type": "video",
        "videoCategoryId": "10",
        "key": api_key,
    })
    url = f"https://www.googleapis.com/youtube/v3/search?{params}"
    try:
        with urlopen(url, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []

    tracks = []
    for item in payload.get("items", []):
        video_id = ((item.get("id") or {}).get("videoId") or "").strip()
        snippet = item.get("snippet") or {}
        title = (snippet.get("title") or "").strip()
        channel = (snippet.get("channelTitle") or "").strip()
        if not title:
            continue
        tracks.append({
            "video_id": video_id,
            "title": title[:140],
            "artist": channel[:140],
            "youtube_url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
        })
    return tracks


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "type", "is_recommended", "created_at")
    list_filter = ("type", "is_recommended", "created_at")
    search_fields = ("user__username", "caption")
    actions = [make_recommended, remove_recommended]
    list_editable = ("is_recommended",)

    def save_model(self, request, obj, form, change):
        if obj.type != "reel":
            obj.is_recommended = False
        super().save_model(request, obj, form, change)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "open_user_insights")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("reels_preview",)
    fields = ("user", "image", "bio", "reels_preview")
    change_list_template = "admin/myapp/profile/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "user-insights/",
                self.admin_site.admin_view(self.user_insights_view),
                name="myapp_profile_user_insights",
            )
        ]
        return custom_urls + urls

    def open_user_insights(self, obj):
        username = getattr(obj.user, "username", "")
        url = f"{reverse('admin:myapp_profile_user_insights')}?{urlencode({'username': username})}"
        return format_html('<a href="{}">Open User Insights</a>', url)

    open_user_insights.short_description = "User insights"

    def user_insights_view(self, request):
        username = (request.POST.get("username") or request.GET.get("username") or "").strip()
        user_obj = None
        profile_obj = None
        reels = Post.objects.none()
        details = {}

        if username:
            user_obj = User.objects.filter(username__iexact=username).first()
            if not user_obj:
                messages.error(request, f"User '{username}' not found.")
            else:
                profile_obj = Profile.objects.filter(user=user_obj).first()
                reels = Post.objects.filter(user=user_obj, type="reel").order_by("-created_at")

                if request.method == "POST":
                    reel_id = request.POST.get("reel_id")
                    recommend_flag = request.POST.get("recommend")
                    target_reel = reels.filter(pk=reel_id).first()
                    if target_reel:
                        target_reel.is_recommended = recommend_flag == "1"
                        target_reel.save(update_fields=["is_recommended"])
                        state_text = "recommended" if target_reel.is_recommended else "unrecommended"
                        messages.success(request, f"Reel #{target_reel.pk} marked as {state_text}.")
                    redirect_url = f"{reverse('admin:myapp_profile_user_insights')}?{urlencode({'username': user_obj.username})}"
                    return HttpResponseRedirect(redirect_url)

                details = {
                    "full_name": user_obj.get_full_name() or "-",
                    "email": user_obj.email or "-",
                    "date_joined": user_obj.date_joined,
                    "last_login": user_obj.last_login,
                    "bio": profile_obj.bio if profile_obj else "-",
                    "upi_id": profile_obj.upi_id if profile_obj and profile_obj.upi_id else "-",
                    "interests": ", ".join(profile_obj.interests) if profile_obj and profile_obj.interests else "-",
                    "followers_count": Follow.objects.filter(following=user_obj).count(),
                    "following_count": Follow.objects.filter(follower=user_obj).count(),
                    "posts_count": Post.objects.filter(user=user_obj, type="post").count(),
                    "reels_count": reels.count(),
                    "recommended_reels_count": reels.filter(is_recommended=True).count(),
                }

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "User Insights and Reel Recommendation",
            "username": username,
            "user_obj": user_obj,
            "profile_obj": profile_obj,
            "details": details,
            "reels": reels,
        }
        return TemplateResponse(request, "admin/myapp/user_insights.html", context)

    def reels_preview(self, obj):
        if not obj or not obj.pk:
            return "Save profile first to see reels."

        reels = Post.objects.filter(user=obj.user, type="reel").order_by("-created_at")
        if not reels.exists():
            return "No reels uploaded by this user."

        cards = []
        for reel in reels:
            change_url = reverse("admin:myapp_post_change", args=[reel.pk])
            if reel.media:
                media_html = format_html(
                    "<video controls playsinline preload='metadata' style='width:230px; max-width:100%; background:#000; border-radius:8px;'>"
                    "<source src='{}'>"
                    "</video>",
                    reel.media.url,
                )
            else:
                media_html = format_html("<div style='padding:8px; border:1px solid #ddd;'>No media</div>")

            state_color = "#1b5e20" if reel.is_recommended else "#7f1d1d"
            state_text = "Recommended" if reel.is_recommended else "Not recommended"

            cards.append(
                format_html(
                    "<div style='display:inline-block; width:250px; margin:8px; padding:10px; border:1px solid #ddd; border-radius:10px; vertical-align:top;'>"
                    "{}"
                    "<div style='margin-top:8px; font-size:12px; color:#555;'>Reel ID: {}</div>"
                    "<div style='margin-top:6px; font-weight:600; color:{};'>{}</div>"
                    "<div style='margin-top:8px;'><a href='{}' target='_blank'>Open Reel Settings</a></div>"
                    "</div>",
                    media_html,
                    reel.pk,
                    state_color,
                    state_text,
                    change_url,
                )
            )

        return mark_safe("".join(str(card) for card in cards))

    reels_preview.short_description = "User reels (preview)"


@admin.register(Reel)
class ReelAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "is_recommended", "created_at")
    list_filter = ("is_recommended", "created_at")
    search_fields = ("user__username", "caption")
    actions = [make_recommended, remove_recommended]
    list_editable = ("is_recommended",)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(type="reel")

    def save_model(self, request, obj, form, change):
        obj.type = "reel"
        super().save_model(request, obj, form, change)


admin.site.register(Follow)
admin.site.register(Notification)
admin.site.register(Story)
admin.site.register(StorySeen)
admin.site.register(Message)
admin.site.register(Like)
admin.site.register(Comment)


@admin.register(StoryMusic)
class StoryMusicAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "artist", "section", "is_active", "youtube_url", "created_at")
    list_filter = ("section", "is_active", "created_at")
    search_fields = ("title", "artist", "youtube_video_id", "youtube_url")
    autocomplete_fields = ("created_by",)
    readonly_fields = ("created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.action(description="Import songs from YouTube API for selected query rows")
def run_youtube_import(modeladmin, request, queryset):
    api_key = getattr(settings, "YOUTUBE_API_KEY", "")
    if not api_key:
        messages.error(request, "YOUTUBE_API_KEY not configured in settings/env.")
        return

    total_rows = 0
    imported_count = 0
    active_rows = queryset.filter(is_active=True)

    for row in active_rows:
        tracks = _youtube_music_search(row.query, row.max_results)
        imported_for_row = 0
        for track in tracks:
            video_id = track.get("video_id") or ""
            defaults = {
                "title": track["title"],
                "artist": track["artist"],
                "section": row.section,
                "youtube_url": track["youtube_url"],
                "is_active": True,
            }
            if video_id:
                song_obj, _ = StoryMusic.objects.update_or_create(
                    youtube_video_id=video_id,
                    defaults=defaults,
                )
            else:
                song_obj, _ = StoryMusic.objects.get_or_create(
                    title=track["title"],
                    artist=track["artist"],
                    section=row.section,
                    defaults={"youtube_url": track["youtube_url"], "is_active": True},
                )
            if not song_obj.created_by_id:
                song_obj.created_by = request.user
                song_obj.save(update_fields=["created_by"])
            imported_for_row += 1

        row.last_run_at = timezone.now()
        row.last_imported_count = imported_for_row
        row.save(update_fields=["last_run_at", "last_imported_count"])
        imported_count += imported_for_row
        total_rows += 1

    if total_rows == 0:
        messages.warning(request, "No active import rows selected.")
    else:
        messages.success(request, f"Imported/updated {imported_count} song(s) from {total_rows} import row(s).")


@admin.register(StoryMusicImport)
class StoryMusicImportAdmin(admin.ModelAdmin):
    list_display = ("id", "query", "section", "max_results", "is_active", "last_imported_count", "last_run_at", "created_at")
    list_filter = ("section", "is_active", "created_at")
    search_fields = ("query",)
    actions = [run_youtube_import]


