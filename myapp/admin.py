import json
from collections import defaultdict
from urllib.parse import urlencode
from urllib.request import urlopen

from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.models import Group, User
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
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
    ReelWatch,
    Story,
    StoryMusic,
    StoryMusicImport,
    StorySeen,
)

from myapp.views import (
    INTEREST_CATEGORY_KEYWORDS,
    _categories_for_text,
    _profile_manual_interests,
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
    list_display = ("user", "open_user_insights", "open_category_insights")
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
            ),
            path(
                "category-insights/",
                self.admin_site.admin_view(self.category_insights_view),
                name="myapp_profile_category_insights",
            ),
        ]
        return custom_urls + urls

    def open_user_insights(self, obj):
        username = getattr(obj.user, "username", "")
        url = f"{reverse('admin:myapp_profile_user_insights')}?{urlencode({'username': username})}"
        return format_html('<a href="{}">Open User Insights</a>', url)

    open_user_insights.short_description = "User insights"

    def open_category_insights(self, obj):
        username = getattr(obj.user, "username", "")
        url = f"{reverse('admin:myapp_profile_category_insights')}?{urlencode({'username': username})}"
        return format_html('<a href="{}">Open Category Insights</a>', url)

    open_category_insights.short_description = "Category insights"

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

    def _category_debug_for_user(self, user_obj):
        scores = {category: 0.0 for category in INTEREST_CATEGORY_KEYWORDS}
        breakdown = {
            category: {"likes": 0.0, "saves": 0.0, "own": 0.0, "watch": 0.0, "manual": 0.0}
            for category in INTEREST_CATEGORY_KEYWORDS
        }
        category_order = {name: index for index, name in enumerate(INTEREST_CATEGORY_KEYWORDS.keys())}

        def add_score(category, key, value):
            if category not in scores:
                return
            scores[category] += value
            breakdown[category][key] += value

        liked_captions = (
            Post.objects.filter(likes__user=user_obj)
            .exclude(caption="")
            .values_list("caption", flat=True)
        )
        saved_captions = (
            user_obj.saved_posts.exclude(caption="")
            .values_list("caption", flat=True)
        )
        own_captions = (
            Post.objects.filter(user=user_obj)
            .exclude(caption="")
            .values_list("caption", flat=True)
        )

        for caption in liked_captions:
            for category in _categories_for_text(caption):
                add_score(category, "likes", 3)
        for caption in saved_captions:
            for category in _categories_for_text(caption):
                add_score(category, "saves", 2)
        for caption in own_captions:
            for category in _categories_for_text(caption):
                add_score(category, "own", 1)

        watch_rows = (
            ReelWatch.objects.filter(user=user_obj)
            .select_related("post")
            .only("watch_seconds", "views", "post__caption")
        )
        for row in watch_rows:
            watch_seconds = float(getattr(row, "watch_seconds", 0) or 0)
            views = int(getattr(row, "views", 0) or 0)
            watch_weight = (min(watch_seconds, 120) * 0.2) + (views * 3)
            if watch_weight <= 0:
                continue
            for category in _categories_for_text(row.post.caption or ""):
                add_score(category, "watch", watch_weight)

        manual_interests = _profile_manual_interests(user_obj)
        manual_boost = len(manual_interests) * 100
        for index, category in enumerate(manual_interests):
            add_score(category, "manual", manual_boost - index)

        ranked = sorted(
            scores.keys(),
            key=lambda category: (-scores[category], category_order.get(category, 0)),
        )
        rows = [
            {
                "category": category,
                "score": round(scores[category], 2),
                "likes": round(breakdown[category]["likes"], 2),
                "saves": round(breakdown[category]["saves"], 2),
                "own": round(breakdown[category]["own"], 2),
                "watch": round(breakdown[category]["watch"], 2),
                "manual": round(breakdown[category]["manual"], 2),
            }
            for category in ranked
        ]

        summary = {
            "liked_posts": Post.objects.filter(likes__user=user_obj).count(),
            "saved_posts": user_obj.saved_posts.count(),
            "own_posts": Post.objects.filter(user=user_obj).count(),
            "watch_rows": watch_rows.count(),
            "manual_interests": ", ".join(manual_interests) if manual_interests else "-",
        }
        return rows, summary

    def category_insights_view(self, request):
        username = (request.GET.get("username") or "").strip()
        user_obj = None
        rows = []
        summary = {}

        if username:
            user_obj = User.objects.filter(username__iexact=username).first()
            if not user_obj:
                messages.error(request, f"User '{username}' not found.")
            else:
                rows, summary = self._category_debug_for_user(user_obj)

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Category Insights",
            "username": username,
            "user_obj": user_obj,
            "rows": rows,
            "summary": summary,
        }
        return TemplateResponse(request, "admin/myapp/category_insights.html", context)

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


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    extra = 0
    fields = ("image", "bio", "upi_id", "interests")

