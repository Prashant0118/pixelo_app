import json
import mimetypes
import os
import struct
import subprocess
import tempfile
import time
from collections import defaultdict
from urllib.parse import urlencode, quote
from urllib.request import urlopen

from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Case, When, Value, IntegerField, Count
from django.core.files.base import File, ContentFile
from django.core.files.storage import default_storage
from django.conf import settings
from django.urls import reverse

from myapp.models import Post, Profile, Follow, Notification, Message, Like, Comment, Story, StorySeen, ChatLock, ReelWatch, StoryMusic
from myapp.forms import UserUpdateForm, ProfileUpdateForm, UpiIdUpdateForm


# Create your views here.
STORY_FILTER_LABELS = [
    ("none", "Normal"),
    ("grayscale", "Grayscale"),
    ("sepia", "Sepia"),
    ("vivid", "Vivid"),
    ("cool", "Cool Blue"),
    ("warm", "Warm Tone"),
    ("contrast", "High Contrast"),
    ("vintage", "Vintage"),
    ("blur", "Soft Blur"),
    ("bright", "Bright"),
    ("dramatic", "Dramatic"),
    ("mono", "Mono Dark"),
]
STORY_FILTER_CHOICES = {code for code, _ in STORY_FILTER_LABELS}
STORY_FILTER_CSS = {
    "none": "none",
    "grayscale": "grayscale(1)",
    "sepia": "sepia(0.9)",
    "vivid": "saturate(1.7) contrast(1.15)",
    "cool": "saturate(1.05) hue-rotate(320deg)",
    "warm": "sepia(0.25) saturate(1.2) brightness(1.05)",
    "contrast": "contrast(1.45)",
    "vintage": "sepia(0.45) contrast(1.05) brightness(0.95)",
    "blur": "blur(1.1px)",
    "bright": "brightness(1.18) saturate(1.08)",
    "dramatic": "contrast(1.35) saturate(1.3) brightness(0.88)",
    "mono": "grayscale(0.95) contrast(1.25) brightness(0.85)",
}
STORY_MUSIC_SUGGESTIONS = {
    "for_you": ["Night Drive", "Sajni Re", "Moonlight Beat", "Lo-Fi Coffee", "Dream Pop"],
    "new": ["New Drop 1", "Weekend Mix", "Fresh Vibes", "Indie Wave", "Neon Pop"],
    "trending": ["Trending Audio 1", "Trending Audio 2", "Viral Beat", "Club Hook", "Top Reels Mix"],
    "saved": [],
    "original_audio": ["Original Audio", "Voice Clip", "Ambient Cut"],
}
YOUTUBE_SECTION_QUERY = {
    "for_you": "best songs for instagram stories",
    "new": "new songs",
    "trending": "trending songs",
}


def _media_debug_enabled():
    return (os.getenv("MEDIA_DEBUG", "") or "").lower() in ("1", "true", "yes", "on")

INTEREST_CATEGORY_KEYWORDS = {
    "Trending": ["trending", "viral", "popular", "for you", "fyp"],
    "Learning": ["learning", "learn", "study", "education", "tips"],
    "School Studies": [
        "school", "class 10", "class 12", "cbse", "icse", "board exam",
        "homework", "assignment", "worksheet", "school notes", "school study"
    ],
    "College Studies": [
        "college", "university", "semester", "sem", "credits", "cgpa", "sgpa",
        "backlog", "lab", "college notes", "university notes", "thesis"
    ],
    "Campus Life": [
        "campus", "hostel", "mess", "college fest", "society", "club", "event"
    ],
    "Placements": [
        "placement", "placements", "campus placement", "on-campus", "off-campus",
        "placement drive", "company visit"
    ],
    "Internships": ["internship", "intern", "stipend", "trainee"],
    "Coding": ["coding", "code", "programming", "developer", "python", "javascript"],
    "Mathematics": ["math", "mathematics", "algebra", "geometry", "calculus"],
    "Data Science": ["data science", "machine learning", "ai", "analytics", "dataset"],
    "Competitive Exams": ["exam", "upsc", "ssc", "jee", "neet", "preparation"],
    "English Speaking": ["english speaking", "spoken english", "vocabulary", "grammar"],
    "Notes Sharing": ["notes", "handwritten", "summary", "revision notes"],
    "Study With Me": ["study with me", "pomodoro", "study session", "desk setup"],
    "Creativity": ["creative", "creativity", "idea", "innovation"],
    "Art": ["art", "painting", "sketch", "drawing", "illustration"],
    "Design": ["design", "ui", "ux", "graphic design", "prototype"],
    "Photography": ["photography", "photo", "camera", "portrait", "editing"],
    "Music": ["music", "song", "cover", "instrumental", "beats"],
    "Fashion": ["fashion", "style", "outfit", "lookbook"],
    "Growth": ["growth", "self growth", "self improvement", "mindset"],
    "Startups": ["startup", "founder", "saas", "business idea"],
    "Business": ["business", "strategy", "sales", "entrepreneurship"],
    "Finance": ["finance", "money", "budget", "investing", "saving"],
    "Trading": ["trading", "stock market", "crypto", "intraday", "chart"],
    "Marketing": ["marketing", "brand", "seo", "content marketing", "ads"],
    "Productivity": ["productivity", "focus", "time management", "deep work"],
    "Goals": ["goal", "target", "goal setting", "weekly goals"],
    "Achievements": ["achievement", "milestone", "result", "win"],
    "Freelancing": ["freelancing", "client", "gig", "remote work"],
    "Interview Preparation": ["interview", "hr round", "dsa", "mock interview"],
    "Entertainment": ["entertainment", "fun", "comedy", "show"],
    "Gaming": ["gaming", "gameplay", "esports", "pubg", "valorant"],
    "Memes": ["meme", "funny", "lol", "relatable"],
    "Travel": ["travel", "trip", "journey", "destination", "vlog"],
    "Food": ["food", "recipe", "cooking", "street food", "meal"],
    "Lifestyle": ["lifestyle", "daily life", "routine", "vlog"],
    "Fitness": ["fitness", "workout", "gym", "exercise", "training"],
    "Sports": [
        "sport", "sports", "athlete", "athletic", "match", "tournament", "league",
        "game", "team", "coach", "attack", "defense", "defence", "serve", "spike",
        "volleyball", "football", "soccer", "cricket", "badminton", "tennis", "kabaddi",
        "basketball", "hockey", "baseball", "swimming", "running", "marathon"
    ],
    "Health": ["health", "wellness", "diet", "healthy"],
    "Meditation": ["meditation", "mindfulness", "breathing", "calm"],
    "Morning Routine": ["morning routine", "5am", "habit", "sunrise"],
    "Motivation": ["motivation", "inspiration", "quote", "discipline"],
    "Challenges": ["challenge", "task", "push yourself"],
    "Daily Challenge": ["daily challenge", "day 1", "day challenge"],
    "30 Day Progress": ["30 day", "30 days", "progress", "transformation"],
    "Mini Projects": ["mini project", "project build", "side project"],
    "Build in Public": ["build in public", "building", "ship", "maker"],
    "Problem Solving": ["problem solving", "logic", "solution", "debugging"],
    "Brain Teasers": ["brain teaser", "riddle", "puzzle", "iq"],
    "Case Studies": ["case study", "analysis", "breakdown"],
    "Discussions": ["discussion", "debate", "opinion", "thoughts"],
    "Q&A": ["q&a", "question", "answer", "ask me anything"],
    "Portfolio Showcase": ["portfolio", "showcase", "project showcase"],
    "Short Tutorials": ["tutorial", "quick tips", "how to", "guide"],
}


def _keyword_variants(keyword):
    base = (keyword or "").strip().lower()
    if not base:
        return set()
    compact = base.replace(" ", "")
    underscored = base.replace(" ", "_")
    hyphenated = base.replace(" ", "-")
    return {base, compact, underscored, hyphenated}


def _increment_category_scores_from_text(text, scores, weight=1):
    if not text:
        return
    normalized = text.lower()
    for category, keywords in INTEREST_CATEGORY_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            scores[category] += weight


def _clean_interest_selection(raw_interests):
    cleaned = []
    seen = set()
    for item in raw_interests or []:
        category = (item or "").strip()
        if category in INTEREST_CATEGORY_KEYWORDS and category not in seen:
            seen.add(category)
            cleaned.append(category)
    return cleaned[:15]


def _profile_manual_interests(user):
    try:
        raw_interests = user.profile.interests
    except Profile.DoesNotExist:
        return []
    if not isinstance(raw_interests, list):
        return []
    return _clean_interest_selection(raw_interests)


def _ordered_categories_for_user(user):
    scores = {category: 0 for category in INTEREST_CATEGORY_KEYWORDS}
    category_order = {name: index for index, name in enumerate(INTEREST_CATEGORY_KEYWORDS.keys())}
    manual_interests = _profile_manual_interests(user)

    liked_captions = (
        Post.objects.filter(likes__user=user)
        .exclude(caption="")
        .values_list("caption", flat=True)
    )
    saved_captions = (
        user.saved_posts.exclude(caption="")
        .values_list("caption", flat=True)
    )
    own_captions = (
        Post.objects.filter(user=user)
        .exclude(caption="")
        .values_list("caption", flat=True)
    )

    for caption in liked_captions:
        _increment_category_scores_from_text(caption, scores, weight=3)
    for caption in saved_captions:
        _increment_category_scores_from_text(caption, scores, weight=2)
    for caption in own_captions:
        _increment_category_scores_from_text(caption, scores, weight=1)

    watch_rows = (
        ReelWatch.objects.filter(user=user)
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
            scores[category] += watch_weight

    manual_boost = len(manual_interests) * 100
    for index, category in enumerate(manual_interests):
        scores[category] += (manual_boost - index)

    ordered = sorted(
        INTEREST_CATEGORY_KEYWORDS.keys(),
        key=lambda category: (-scores[category], category_order[category]),
    )
    return ordered


def _ordered_reel_categories_for_user(user):
    ranked = _ordered_categories_for_user(user)
    without_trending = [category for category in ranked if category != "Trending"]
    return ["All", "Trending", *without_trending]


def _build_category_query(category_name):
    keywords = INTEREST_CATEGORY_KEYWORDS.get(category_name, [])
    query = Q()
    for keyword in keywords:
        for variant in _keyword_variants(keyword):
            query |= Q(caption__icontains=variant)
            query |= Q(caption__icontains=f"#{variant}")
    return query


def _categories_for_text(text):
    if not text:
        return []
    normalized = text.lower()
    hashtag_normalized = normalized.replace("#", "")
    searchable_text = f"{normalized} {hashtag_normalized}"
    matched = []
    for category, keywords in INTEREST_CATEGORY_KEYWORDS.items():
        if any(
            variant in searchable_text
            for keyword in keywords
            for variant in _keyword_variants(keyword)
        ):
            matched.append(category)
    return matched


def _reel_personalization_signals(user):
    category_scores = defaultdict(float)
    creator_scores = defaultdict(float)
    manual_interests = _profile_manual_interests(user)

    for index, category in enumerate(manual_interests):
        category_scores[category] += 40 - index

    liked_reel_captions = (
        Post.objects.filter(type="reel", likes__user=user)
        .exclude(caption="")
        .values_list("caption", flat=True)
    )
    for caption in liked_reel_captions:
        for category in _categories_for_text(caption):
            category_scores[category] += 12

    saved_reel_captions = (
        user.saved_posts.filter(type="reel")
        .exclude(caption="")
        .values_list("caption", flat=True)
    )
    for caption in saved_reel_captions:
        for category in _categories_for_text(caption):
            category_scores[category] += 8

    watch_rows = ReelWatch.objects.filter(
        user=user,
        post__type="reel"
    ).select_related("post", "post__user")
    for row in watch_rows:
        creator_scores[row.post.user_id] += (row.watch_seconds * 0.7) + (row.views * 5)
        for category in _categories_for_text(row.post.caption or ""):
            category_scores[category] += (row.watch_seconds * 0.35) + (row.views * 2)

    return category_scores, creator_scores


def _score_reel_for_user(reel, category_scores, creator_scores, liked_ids):
    score = 0.0
    score += creator_scores.get(reel.user_id, 0)
    if reel.id in liked_ids:
        score += 20
    if reel.is_recommended:
        score += 8

    for category in _categories_for_text(reel.caption or ""):
        score += category_scores.get(category, 0)

    age_hours = max(1, (timezone.now() - reel.created_at).total_seconds() / 3600)
    score += 36 / age_hours
    return score


def _is_video_file(name, content_type=""):
    if content_type and content_type.startswith("video/"):
        return True
    guessed, _ = mimetypes.guess_type(name or "")
    return bool(guessed and guessed.startswith("video/"))


def _ffprobe_duration_seconds(path):
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
    except subprocess.TimeoutExpired:
        print(f"[_ffprobe_duration_seconds] timeout expired for {path}")
        return None
    except FileNotFoundError:
        print("[_ffprobe_duration_seconds] ffprobe not found in PATH")
        return None
    except Exception as e:
        print(f"[_ffprobe_duration_seconds] Exception: {e}")
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


def _video_duration_seconds(uploaded_file):
    if not uploaded_file:
        return None
    temp_path = None
    try:
        suffix = os.path.splitext(getattr(uploaded_file, "name", "") or "")[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            for chunk in uploaded_file.chunks():
                tmp.write(chunk)
            temp_path = tmp.name
        try:
            uploaded_file.seek(0)
        except Exception:
            pass

        try:
            duration = _ffprobe_duration_seconds(temp_path)
            if duration is not None:
                return duration
        except Exception as e:
            print(f"[_video_duration_seconds] ffprobe failed: {e}")

        if suffix in {".mp4", ".m4v", ".mov"}:
            try:
                return _mp4_duration_seconds(temp_path)
            except Exception as e:
                print(f"[_video_duration_seconds] mp4 parsing failed: {e}")
        return None
    except Exception as e:
        print(f"[_video_duration_seconds] Error: {e}")
        return None
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def _format_mb(value):
    try:
        return f"{value / (1024 * 1024):.1f} MB"
    except Exception:
        return ""


def _direct_upload_enabled():
    return bool(
        getattr(settings, "CLOUDINARY_CLOUD_NAME", "")
        and getattr(settings, "CLOUDINARY_API_KEY", "")
        and getattr(settings, "CLOUDINARY_API_SECRET", "")
    )


def _upload_page_context(error=None):
    upload_preset = getattr(settings, "CLOUDINARY_UPLOAD_PRESET", "") or ""
    return {
        "error": error,
        "direct_upload_enabled": _direct_upload_enabled(),
        "cloudinary_cloud_name": getattr(settings, "CLOUDINARY_CLOUD_NAME", ""),
        "cloudinary_api_key": getattr(settings, "CLOUDINARY_API_KEY", ""),
        "cloudinary_upload_preset": upload_preset,
        "cloudinary_widget_enabled": bool(upload_preset),
        "allow_unsigned_upload": bool(getattr(settings, "ALLOW_UNSIGNED_UPLOAD", False)),
        "direct_upload_min_bytes": getattr(settings, "DIRECT_UPLOAD_MIN_BYTES", 0),
        "max_direct_upload_bytes": getattr(settings, "MAX_DIRECT_UPLOAD_BYTES", 0),
        "max_reel_upload_bytes": getattr(settings, "MAX_REEL_UPLOAD_BYTES", 0),
        "max_post_upload_bytes": getattr(settings, "MAX_POST_UPLOAD_BYTES", 0),
    }


def _fetch_youtube_music_suggestions(query, max_results=10):
    api_key = getattr(settings, "YOUTUBE_API_KEY", "") or os.getenv("YOUTUBE_API_KEY", "")
    if not api_key:
        return []
    params = urlencode({
        "part": "snippet",
        "maxResults": max_results,
        "q": query,
        "type": "video",
        "videoCategoryId": "10",
        "key": api_key,
    })
    url = f"https://www.googleapis.com/youtube/v3/search?{params}"
    try:
        with urlopen(url, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []
    tracks = []
    for item in payload.get("items", []):
        snippet = item.get("snippet") or {}
        title = (snippet.get("title") or "").strip()
        channel = (snippet.get("channelTitle") or "").strip()
        video_id = ((item.get("id") or {}).get("videoId") or "").strip()
        if not title or not video_id:
            continue
        thumbnails = snippet.get("thumbnails") or {}
        artwork_url = (
            ((thumbnails.get("medium") or {}).get("url") or "").strip()
            or ((thumbnails.get("high") or {}).get("url") or "").strip()
            or ((thumbnails.get("default") or {}).get("url") or "").strip()
        )
        label = f"{title} - {channel}" if channel else title
        tracks.append(_music_option(
            label=label[:80],
            youtube_url=f"https://www.youtube.com/watch?v={video_id}",
            artwork_url=artwork_url,
        ))
    return tracks


def _music_option(label, music_id=None, preview_url="", youtube_url="", artwork_url=""):
    return {
        "label": (label or "").strip()[:80],
        "music_id": music_id or "",
        "preview_url": preview_url or "",
        "youtube_url": youtube_url or "",
        "artwork_url": artwork_url or "",
    }


def _merge_music_options(primary, secondary, limit=50):
    merged = []
    seen = set()
    for row in (primary or []) + (secondary or []):
        option = _music_option(
            label=(row or {}).get("label", ""),
            music_id=(row or {}).get("music_id", ""),
            preview_url=(row or {}).get("preview_url", ""),
            youtube_url=(row or {}).get("youtube_url", ""),
            artwork_url=(row or {}).get("artwork_url", ""),
        )
        if not option["label"]:
            continue
        dedupe_key = (
            option["label"].strip().lower(),
            option["youtube_url"].strip().lower(),
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        merged.append(option)
        if len(merged) >= limit:
            break
    return merged


def _fetch_itunes_music_options(query, max_results=40):
    params = urlencode({
        "term": query,
        "entity": "song",
        "limit": max_results,
    })
    url = f"https://itunes.apple.com/search?{params}"
    try:
        with urlopen(url, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []

    options = []
    for row in payload.get("results", []):
        track = (row.get("trackName") or "").strip()
        artist = (row.get("artistName") or "").strip()
        preview_url = (row.get("previewUrl") or "").strip()
        track_url = (row.get("trackViewUrl") or "").strip()
        artwork_url = (
            (row.get("artworkUrl100") or "").strip()
            or (row.get("artworkUrl60") or "").strip()
            or (row.get("artworkUrl30") or "").strip()
        )
        if not track:
            continue
        label = f"{track} - {artist}" if artist else track
        options.append(_music_option(
            label=label[:80],
            preview_url=preview_url,
            youtube_url=track_url,
            artwork_url=artwork_url,
        ))
    return options


def _download_music_preview(preview_url, max_bytes=5 * 1024 * 1024):
    normalized = (preview_url or "").strip()
    if not (normalized.startswith("http://") or normalized.startswith("https://")):
        return None
    try:
        with urlopen(normalized, timeout=6) as response:
            content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            data = response.read(max_bytes + 1)
    except Exception:
        return None

    if not data or len(data) > max_bytes:
        return None

    if content_type and not content_type.startswith("audio/"):
        return None

    guessed_ext = mimetypes.guess_extension(content_type) if content_type else ""
    if not guessed_ext:
        guessed_ext = os.path.splitext(normalized.split("?")[0])[1] or ".mp3"
    if len(guessed_ext) > 8:
        guessed_ext = ".mp3"
    filename = f"preview_{int(timezone.now().timestamp())}{guessed_ext}"
    return ContentFile(data, name=filename)


def _admin_story_music_options(limit=60):
    rows = StoryMusic.objects.filter(is_active=True).order_by("-created_at")[:limit]
    options = []
    for row in rows:
        preview_url = ""
        if row.audio and row.audio.name:
            try:
                preview_url = row.audio.url
            except ValueError:
                preview_url = ""
        options.append(_music_option(
            label=row.display_title,
            music_id=row.id,
            preview_url=preview_url,
            youtube_url=row.youtube_url,
        ))
    return options


def _story_music_sections(user):
    sections = {
        "for_you": [],
        "trending": [],
        "new": [],
    }
    for section_key, query in YOUTUBE_SECTION_QUERY.items():
        itunes_tracks = _fetch_itunes_music_options(query, max_results=30)
        yt_tracks = _fetch_youtube_music_suggestions(query, max_results=30)
        merged_tracks = _merge_music_options(itunes_tracks, yt_tracks, limit=50)
        if merged_tracks:
            sections[section_key] = merged_tracks
    return sections


def _story_gallery_items(user, limit=30):
    items = []
    seen = set()

    post_media = (
        Post.objects.filter(user=user)
        .exclude(media="")
        .exclude(media__isnull=True)
        .order_by("-created_at")[:limit]
    )
    for post in post_media:
        if not post.media:
            continue
        storage_name = post.media.name
        if storage_name in seen:
            continue
        seen.add(storage_name)
        items.append({
            "url": post.media_url,
            "storage_name": storage_name,
            "kind": "video" if _is_video_file(storage_name) else "image",
        })

    story_media = Story.objects.filter(user=user).order_by("-created_at")[:limit]
    for story in story_media:
        media_file = story.media or story.image
        if not media_file:
            continue
        storage_name = media_file.name
        if storage_name in seen:
            continue
        seen.add(storage_name)
        preview_url = story.preview_url
        if not preview_url:
            continue
        items.append({
            "url": preview_url,
            "storage_name": storage_name,
            "kind": "video" if story.is_video else "image",
        })

    return items[:limit]


def _story_upload_context(user, error=None):
    return {
        "error": error,
        "filter_options": STORY_FILTER_LABELS,
        "music_sections": _story_music_sections(user),
        "gallery_items": _story_gallery_items(user),
    }


@login_required
@require_GET
def story_music_search_api(request):
    query = (request.GET.get("q") or "").strip()
    if len(query) < 2:
        return JsonResponse({"tracks": []})
    tracks = _merge_music_options(
        _fetch_itunes_music_options(query, max_results=30),
        _fetch_youtube_music_suggestions(query, max_results=30),
        limit=50,
    )
    return JsonResponse({"tracks": tracks})


def _story_access_user_ids(user):
    following_ids = set(
        Follow.objects.filter(follower=user).values_list("following_id", flat=True)
    )
    follower_ids = set(
        Follow.objects.filter(following=user).values_list("follower_id", flat=True)
    )
    return following_ids | follower_ids | {user.id}


def _shareable_followers(user):
    follower_ids = Follow.objects.filter(
        following=user
    ).values_list("follower_id", flat=True)
    return User.objects.filter(id__in=follower_ids).order_by("username")


def _social_priority_user_ids(user):
    following_ids = set(
        Follow.objects.filter(follower=user).values_list("following_id", flat=True)
    )
    follower_ids = set(
        Follow.objects.filter(following=user).values_list("follower_id", flat=True)
    )
    return following_ids | follower_ids


def _ensure_profiles_for_user_ids(user_ids):
    ids = {uid for uid in (user_ids or []) if uid}
    if not ids:
        return
    existing_ids = set(
        Profile.objects.filter(user_id__in=ids).values_list("user_id", flat=True)
    )
    missing_ids = [uid for uid in ids if uid not in existing_ids]
    if missing_ids:
        Profile.objects.bulk_create(
            [Profile(user_id=uid) for uid in missing_ids],
            ignore_conflicts=True,
        )


@login_required
def home(request):
    profile_username = (request.GET.get("user") or "").strip()
    if profile_username:
        profile_user = get_object_or_404(User, username=profile_username)
        posts = Post.objects.filter(user=profile_user).order_by("-created_at")

        liked_post_ids = set(
            Like.objects.filter(user=request.user).values_list("post_id", flat=True)
        )
        saved_post_ids = set(
            request.user.saved_posts.values_list("id", flat=True)
        )
        posts = list(posts)
        for post in posts:
            post.story_id = None

        context = {
            "posts": posts,
            "selected_category": "All",
            "featured_categories": [],
            "hidden_categories": [],
            "story_items": [],
            "active_story_user_ids": [],
            "unseen_story_user_ids": [],
            "current_user_story": None,
            "current_user_story_seen": True,
            "liked_post_ids": liked_post_ids,
            "saved_post_ids": saved_post_ids,
            "share_followers": _shareable_followers(request.user),
            "is_profile_feed": True,
            "profile_user": profile_user,
        }
        return render(request, 'home.html', context)

    category_ranked = _ordered_reel_categories_for_user(request.user)
    selected_category = (request.GET.get("category") or "All").strip()
    if selected_category not in category_ranked:
        selected_category = "All"

    featured_limit = 8
    featured_categories = category_ranked[:featured_limit]
    hidden_categories = category_ranked[featured_limit:]

    social_priority_ids = _social_priority_user_ids(request.user)
    fresh_social_cutoff = timezone.now() - timedelta(hours=18)
    posts_qs = Post.objects.annotate(
        own_fresh_priority=Case(
            When(
                user_id=request.user.id,
                created_at__gte=fresh_social_cutoff,
                then=Value(0),
            ),
            default=Value(1),
            output_field=IntegerField(),
        ),
        fresh_social_priority=Case(
            When(
                user_id__in=social_priority_ids,
                created_at__gte=fresh_social_cutoff,
                then=Value(0),
            ),
            default=Value(1),
            output_field=IntegerField(),
        ),
        social_priority=Case(
            When(user_id__in=social_priority_ids, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    )
    if selected_category == "Trending":
        posts = (
            posts_qs.annotate(
                total_likes=Count("likes", distinct=True),
                total_comments=Count("comments", distinct=True),
            )
            .order_by(
                "own_fresh_priority",
                "fresh_social_priority",
                "social_priority",
                "-created_at",
                "-is_recommended",
                "-total_likes",
                "-total_comments",
            )
        )
    elif selected_category == "All":
        posts = posts_qs.order_by(
            "own_fresh_priority",
            "fresh_social_priority",
            "social_priority",
            "-created_at",
        )
    else:
        category_query = _build_category_query(selected_category)
        posts = posts_qs.filter(category_query).order_by(
            "own_fresh_priority",
            "fresh_social_priority",
            "social_priority",
            "-created_at",
        )

    liked_post_ids = set(
        Like.objects.filter(user=request.user).values_list("post_id", flat=True)
    )
    saved_post_ids = set(
        request.user.saved_posts.values_list("id", flat=True)
    )
    visible_user_ids = _story_access_user_ids(request.user)
    active_since = timezone.now() - timedelta(hours=24)
    stories_qs = Story.objects.filter(
        user_id__in=visible_user_ids,
        created_at__gte=active_since
    ).select_related("user").order_by("-created_at")

    active_story_ids = list(stories_qs.values_list("id", flat=True))
    seen_story_ids = set(
        StorySeen.objects.filter(
            viewer=request.user,
            story_id__in=active_story_ids
        ).values_list("story_id", flat=True)
    )

    current_user_stories = list(stories_qs.filter(user=request.user))
    current_user_story = current_user_stories[0] if current_user_stories else None
    current_user_story_seen = True
    if current_user_stories:
        current_user_story_seen = all(story.id in seen_story_ids for story in current_user_stories)

    story_items = []
    story_state_by_user = {}
    first_story_id_by_user = {}
    for story in stories_qs:
        if story.user_id not in first_story_id_by_user:
            first_story_id_by_user[story.user_id] = story.id
        if story.user_id == request.user.id:
            continue
        if story.user_id not in story_state_by_user:
            story_state_by_user[story.user_id] = {
                "story": story,
                "has_unseen": False,
            }
        if story.id not in seen_story_ids:
            story_state_by_user[story.user_id]["has_unseen"] = True
    story_items = list(story_state_by_user.values())
    active_story_user_ids = [item["story"].user_id for item in story_items]
    unseen_story_user_ids = [
        item["story"].user_id for item in story_items if item["has_unseen"]
    ]
    posts = list(posts)
    for post in posts:
        post.story_id = first_story_id_by_user.get(post.user_id)

    if _media_debug_enabled():
        for post in posts[:10]:
            if post.media and not post.media_url:
                try:
                    raw_url = post.media.url
                except Exception:
                    raw_url = ""
                print(
                    "[media-debug][home] missing media_url",
                    {
                        "post_id": post.id,
                        "name": getattr(post.media, "name", ""),
                        "type": post.type,
                        "is_video": post.is_video,
                        "raw_url": raw_url,
                        "can_use_cloudinary": getattr(settings, "CAN_USE_CLOUDINARY", False),
                        "cloud_name": getattr(settings, "CLOUDINARY_CLOUD_NAME", ""),
                    },
                )

    context = {
        'posts': posts,
        "selected_category": selected_category,
        "featured_categories": featured_categories,
        "hidden_categories": hidden_categories,
        "story_items": story_items,
        "active_story_user_ids": active_story_user_ids,
        "unseen_story_user_ids": unseen_story_user_ids,
        "current_user_story": current_user_story,
        "current_user_story_seen": current_user_story_seen,
        "liked_post_ids": liked_post_ids,
        "saved_post_ids": saved_post_ids,
        "share_followers": _shareable_followers(request.user),
    }

    return render(request, 'home.html', context)


@login_required
def notifications(request):
    notifications_qs = Notification.objects.filter(
        receiver=request.user
    ).select_related("sender").order_by("-created_at")

    notifications_qs.filter(is_read=False).update(is_read=True)

    # Group notifications like Instagram: Today, Yesterday, Last 7 days, Older
    from django.utils import timezone
    from datetime import timedelta

    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    last7_start = today - timedelta(days=7)

    sections = [
        {"title": "Today", "rows": []},
        {"title": "Yesterday", "rows": []},
        {"title": "Last 7 days", "rows": []},
        {"title": "Earlier", "rows": []},
    ]

    for n in notifications_qs:
        n_date = timezone.localtime(n.created_at).date()
        if n_date == today:
            sections[0]["rows"].append(n)
        elif n_date == yesterday:
            sections[1]["rows"].append(n)
        elif last7_start <= n_date < yesterday:
            sections[2]["rows"].append(n)
        else:
            sections[3]["rows"].append(n)

    return render(request, "notification.html", {
        "notifications": notifications_qs,
        "sections": sections,
    })




@login_required
def profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    posts = Post.objects.filter(user=profile_user, type="post").order_by("-created_at")
    reels = Post.objects.filter(user=profile_user, type="reel").order_by("-created_at")
    highlighted_stories = Story.objects.filter(
        user=profile_user,
        is_highlight=True
    ).order_by("-created_at")

    is_following = False
    is_followed_back = False
    can_message = False

    if request.user.is_authenticated and request.user != profile_user:
        is_following = Follow.objects.filter(
            follower=request.user,
            following=profile_user
        ).exists()
        is_followed_back = Follow.objects.filter(
            follower=profile_user,
            following=request.user
        ).exists()
        can_message = is_following and is_followed_back

    followers_count = Follow.objects.filter(following=profile_user).count()
    following_count = Follow.objects.filter(follower=profile_user).count()
    active_since = timezone.now() - timedelta(hours=24)
    active_story_ids = list(
        Story.objects.filter(
            user=profile_user,
            created_at__gte=active_since
        ).order_by("-created_at").values_list("id", flat=True)
    )
    profile_story_id = active_story_ids[0] if active_story_ids else None
    profile_story_seen = True
    if profile_story_id and request.user != profile_user:
        seen_ids = set(
            StorySeen.objects.filter(
                viewer=request.user,
                story_id__in=active_story_ids
            ).values_list("story_id", flat=True)
        )
        profile_story_seen = all(story_id in seen_ids for story_id in active_story_ids)

    context = {
        "profile_user": profile_user,
        "posts": posts,
        "reels": reels,
        "manual_interests": _profile_manual_interests(profile_user),
        "highlighted_stories": highlighted_stories,
        "posts_count": (posts.count() if posts else 0) + (reels.count() if reels else 0),
        "followers_count": followers_count,
        "following_count": following_count,
        "is_following": is_following,
        "is_followed_back": is_followed_back,
        "can_message": can_message,
        "profile_story_id": profile_story_id,
        "profile_story_seen": profile_story_seen,
    }

    return render(request, "profile.html", context)


@login_required
def profile_menu(request):
    return render(request, "profile_menu.html")


@login_required
def search_view(request):
    query = request.GET.get('q', '')
    users = User.objects.filter(username__icontains=query).order_by("username")

    recommended_reels = list(
        Post.objects.filter(
            type='reel',
            is_recommended=True,
            media__isnull=False
        ).select_related('user').order_by('-created_at')[:12]
    )

    context = {
        'users': users,
        'query': query,
        'recommended_reels': recommended_reels
    }

    return render(request, 'search.html', context)


@login_required
def reels(request):
    profile_username = (request.GET.get("user") or "").strip()
    profile_user = None
    selected_category = (request.GET.get("category") or "All").strip()
    available_categories = _ordered_reel_categories_for_user(request.user)
    if selected_category not in available_categories:
        selected_category = "All"

    social_priority_ids = _social_priority_user_ids(request.user)
    reels_qs = Post.objects.filter(type="reel").select_related("user").prefetch_related(
        "likes", "comments__user"
    )
    if profile_username:
        profile_user = get_object_or_404(User, username=profile_username)
        reels_qs = reels_qs.filter(user=profile_user)

    share_followers = _shareable_followers(request.user)
    # Ensure profiles exist for reel owners + share followers to avoid template errors.
    reel_user_ids = set(reels_qs.values_list("user_id", flat=True))
    follower_ids = set(share_followers.values_list("id", flat=True))
    _ensure_profiles_for_user_ids(reel_user_ids | follower_ids | {request.user.id})

    liked_post_ids = set(
        Like.objects.filter(user=request.user).values_list("post_id", flat=True)
    )
    category_scores, creator_scores = _reel_personalization_signals(request.user)

    if selected_category == "Trending":
        ranked_reels = list(
            reels_qs.annotate(
                total_likes=Count("likes", distinct=True),
                total_comments=Count("comments", distinct=True),
            ).order_by("-is_recommended", "-total_likes", "-total_comments", "-created_at")
        )
    else:
        filtered_qs = reels_qs
        if selected_category != "All":
            filtered_qs = filtered_qs.filter(_build_category_query(selected_category))

        ranked_reels = sorted(
            filtered_qs,
            key=lambda reel: (
                0 if reel.user_id in social_priority_ids else 1,
                -_score_reel_for_user(
                    reel,
                    category_scores=category_scores,
                    creator_scores=creator_scores,
                    liked_ids=liked_post_ids,
                ),
                -reel.created_at.timestamp(),
            ),
        )

    if _media_debug_enabled():
        for reel in ranked_reels[:10]:
            if reel.media and not reel.media_url:
                try:
                    raw_url = reel.media.url
                except Exception:
                    raw_url = ""
                print(
                    "[media-debug][reels] missing media_url",
                    {
                        "post_id": reel.id,
                        "name": getattr(reel.media, "name", ""),
                        "type": reel.type,
                        "is_video": reel.is_video,
                        "raw_url": raw_url,
                        "can_use_cloudinary": getattr(settings, "CAN_USE_CLOUDINARY", False),
                        "cloud_name": getattr(settings, "CLOUDINARY_CLOUD_NAME", ""),
                    },
                )

    return render(request, "reels.html", {
        "reels": ranked_reels,
        "selected_category": selected_category,
        "liked_post_ids": liked_post_ids,
        "share_followers": share_followers,
    })


@login_required
def reel_watch_ping(request, post_id):
    reel = get_object_or_404(Post, id=post_id, type="reel")
    if request.method != "POST":
        return JsonResponse({"ok": True})
    seconds_raw = request.POST.get("seconds", "0")
    mark_view_raw = request.POST.get("mark_view", "0")

    try:
        watched_seconds = float(seconds_raw)
    except (TypeError, ValueError):
        watched_seconds = 0.0

    watched_seconds = max(0.0, min(300.0, watched_seconds))
    mark_view = mark_view_raw == "1"

    row, _ = ReelWatch.objects.get_or_create(user=request.user, post=reel)
    if watched_seconds > 0:
        row.watch_seconds += watched_seconds
    if mark_view:
        row.views += 1
    row.save(update_fields=["watch_seconds", "views", "updated_at"])
    return JsonResponse({"ok": True})


@login_required
@require_POST
def post_watch_ping(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    
    # Parse JSON body
    seconds_raw = "0"
    mark_view_raw = "0"
    try:
        body = json.loads(request.body) if request.body else {}
        seconds_raw = body.get("seconds", "0")
        mark_view_raw = body.get("mark_view", "0")
    except (json.JSONDecodeError, ValueError):
        pass

    try:
        watched_seconds = float(seconds_raw)
    except (TypeError, ValueError):
        watched_seconds = 0.0

    watched_seconds = max(0.0, min(300.0, watched_seconds))
    mark_view = mark_view_raw == "1"

    row, _ = ReelWatch.objects.get_or_create(user=request.user, post=post)
    if watched_seconds > 0:
        row.watch_seconds += watched_seconds
    if mark_view:
        row.views += 1
    row.save(update_fields=["watch_seconds", "views", "updated_at"])
    return JsonResponse({"ok": True})


def register(request):
    if request.method == 'POST':
        email = request.POST.get('email', '')
        username = request.POST.get('username', '')
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        if password1 != password2:
            return render(request, 'register.html', {'error': 'Passwords do not match'})

        if User.objects.filter(username=username).exists():
            return render(request, 'register.html', {'error': 'Username already exists'})

        if User.objects.filter(email=email).exists():
            return render(request, 'register.html', {'error': 'Email already registered'})

        User.objects.create_user(username=username, email=email, password=password1)
        return redirect('login')

    return render(request, 'register.html')


def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            return render(request, 'login.html', {'error': 'Invalid credentials'})

    return render(request, 'login.html')


def user_logout(request):
    logout(request)
    return redirect('login')


@login_required
def edit_profile(request):
    interest_categories = list(INTEREST_CATEGORY_KEYWORDS.keys())
    selected_interests = _profile_manual_interests(request.user)

    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST,
                                    request.FILES,
                                    instance=request.user.profile)
        selected_interests = _clean_interest_selection(request.POST.getlist("interests"))

        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            profile_obj = p_form.save(commit=False)
            profile_obj.interests = selected_interests
            profile_obj.save()
            return redirect('profile', username=request.user.username)
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)

    context = {
        'u_form': u_form,
        'p_form': p_form,
        "interest_categories": interest_categories,
        "selected_interests": selected_interests,
    }

    return render(request, 'edit_profile.html', context)


@login_required
def edit_bio(request):
    if request.method == 'POST':
        p_form = ProfileUpdateForm(request.POST, instance=request.user.profile)

        if p_form.is_valid():
            p_form.save()
            return redirect('profile', username=request.user.username)
    else:
        p_form = ProfileUpdateForm(instance=request.user.profile)

    context = {
        'p_form': p_form
    }

    return render(request, 'edit_bio.html', context)


@login_required
def payment_settings(request):
    if request.method == "POST":
        upi_form = UpiIdUpdateForm(request.POST, instance=request.user.profile)
        if upi_form.is_valid():
            upi_form.save()
            return redirect("profile", username=request.user.username)
    else:
        upi_form = UpiIdUpdateForm(instance=request.user.profile)

    return render(request, "payment_settings.html", {
        "upi_form": upi_form
    })


@login_required
@require_POST
def follow(request, username):
    target_user = get_object_or_404(User, username=username)

    if request.user == target_user:
        return redirect('profile', username=username)

    follow, created = Follow.objects.get_or_create(
        follower=request.user,
        following=target_user
    )

    if created:
        # Create notification only when new follow is created
        Notification.objects.create(
            sender=request.user,
            receiver=target_user,
            notification_type="follow"
        )

    return redirect('profile', username=username)


@login_required
@require_POST
def unfollow(request, username):
    target_user = get_object_or_404(User, username=username)

    if request.user == target_user:
        return redirect('profile', username=username)

    Follow.objects.filter(
        follower=request.user,
        following=target_user
    ).delete()

    return redirect('profile', username=username)


@login_required
def send_follow_request(request, username):
    user_to_follow = get_object_or_404(User, username=username)

    if request.user != user_to_follow:
        follow_obj, created = Follow.objects.get_or_create(
            follower=request.user,
            following=user_to_follow
        )

        if created:
            Notification.objects.create(
                sender=request.user,
                receiver=user_to_follow,
                notification_type="follow"
            )

    return redirect("profile", username=username)


@login_required
def accept_follow(request, follow_id):
    follow = get_object_or_404(Follow, id=follow_id)
    follow.accepted = True
    follow.save()

    # Create notification for the follower
    Notification.objects.create(
        sender=request.user,
        receiver=follow.follower,
        notification_type="follow_accepted"
    )

    return redirect("notifications")


@login_required
def notification_view(request):
    notifications = Notification.objects.filter(receiver=request.user).order_by("-created_at")

    return render(request, "notification.html", {
        "notifications": notifications
    })


def _chat_partner_ids(user):
    sent_ids = set(
        Message.objects.filter(sender=user).values_list("receiver_id", flat=True)
    )
    received_ids = set(
        Message.objects.filter(receiver=user).values_list("sender_id", flat=True)
    )
    partner_ids = sent_ids | received_ids
    partner_ids.discard(user.id)
    return partner_ids


def _chat_contact_ids(user):
    following_ids = set(
        Follow.objects.filter(follower=user).values_list("following_id", flat=True)
    )
    follower_ids = set(
        Follow.objects.filter(following=user).values_list("follower_id", flat=True)
    )
    # Chat contacts must be mutual-follow users.
    contact_ids = following_ids & follower_ids
    contact_ids.discard(user.id)
    return contact_ids


def _is_mutual_follow(user_a, user_b):
    if not user_a or not user_b or user_a == user_b:
        return False
    return (
        Follow.objects.filter(follower=user_a, following=user_b).exists()
        and Follow.objects.filter(follower=user_b, following=user_a).exists()
    )


def _chat_lock_map(user):
    locks = ChatLock.objects.filter(owner=user, is_active=True)
    return {lock.target_id: lock for lock in locks}


def _chat_unlock_ids_from_code(user, code_candidate):
    normalized = (code_candidate or "").strip()
    if not normalized:
        return set()
    unlocked = set()
    for lock in ChatLock.objects.filter(owner=user, is_active=True):
        if lock.matches_code(normalized):
            unlocked.add(lock.target_id)
    return unlocked


def _chat_visible_contact_ids(user, code_candidate=""):
    contact_ids = _chat_contact_ids(user)
    lock_map = _chat_lock_map(user)
    unlocked_ids = _chat_unlock_ids_from_code(user, code_candidate)
    locked_ids = set(lock_map.keys()) - unlocked_ids
    return contact_ids - locked_ids, unlocked_ids


def _chat_search_results(user, query, limit=12):
    normalized_query = " ".join((query or "").split()).strip()
    if not normalized_query:
        return []

    contact_ids, unlocked_ids = _chat_visible_contact_ids(user, normalized_query)
    if not contact_ids:
        return []

    users = User.objects.filter(id__in=contact_ids).filter(
        Q(username__icontains=normalized_query)
        | Q(first_name__icontains=normalized_query)
        | Q(last_name__icontains=normalized_query)
    ).annotate(
        relevance=Case(
            When(username__iexact=normalized_query, then=Value(0)),
            When(username__istartswith=normalized_query, then=Value(1)),
            When(first_name__istartswith=normalized_query, then=Value(2)),
            When(last_name__istartswith=normalized_query, then=Value(2)),
            When(username__icontains=normalized_query, then=Value(3)),
            default=Value(4),
            output_field=IntegerField(),
        )
    ).order_by("relevance", "username")

    results = list(users[:limit])

    # If the query itself is a valid lock code, surface unlocked users
    # even when their usernames don't match the query string.
    if unlocked_ids:
        unlocked_users = list(
            User.objects.filter(id__in=(unlocked_ids & contact_ids)).order_by("username")[:limit]
        )
        existing_ids = {u.id for u in results}
        for user_obj in unlocked_users:
            if user_obj.id not in existing_ids:
                results.append(user_obj)

    return results[:limit]


def _format_relative_time(dt, now=None):
    if not dt:
        return ""
    now = now or timezone.now()
    delta = now - dt
    seconds = max(0, int(delta.total_seconds()))
    if seconds < 60:
        return "now"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def _message_preview_text(message):
    if message.content:
        return message.content
    if message.media_type == "image":
        return "[Photo]"
    if message.media_type == "video":
        return "[Video]"
    if message.media_type == "audio":
        return "[Voice message]"
    return "[Attachment]"


def _detect_chat_media_type(file_obj):
    content_type = (getattr(file_obj, "content_type", "") or "").lower()
    if content_type.startswith("image/"):
        return "image"
    if content_type.startswith("video/"):
        return "video"
    if content_type.startswith("audio/"):
        return "audio"
    # Fallback to filename-based detection when content_type is missing/unknown.
    name = (getattr(file_obj, "name", "") or "").lower()
    guessed, _ = mimetypes.guess_type(name)
    if guessed:
        if guessed.startswith("image/"):
            return "image"
        if guessed.startswith("video/"):
            return "video"
        if guessed.startswith("audio/"):
            return "audio"
    if name.endswith((".heic", ".heif")):
        return "image"
    return ""


def _is_user_active_recently(user_obj, now=None, minutes=10):
    now = now or timezone.now()
    return bool(
        getattr(user_obj, "last_login", None)
        and (now - user_obj.last_login) <= timedelta(minutes=minutes)
    )


def _build_chat_rows(request_user, users_qs):
    rows = []
    now = timezone.now()
    for u in users_qs:
        last_message = (
            Message.objects.filter(
                (Q(sender=request_user, receiver=u) | Q(sender=u, receiver=request_user))
            )
            .order_by("-timestamp")
            .first()
        )
        unread_count = Message.objects.filter(
            sender=u,
            receiver=request_user,
            is_seen=False
        ).count()
        if last_message:
            is_mine = last_message.sender_id == request_user.id
            preview_text = _message_preview_text(last_message)
            if is_mine:
                subtitle = f"You: {preview_text[:34]}"
            else:
                subtitle = preview_text[:40]
            time_text = _format_relative_time(last_message.timestamp, now)
        else:
            subtitle = "Tap to chat"
            time_text = ""

        active_recently = _is_user_active_recently(u, now=now, minutes=10)
        if unread_count > 0 and last_message and last_message.sender_id == u.id:
            status_text = _message_preview_text(last_message)[:48]
        elif not last_message and not active_recently:
            status_text = "Tap to chat"
        elif active_recently:
            status_text = "Active now"
        elif getattr(u, "last_login", None):
            status_text = f"Active {_format_relative_time(u.last_login, now)} ago"
        else:
            status_text = subtitle

        rows.append({
            "user": u,
            "subtitle": subtitle,
            "status_text": status_text,
            "time_text": time_text,
            "unread_count": unread_count,
            "is_unread": unread_count > 0,
            "active_recently": active_recently,
        })
    return rows


@login_required
def chat_inbox(request):
    chat_search_query = (request.GET.get("q") or "").strip()
    chat_search_results = _chat_search_results(request.user, chat_search_query)
    visible_contact_ids, unlocked_ids = _chat_visible_contact_ids(request.user, chat_search_query)
    partner_ids = _chat_partner_ids(request.user) & visible_contact_ids
    partner_ids |= unlocked_ids
    if partner_ids:
        chat_users = User.objects.filter(id__in=partner_ids).order_by("username")
    else:
        chat_users = User.objects.none()
    chat_rows = _build_chat_rows(request.user, chat_users)
    return render(request, "chat_inbox.html", {
        "chat_users": chat_users,
        "chat_rows": chat_rows,
        "chat_search_query": chat_search_query,
        "chat_search_results": chat_search_results,
    })


@login_required
def chat(request, username):
    receiver = get_object_or_404(User, username=username)
    if receiver != request.user and not _is_mutual_follow(request.user, receiver):
        return HttpResponseForbidden("Chat is available only after follow back.")

    chat_search_query = (request.GET.get("q") or "").strip()
    chat_search_results = _chat_search_results(request.user, chat_search_query)

    # Mark incoming messages as seen as soon as this chat is opened.
    if receiver != request.user:
        Message.objects.filter(
            sender=receiver,
            receiver=request.user,
            is_seen=False
        ).update(is_seen=True)

    visible_contact_ids, unlocked_ids = _chat_visible_contact_ids(request.user, chat_search_query)
    partner_ids = (_chat_partner_ids(request.user) & visible_contact_ids) | unlocked_ids
    if receiver != request.user:
        partner_ids.add(receiver.id)
    if partner_ids:
        chat_users = User.objects.filter(id__in=partner_ids).order_by("username")
    else:
        chat_users = User.objects.none()
    chat_rows = _build_chat_rows(request.user, chat_users)

    if receiver == request.user:
        first_user = chat_users.first()
        if first_user:
            return redirect("chat", username=first_user.username)

    if request.method == "POST":
        content = (request.POST.get("message") or "").strip()
        if content:
            Message.objects.create(
                sender=request.user,
                receiver=receiver,
                content=content
            )
            return redirect("chat", username=receiver.username)

    messages = Message.objects.filter(
        sender=request.user, receiver=receiver
    ) | Message.objects.filter(
        sender=receiver, receiver=request.user
    )
    messages = messages.order_by("timestamp")
    receiver_active_recently = _is_user_active_recently(receiver, now=timezone.now(), minutes=10)

    return render(request, "chat.html", {
        "messages": messages,
        "receiver": receiver,
        "receiver_active_recently": receiver_active_recently,
        "chat_users": chat_users,
        "chat_rows": chat_rows,
        "chat_search_query": chat_search_query,
        "chat_search_results": chat_search_results,
    })


@login_required
@require_POST
def lock_chat(request, username):
    target_user = get_object_or_404(User, username=username)
    if target_user == request.user:
        return JsonResponse({"error": "Cannot lock self chat"}, status=400)
    if not _is_mutual_follow(request.user, target_user):
        return JsonResponse({"error": "Lock chat is available only after follow back."}, status=403)

    code = " ".join((request.POST.get("code") or "").split()).strip()
    if len(code) < 3:
        return JsonResponse({"error": "Code must be at least 3 characters"}, status=400)

    lock_obj, _ = ChatLock.objects.get_or_create(owner=request.user, target=target_user)
    lock_obj.set_code(code)
    lock_obj.save(update_fields=["code_hash", "is_active", "updated_at"])
    return JsonResponse({"locked": True, "username": target_user.username})


def _serialize_chat_message(message, request_user):
    media_url = message.media_url or ""
    media_type = message.media_type
    if message.media and not media_type:
        guessed, _ = mimetypes.guess_type(message.media.name or "")
        if guessed:
            if guessed.startswith("image/"):
                media_type = "image"
            elif guessed.startswith("video/"):
                media_type = "video"
            elif guessed.startswith("audio/"):
                media_type = "audio"
    return {
        "id": message.id,
        "content": message.content,
        "media_url": media_url,
        "media_type": media_type,
        "is_mine": message.sender_id == request_user.id,
        "is_seen": message.is_seen,
        "sender": message.sender.username,
        "timestamp": message.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _chat_group_name(user_id, peer_id):
    low_id, high_id = sorted([user_id, peer_id])
    return f"chat_{low_id}_{high_id}"


@login_required
@require_GET
def chat_messages_api(request, username):
    receiver = get_object_or_404(User, username=username)
    if receiver != request.user and not _is_mutual_follow(request.user, receiver):
        return JsonResponse({"error": "Chat is available only after follow back."}, status=403)
    last_id = request.GET.get("last_id")

    Message.objects.filter(
        sender=receiver,
        receiver=request.user,
        is_seen=False
    ).update(is_seen=True)

    qs = Message.objects.filter(
        sender=request.user, receiver=receiver
    ) | Message.objects.filter(
        sender=receiver, receiver=request.user
    )
    qs = qs.order_by("id")

    if last_id and last_id.isdigit():
        qs = qs.filter(id__gt=int(last_id))

    data = [_serialize_chat_message(m, request.user) for m in qs]
    return JsonResponse({"messages": data})


@login_required
@require_POST
def chat_send_api(request, username):
    receiver = get_object_or_404(User, username=username)
    if receiver != request.user and not _is_mutual_follow(request.user, receiver):
        return JsonResponse({"error": "Chat is available only after follow back."}, status=403)
    content = (request.POST.get("message") or "").strip()
    media_file = request.FILES.get("media")
    media_type = "text"

    if media_file:
        media_type = _detect_chat_media_type(media_file)
        if not media_type:
            return JsonResponse({"error": "Only image, video, or audio files are allowed."}, status=400)

    if not content and not media_file:
        return JsonResponse({"error": "Empty message"}, status=400)

    message = Message(
        sender=request.user,
        receiver=receiver,
        content=content,
        media_type=media_type,
    )
    if media_file:
        message.media = media_file
    try:
        message.save()
    except Exception as exc:
        # Provide a clear error for client + server logs to debug storage issues.
        err_text = f"Upload failed: {exc.__class__.__name__}"
        try:
            detail = str(exc)
            if detail:
                err_text = f"{err_text} - {detail}"
        except Exception:
            pass
        print(f"[chat_send_api] {err_text}")
        return JsonResponse({"error": err_text}, status=500)

    channel_layer = get_channel_layer()
    if channel_layer:
        media_url = message.media_url or ""
        async_to_sync(channel_layer.group_send)(
            _chat_group_name(request.user.id, receiver.id),
            {
                "type": "chat_message",
                "message": {
                    "id": message.id,
                    "content": message.content,
                    "media_url": media_url,
                    "media_type": message.media_type,
                    "sender": request.user.username,
                    "sender_id": request.user.id,
                    "is_seen": message.is_seen,
                    "timestamp": message.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                },
            },
        )

    return JsonResponse({
        "message": _serialize_chat_message(message, request.user)
    })


@login_required
@require_POST
def chat_delete_api(request, username, message_id):
    receiver = get_object_or_404(User, username=username)
    if receiver != request.user and not _is_mutual_follow(request.user, receiver):
        return JsonResponse({"error": "Chat is available only after follow back."}, status=403)

    message = get_object_or_404(Message, id=message_id)
    if message.sender_id != request.user.id:
        return JsonResponse({"error": "Not allowed"}, status=403)

    valid_pair = (
        (message.sender_id == request.user.id and message.receiver_id == receiver.id)
        or (message.sender_id == receiver.id and message.receiver_id == request.user.id)
    )
    if not valid_pair:
        return JsonResponse({"error": "Invalid chat message"}, status=400)

    if message.media:
        message.media.delete(save=False)
    message.delete()
    return JsonResponse({"deleted": True, "id": message_id})



@login_required
def search(request):
    query = (request.GET.get('q') or '').strip()
    users = User.objects.all()
    if query:
        normalized_query = " ".join(query.split())
        users = users.filter(
            Q(username__icontains=normalized_query)
            | Q(first_name__icontains=normalized_query)
            | Q(last_name__icontains=normalized_query)
            | Q(email__icontains=normalized_query)
        ).annotate(
            relevance=Case(
                When(username__iexact=normalized_query, then=Value(0)),
                When(username__istartswith=normalized_query, then=Value(1)),
                When(first_name__istartswith=normalized_query, then=Value(2)),
                When(last_name__istartswith=normalized_query, then=Value(2)),
                When(username__icontains=normalized_query, then=Value(3)),
                default=Value(4),
                output_field=IntegerField(),
            )
        ).order_by('relevance', 'username')
    else:
        users = users.order_by('username')

    recommended_reels = list(
        Post.objects.filter(
            type='reel',
            is_recommended=True,
            media__isnull=False
        ).select_related('user').order_by('-created_at')[:12]
    )

    return render(request, 'search.html', {
        'users': users[:30],
        'query': query,
        'recommended_reels': recommended_reels,
    })


@login_required
@require_GET
def search_suggestions(request):
    query = (request.GET.get("q") or "").strip()
    if len(query) < 1:
        return JsonResponse({"users": []})

    normalized_query = " ".join(query.split())
    users = User.objects.select_related("profile").filter(
        Q(username__icontains=normalized_query)
        | Q(first_name__icontains=normalized_query)
        | Q(last_name__icontains=normalized_query)
        | Q(email__icontains=normalized_query)
    ).annotate(
        relevance=Case(
            When(username__iexact=normalized_query, then=Value(0)),
            When(username__istartswith=normalized_query, then=Value(1)),
            When(first_name__istartswith=normalized_query, then=Value(2)),
            When(last_name__istartswith=normalized_query, then=Value(2)),
            When(username__icontains=normalized_query, then=Value(3)),
            default=Value(4),
            output_field=IntegerField(),
        )
    ).order_by("relevance", "username")[:10]

    return JsonResponse({
        "users": [
            {
                "username": user.username,
                "display_name": user.get_full_name().strip() or user.username,
                "avatar_url": _user_avatar_url(user),
            }
            for user in users
        ]
    })
    
@login_required
def followers_list(request, username):
    profile_user = get_object_or_404(User, username=username)

    followers = Follow.objects.filter(
        following=profile_user
    ).select_related("follower")

    return render(request, "followers.html", {
        "profile_user": profile_user,
        "followers": followers
    })


@login_required
def following_list(request, username):
    profile_user = get_object_or_404(User, username=username)

    following = Follow.objects.filter(
        follower=profile_user
    ).select_related("following")

    return render(request, "following.html", {
        "profile_user": profile_user,
        "following": following
    })


@login_required
def upload(request):
    if request.method == "POST":
        try:
            media = request.FILES.get("media")
            caption = (request.POST.get("caption") or "").strip()
            post_type = (request.POST.get("type") or "post").strip().lower()
            if post_type not in ("post", "reel"):
                post_type = "post"

            if not media:
                return render(
                    request,
                    "upload.html",
                    _upload_page_context("Please select a file to upload."),
                )

            # Get file size early for validation
            size = getattr(media, "size", None)
            if not size:
                size = 0

            # FOR REELS: Auto-convert to post if file exceeds reel limit
            # This prevents timeout issues when processing large videos on Render.com
            if post_type == "reel" and size > settings.MAX_REEL_UPLOAD_BYTES:
                post_type = "post"

            # Check post size limit
            if post_type == "post" and size > settings.MAX_POST_UPLOAD_BYTES:
                return render(
                    request,
                    "upload.html",
                    _upload_page_context(
                        "Post file is too large. Max size is "
                        f"{_format_mb(settings.MAX_POST_UPLOAD_BYTES)}. "
                        "Please reduce video quality or duration."
                    ),
                )

            # Quick file type validation (no heavy processing)
            content_type = (getattr(media, "content_type", "") or "").lower()
            name = getattr(media, "name", "") or ""
            ext = os.path.splitext(name)[1].lower()
            video_exts = {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv", ".ogv", ".3gp", ".3gpp"}

            is_video_upload = _is_video_file(name, content_type) or (ext in video_exts)

            # Ensure video files always keep a video extension (helps detection + playback)
            if is_video_upload and ext not in video_exts:
                guessed_ext = mimetypes.guess_extension(content_type) if content_type else ""
                if guessed_ext not in video_exts:
                    guessed_ext = ".mp4"
                base = name[:-len(ext)] if ext else name
                media.name = f"{base}{guessed_ext}"
                name = getattr(media, "name", "") or ""
                ext = os.path.splitext(name)[1].lower()

            # Validate reel uploads
            if post_type == "reel":
                if not is_video_upload:
                    guessed, _ = mimetypes.guess_type(getattr(media, "name", ""))
                    if not (guessed and guessed.startswith("video/")):
                        return render(
                            request,
                            "upload.html",
                            _upload_page_context(
                                "Reel upload only supports video files (mp4, webm, mov, m4v, etc.)."
                            ),
                        )
                # NOTE: Duration check is DISABLED to prevent 502 timeouts on Render.com platform
                # File size check (MAX_REEL_UPLOAD_BYTES) is sufficient for auto-conversion
                # Large videos automatically upload as posts instead

            # Create post with safe error handling
            # Seek to start in case file was read elsewhere
            try:
                media.seek(0)
            except Exception:
                pass

            post = Post.objects.create(
                user=request.user,
                media=media,
                caption=caption,
                type=post_type
            )

        except IOError as exc:
            err_text = "Upload interrupted - file read error. Please try again."
            print(f"[upload] IOError: {exc}")
            return render(request, "upload.html", _upload_page_context(err_text))
        except MemoryError as exc:
            err_text = "Upload too large for current server capacity. Try a smaller file."
            print(f"[upload] MemoryError: {exc}")
            return render(request, "upload.html", _upload_page_context(err_text))
        except Exception as exc:
            err_text = f"Upload failed: {exc.__class__.__name__}"
            try:
                detail = str(exc)
                if detail and len(detail) < 200:
                    err_text = f"{err_text} - {detail}"
            except Exception:
                pass
            print(f"[upload] {err_text}")
            return render(request, "upload.html", _upload_page_context(err_text))

        # Success: Post created
        if _media_debug_enabled():
            try:
                raw_url = post.media.url
            except Exception:
                raw_url = ""
            print(
                "[media-debug][upload] created post",
                {
                    "post_id": post.id,
                    "name": getattr(post.media, "name", ""),
                    "type": post.type,
                    "is_video": post.is_video,
                    "raw_url": raw_url,
                    "media_url": post.media_url,
                    "can_use_cloudinary": getattr(settings, "CAN_USE_CLOUDINARY", False),
                    "cloud_name": getattr(settings, "CLOUDINARY_CLOUD_NAME", ""),
                },
            )

        return redirect("home")

    return render(request, "upload.html", _upload_page_context())


@login_required
@require_POST
def cloudinary_signature(request):
    if not _direct_upload_enabled():
        return JsonResponse({"error": "Direct upload not configured."}, status=400)

    try:
        payload = json.loads((request.body or b"{}").decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = {}

    resource_type = (payload.get("resource_type") or "video").lower()
    if resource_type not in ("video", "image"):
        resource_type = "video"

    raw_params = payload.get("params_to_sign")
    if isinstance(raw_params, dict):
        allowed_keys = {
            "timestamp",
            "folder",
            "resource_type",
            "use_filename",
            "unique_filename",
            "public_id",
            "tags",
            "context",
            "overwrite",
            "invalidate",
            "eager",
            "eager_async",
            "notification_url",
            "chunk_size",
            "upload_preset",
        }
        params_to_sign = {key: raw_params[key] for key in raw_params if key in allowed_keys}
        params_to_sign["resource_type"] = resource_type
        if "timestamp" not in params_to_sign:
            params_to_sign["timestamp"] = int(time.time())
        if "folder" not in params_to_sign:
            params_to_sign["folder"] = f"posts/u{request.user.id}"
        if "use_filename" not in params_to_sign:
            params_to_sign["use_filename"] = "true"
        if "unique_filename" not in params_to_sign:
            params_to_sign["unique_filename"] = "true"
    else:
        timestamp = int(time.time())
        folder = f"posts/u{request.user.id}"
        params_to_sign = {
            "timestamp": timestamp,
            "folder": folder,
            "resource_type": resource_type,
            "use_filename": "true",
            "unique_filename": "true",
        }

    try:
        import cloudinary.utils
        signature = cloudinary.utils.api_sign_request(
            params_to_sign,
            settings.CLOUDINARY_API_SECRET,
        )
    except Exception:
        return JsonResponse({"error": "Cloudinary signing failed."}, status=500)

    return JsonResponse({
        "cloud_name": settings.CLOUDINARY_CLOUD_NAME,
        "api_key": settings.CLOUDINARY_API_KEY,
        "timestamp": params_to_sign.get("timestamp"),
        "signature": signature,
        "folder": params_to_sign.get("folder"),
        "resource_type": resource_type,
        "use_filename": "true",
        "unique_filename": "true",
        "max_bytes": getattr(settings, "MAX_DIRECT_UPLOAD_BYTES", 0),
    })


@login_required
@require_POST
def cloudinary_complete_upload(request):
    try:
        payload = json.loads((request.body or b"{}").decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    public_id = (payload.get("public_id") or "").strip()
    resource_type = (payload.get("resource_type") or "").strip().lower()
    file_format = (payload.get("format") or "").strip().lower()
    file_bytes = payload.get("bytes")
    post_type = (payload.get("post_type") or "post").strip().lower()
    caption = (payload.get("caption") or "").strip()

    if post_type not in ("post", "reel"):
        post_type = "post"
    if not public_id or resource_type not in ("image", "video"):
        return JsonResponse({"error": "Missing upload data."}, status=400)
    if post_type == "reel" and resource_type != "video":
        return JsonResponse({"error": "Reel upload must be a video."}, status=400)

    max_bytes = getattr(settings, "MAX_DIRECT_UPLOAD_BYTES", 0) or 0
    if max_bytes and isinstance(file_bytes, (int, float)) and file_bytes > max_bytes:
        return JsonResponse({"error": "Upload is too large."}, status=400)

    # Auto-convert reels to posts if file is too large for reel storage
    if post_type == "reel" and file_bytes and file_bytes > settings.MAX_REEL_UPLOAD_BYTES:
        post_type = "post"

    if file_format:
        media_name = f"{public_id}.{file_format}"
    else:
        media_name = public_id

    try:
        post = Post.objects.create(
            user=request.user,
            caption=caption,
            type=post_type,
        )
        post.media.name = media_name
        post.save(update_fields=["media"])
    except Exception as exc:
        err_text = f"Upload failed: {exc.__class__.__name__}"
        try:
            detail = str(exc)
            if detail:
                err_text = f"{err_text} - {detail}"
        except Exception:
            pass
        print(f"[cloudinary_complete_upload] {err_text}")
        return JsonResponse({"error": err_text}, status=500)

    return JsonResponse({"ok": True, "redirect": reverse("home")})


@login_required
def upload_story(request):
    if request.method == "POST":
        image_file = request.FILES.get("image") or request.FILES.get("media")
        music_preview_url = (request.POST.get("music_preview_url") or "").strip()
        music_suggestion = (request.POST.get("music_suggestion") or "").strip()[:80]
        music_youtube_url = (request.POST.get("music_youtube_url") or "").strip()
        if music_youtube_url and not music_youtube_url.startswith(("http://", "https://")):
            music_youtube_url = ""
        if not image_file:
            return render(request, "upload_story.html", _story_upload_context(request.user, "Please select an image."))

        image_content_type = (getattr(image_file, "content_type", "") or "").lower()
        if image_content_type and not image_content_type.startswith("image/"):
            return render(request, "upload_story.html", _story_upload_context(request.user, "Only image files are allowed for stories."))

        story_kwargs = {
            "user": request.user,
            "image": image_file,
            "media_type": "image",
            "music": None,
            "filter_name": "none",
            "music_suggestion": music_suggestion,
            "music_source_url": music_youtube_url,
            "caption": "",
            "is_partnership": False,
            "audience": "story",
        }
        if music_preview_url:
            preview_file = _download_music_preview(music_preview_url)
            if preview_file:
                story_kwargs["music"] = preview_file

        Story.objects.create(**story_kwargs)
        return redirect("home")

    return render(request, "upload_story.html", _story_upload_context(request.user))


@login_required
def story_archive(request):
    stories = Story.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "story_archive.html", {"stories": stories})


@login_required
@require_POST
def toggle_story_highlight(request, story_id):
    story = get_object_or_404(Story, id=story_id, user=request.user)
    story.is_highlight = not story.is_highlight
    story.save(update_fields=["is_highlight"])
    return redirect("story_archive")


@login_required
def view_story(request, story_id):
    story = get_object_or_404(Story.objects.select_related("user"), id=story_id)
    is_archive_mode = (
        (request.GET.get("archive") or "").strip() == "1"
        and story.user_id == request.user.id
    )

    if is_archive_mode:
        visible_stories = list(
            Story.objects.filter(user=request.user)
            .select_related("user")
            .order_by("created_at", "id")
        )
    else:
        allowed_user_ids = _story_access_user_ids(request.user)
        if story.user_id not in allowed_user_ids:
            return HttpResponseForbidden("You cannot view this story.")

        active_since = timezone.now() - timedelta(hours=24)
        if story.created_at < active_since:
            return HttpResponseForbidden("This story has expired.")

        visible_stories = list(
            Story.objects.filter(
                user_id__in=allowed_user_ids,
                created_at__gte=active_since
            ).select_related("user").order_by("created_at", "id")
        )

    visible_ids = [s.id for s in visible_stories]
    if story.id not in visible_ids:
        return HttpResponseForbidden("Story not available.")

    current_idx = visible_ids.index(story.id)
    prev_story_id = visible_ids[current_idx - 1] if current_idx > 0 else None
    next_story_id = visible_ids[current_idx + 1] if current_idx < len(visible_ids) - 1 else None

    if not is_archive_mode:
        # Mark all currently active stories from this same user as seen
        # so their ring turns to the seen state after opening one story.
        same_user_active_stories = [
            s for s in visible_stories if s.user_id == story.user_id
        ]
        for s in same_user_active_stories:
            StorySeen.objects.get_or_create(viewer=request.user, story=s)

    current_user_stories = [s for s in visible_stories if s.user_id == story.user_id]
    user_story_ids = [s.id for s in current_user_stories]
    user_story_idx = user_story_ids.index(story.id) if story.id in user_story_ids else 0
    story_viewers = []
    if request.user.id == story.user_id:
        story_viewers = list(
            StorySeen.objects.filter(story=story)
            .exclude(viewer=request.user)
            .select_related("viewer", "viewer__profile")
            .order_by("-seen_at")
        )

    return render(request, "view_story.html", {
        "story": story,
        "story_filter_css": STORY_FILTER_CSS.get(story.filter_name or "none", "none"),
        "prev_story_id": prev_story_id,
        "next_story_id": next_story_id,
        "user_story_ids": user_story_ids,
        "user_story_idx": user_story_idx,
        "is_archive_mode": is_archive_mode,
        "story_viewers": story_viewers,
    })

from django.template.loader import render_to_string

def _user_avatar_url(user):
    try:
        profile = user.profile
    except Exception:
        profile = None

    if profile and getattr(profile, "image", None) and getattr(profile.image, "name", ""):
        if profile.image.name not in ("default.jpg", "default.png"):
            try:
                return profile.image.url
            except ValueError:
                pass

    display_name = user.get_full_name().strip() or user.username or "User"
    initials = "".join([part[0] for part in display_name.split() if part][:2]).upper() or "U"
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='256' height='256' viewBox='0 0 256 256'>"
        "<rect width='256' height='256' fill='#2f8dff'/>"
        "<text x='50%' y='54%' dominant-baseline='middle' text-anchor='middle' "
        "font-family='Segoe UI,Arial,sans-serif' font-size='96' font-weight='700' fill='white'>"
        f"{initials}</text></svg>"
    )
    return f"data:image/svg+xml;utf8,{quote(svg)}"

@login_required
@require_POST
def comment_ajax(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    text = None
    content_type = request.META.get("CONTENT_TYPE", "")
    if "application/json" in content_type:
        try:
            data = json.loads((request.body or b"{}").decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"error": "Invalid JSON payload"}, status=400)
        text = data.get("text")
    else:
        text = request.POST.get("text")

    text = (text or "").strip()
    if not text:
        return JsonResponse({"error": "Empty comment"}, status=400)

    comment = Comment.objects.create(
        user=request.user,
        post=post,
        text=text
    )

    if request.user != post.user:
        Notification.objects.create(
            sender=request.user,
            receiver=post.user,
            notification_type="comment",
            post=post,
        )

    html = render_to_string("single_comment.html", {
        "comment": comment,
        "request": request
    })

    return JsonResponse({
        "html": html
    })


@login_required
@require_POST
def like_ajax(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    like = Like.objects.filter(post=post, user=request.user).first()
    if like:
        like.delete()
        liked = False
    else:
        Like.objects.create(post=post, user=request.user)
        liked = True

        if request.user != post.user:
            Notification.objects.create(
                sender=request.user,
                receiver=post.user,
                notification_type="like",
                post=post,
            )

    return JsonResponse({
        "liked": liked,
        "total_likes": post.likes.count()
    })


@login_required
@require_POST
def save_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    if request.user in post.saved_by.all():
        post.saved_by.remove(request.user)
        saved = False
    else:
        post.saved_by.add(request.user)
        saved = True

    return JsonResponse({
        "saved": saved
    })


@login_required
@require_POST
def share_post_to_follower(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    username = (request.POST.get("username") or "").strip()
    if not username:
        return JsonResponse({"error": "Missing username"}, status=400)

    recipient = get_object_or_404(User, username=username)
    is_follower = Follow.objects.filter(
        follower=recipient,
        following=request.user
    ).exists()
    if recipient != request.user and not is_follower:
        return JsonResponse({"error": "Recipient is not your follower"}, status=403)

    Message.objects.create(
        sender=request.user,
        receiver=recipient,
        content=f"__shared_post__:{post.id}"
    )
    return JsonResponse({"sent": True})


@login_required
@require_GET
def post_share_preview(request, post_id):
    post = get_object_or_404(Post.objects.select_related("user"), id=post_id)
    if post.type == "reel":
        target_url = reverse("reels") + f"?reel={post.id}"
    else:
        target_url = reverse("home") + f"#post-{post.id}"
    return JsonResponse({
        "id": post.id,
        "type": post.type,
        "caption": post.caption or "",
        "media_url": post.media_url,
        "username": post.user.username,
        "profile_url": reverse("profile", args=[post.user.username]),
        "target_url": target_url,
    })


@login_required
def saved_posts(request):
    saved_qs = request.user.saved_posts.select_related("user").order_by("-created_at")
    saved_posts_qs = saved_qs.filter(type="post")
    saved_reels_qs = saved_qs.filter(type="reel")
    return render(request, "saved_posts.html", {
        "saved_items": saved_qs,
        "saved_posts": saved_posts_qs,
        "saved_reels": saved_reels_qs,
        "saved_total": saved_qs.count(),
        "saved_posts_count": saved_posts_qs.count(),
        "saved_reels_count": saved_reels_qs.count(),
    })


@login_required
def liked_reels(request):
    liked_post_ids = Like.objects.filter(
        user=request.user
    ).values_list("post_id", flat=True)
    liked_items = Post.objects.filter(
        id__in=liked_post_ids
    ).select_related("user").order_by("-created_at")
    liked_posts = liked_items.filter(type="post")
    liked_reels_qs = liked_items.filter(type="reel")
    return render(request, "liked_reels.html", {
        "liked_items": liked_items,
        "liked_posts": liked_posts,
        "reels": liked_reels_qs,
        "liked_total": liked_items.count(),
        "liked_posts_count": liked_posts.count(),
        "liked_reels_count": liked_reels_qs.count(),
    })


@login_required
@require_POST
def delete_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if post.user != request.user:
        return JsonResponse({"error": "Not allowed"}, status=403)

    if post.media:
        post.media.delete(save=False)
    post.delete()
    return JsonResponse({"deleted": True})


@login_required
@require_POST
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)

    if comment.user == request.user:
        comment.delete()
        return JsonResponse({"deleted": True})

    return JsonResponse({"error": "Not allowed"}, status=403)

def ping_view(request):
    return HttpResponse("OK")