def _safe_unregister(model):
    try:
        admin.site.unregister(model)
    except admin.sites.NotRegistered:
        pass


# Keep only Users visible in admin
_safe_unregister(User)
_safe_unregister(Group)
_safe_unregister(Post)
_safe_unregister(Profile)
_safe_unregister(Reel)
_safe_unregister(Follow)
_safe_unregister(Notification)
_safe_unregister(Story)
_safe_unregister(StorySeen)
_safe_unregister(Message)
_safe_unregister(Like)
_safe_unregister(Comment)
_safe_unregister(StoryMusic)
_safe_unregister(StoryMusicImport)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    inlines = (ProfileInline,)
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    fieldsets = (
        ("Account", {"fields": ("username", "email", "is_active", "is_staff")}),
        ("User Profile", {"fields": ("profile_card",)}),
        ("User Content", {"fields": ("reels_preview", "posts_preview")}),
    )
    readonly_fields = ("profile_card", "reels_preview", "posts_preview")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:user_id>/reels/<int:reel_id>/toggle-recommend/",
                self.admin_site.admin_view(self.toggle_reel_recommend),
                name="myapp_user_toggle_reel_recommend",
            )
        ]
        return custom_urls + urls

    def toggle_reel_recommend(self, request, user_id, reel_id):
        user_obj = User.objects.filter(pk=user_id).first()
        reel = Post.objects.filter(pk=reel_id, user_id=user_id, type="reel").first()
        if not user_obj or not reel:
            messages.error(request, "Reel not found for this user.")
            return HttpResponseRedirect(reverse("admin:auth_user_changelist"))
        reel.is_recommended = not reel.is_recommended
        reel.save(update_fields=["is_recommended"])
        state_text = "recommended" if reel.is_recommended else "not recommended"
        messages.success(request, f"Reel #{reel.pk} marked as {state_text}.")
        return HttpResponseRedirect(reverse("admin:auth_user_change", args=[user_id]))

    def reels_preview(self, obj):
        if not obj or not obj.pk:
            return "Save user first to see reels."

        reels = Post.objects.filter(user=obj, type="reel").order_by("-created_at")
        if not reels.exists():
            return "No reels uploaded by this user."

        cards = []
        for reel in reels:
            toggle_url = reverse("admin:myapp_user_toggle_reel_recommend", args=[obj.pk, reel.pk])
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
                    "<div style='margin-top:8px;'><a href='{}'>Toggle Recommend</a></div>"
                    "</div>",
                    media_html,
                    reel.pk,
                    state_color,
                    state_text,
                    toggle_url,
                )
            )

        return mark_safe("".join(str(card) for card in cards))

    reels_preview.short_description = "User reels (manage)"

    def profile_card(self, obj):
        if not obj:
            return "No user selected."
        profile = Profile.objects.filter(user=obj).first()
        image_url = ""
        if profile and profile.image:
            try:
                image_url = profile.image.url
            except Exception:
                image_url = ""
        if not image_url:
            try:
                image_url = obj.profile.avatar_url
            except Exception:
                image_url = ""
        bio = (profile.bio or "").strip() if profile else ""
        interests = ", ".join(profile.interests) if profile and profile.interests else ""
        followers_count = Follow.objects.filter(following=obj).count()
        following_count = Follow.objects.filter(follower=obj).count()
        posts_count = Post.objects.filter(user=obj, type="post").count()
        reels_count = Post.objects.filter(user=obj, type="reel").count()

        avatar_html = ""
        if image_url:
            avatar_html = format_html(
                "<img src='{}' alt='{}' style='width:88px; height:88px; border-radius:50%; object-fit:cover; border:1px solid #ddd;' />",
                image_url,
                obj.username,
            )
        else:
            avatar_html = format_html(
                "<div style='width:88px; height:88px; border-radius:50%; background:#e5e7eb; display:flex; align-items:center; justify-content:center; font-weight:700; color:#334155;'>"
                "{}</div>",
                (obj.username or "U")[:1].upper(),
            )

        interest_html = ""
        if interests:
            chips = []
            for item in interests.split(","):
                label = item.strip()
                if not label:
                    continue
                chips.append(
                    format_html(
                        "<span style='border:1px solid #314a72; border-radius:999px; background:rgba(16,29,52,0.82); color:#dbe7ff; padding:4px 10px; font-size:12px; display:inline-block; margin:4px 6px 0 0;'>"
                        "{}</span>",
                        label,
                    )
                )
            if chips:
                interest_html = format_html(
                    "<div style='margin-top:8px; display:flex; flex-wrap:wrap;'>{}</div>",
                    mark_safe("".join(str(c) for c in chips)),
                )

        return format_html(
            "<div style='display:flex; gap:16px; align-items:center; padding:14px; border:1px solid #253349; border-radius:14px; background:#0f1b2f; color:#f6f8ff;'>"
            "{}"
            "<div style='min-width:0; flex:1;'>"
            "<div style='font-size:18px; font-weight:700;'>@{}</div>"
            "<div style='color:#a8b6cd; font-size:13px; margin-top:2px;'>{}</div>"
            "<div style='display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap:8px; margin-top:10px;'>"
            "<div style='text-align:center; background:rgba(14,20,34,0.88); border:1px solid #253349; border-radius:12px; padding:8px 6px;'>"
            "<strong style='display:block; font-size:14px;'>{}</strong><span style='color:#a8b6cd; font-size:11px;'>Posts</span></div>"
            "<div style='text-align:center; background:rgba(14,20,34,0.88); border:1px solid #253349; border-radius:12px; padding:8px 6px;'>"
            "<strong style='display:block; font-size:14px;'>{}</strong><span style='color:#a8b6cd; font-size:11px;'>Reels</span></div>"
            "<div style='text-align:center; background:rgba(14,20,34,0.88); border:1px solid #253349; border-radius:12px; padding:8px 6px;'>"
            "<strong style='display:block; font-size:14px;'>{}</strong><span style='color:#a8b6cd; font-size:11px;'>Followers</span></div>"
            "</div>"
            "<div style='display:flex; gap:10px; margin-top:8px; font-size:12px; color:#cbd5e1;'>"
            "<span>Following: <strong style='color:#f6f8ff;'>{}</strong></span>"
            "</div>"
            "{}"
            "</div>"
            "</div>",
            avatar_html,
            obj.username,
            bio or "No bio",
            posts_count,
            reels_count,
            followers_count,
            following_count,
            mark_safe(interest_html),
        )

    profile_card.short_description = "Profile preview"

    def posts_preview(self, obj):
        if not obj or not obj.pk:
            return "Save user first to see posts."

        posts = Post.objects.filter(user=obj, type="post").order_by("-created_at")[:20]
        if not posts.exists():
            return "No posts uploaded by this user."

        items = []
        for post in posts:
            if post.media:
                media_html = format_html(
                    "<div style='width:230px; max-width:100%;'>"
                    "<img src='{}' style='width:100%; border-radius:8px;' />"
                    "</div>",
                    post.media.url,
                )
            else:
                media_html = format_html("<div style='padding:8px; border:1px solid #ddd;'>No media</div>")

            caption = (post.caption or "").strip()[:80] or "No caption"
            items.append(
                format_html(
                    "<div style='display:inline-block; width:250px; margin:8px; padding:10px; border:1px solid #ddd; border-radius:10px; vertical-align:top;'>"
                    "{}"
                    "<div style='margin-top:8px; font-size:12px; color:#555;'>Post ID: {}</div>"
                    "<div style='margin-top:6px; font-size:12px; color:#333;'>{}</div>"
                    "</div>",
                    media_html,
                    post.pk,
                    caption,
                )
            )

        return mark_safe("".join(str(item) for item in items))

    posts_preview.short_description = "User posts"


