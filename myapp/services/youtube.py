import logging
import re
from hashlib import sha256
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3/"
EDUCATION_CATEGORY_ID = "27"
DEFAULT_QUERY = "educational tutorial learning"
SHORTS_MAX_SECONDS = 60
DEFAULT_CACHE_SECONDS = 15 * 60


class YouTubeServiceError(Exception):
    """Raised when the YouTube API cannot return a usable response."""


@dataclass(frozen=True)
class YouTubeVideo:
    title: str
    thumbnail: str
    videoId: str
    channelName: str
    duration_seconds: int

    def to_public_dict(self):
        return {
            "title": self.title,
            "thumbnail": self.thumbnail,
            "videoId": self.videoId,
            "channelName": self.channelName,
        }


def fetch_home_videos(max_results=12, query=DEFAULT_QUERY):
    return _fetch_educational_videos(
        mode="home",
        max_results=max_results,
        query=query,
        include_shorts=False,
    )


def fetch_reels_videos(max_results=12, query=f"{DEFAULT_QUERY} shorts"):
    return _fetch_educational_videos(
        mode="reels",
        max_results=max_results,
        query=query,
        include_shorts=True,
    )


def _fetch_educational_videos(mode, max_results, query, include_shorts):
    max_results = _clamp_max_results(max_results)
    query_hash = sha256(query.strip().lower().encode("utf-8")).hexdigest()[:16]
    cache_key = f"youtube:{mode}:{max_results}:{query_hash}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    api_key = _api_key()
    if not api_key:
        raise YouTubeServiceError("YOUTUBE_API_KEY is not configured.")

    search_limit = min(50, max(max_results * 4, max_results))
    video_ids = _search_video_ids(api_key=api_key, query=query, max_results=search_limit)
    videos = _fetch_video_details(api_key=api_key, video_ids=video_ids)

    if include_shorts:
        filtered = [video for video in videos if video.duration_seconds < SHORTS_MAX_SECONDS]
    else:
        filtered = [video for video in videos if video.duration_seconds >= SHORTS_MAX_SECONDS]

    payload = [video.to_public_dict() for video in filtered[:max_results]]
    cache.set(cache_key, payload, getattr(settings, "YOUTUBE_API_CACHE_SECONDS", DEFAULT_CACHE_SECONDS))
    return payload


def _api_key():
    return (getattr(settings, "YOUTUBE_API_KEY", "") or "").strip()


def _clamp_max_results(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 12
    return max(1, min(parsed, 25))


def _search_video_ids(api_key, query, max_results):
    params = {
        "part": "snippet",
        "type": "video",
        "q": query or DEFAULT_QUERY,
        "maxResults": max_results,
        "videoCategoryId": EDUCATION_CATEGORY_ID,
        "safeSearch": "strict",
        "key": api_key,
    }
    payload = _get("search", params=params)
    video_ids = []
    seen = set()
    for item in payload.get("items", []):
        video_id = ((item.get("id") or {}).get("videoId") or "").strip()
        if video_id and video_id not in seen:
            seen.add(video_id)
            video_ids.append(video_id)
    return video_ids


def _fetch_video_details(api_key, video_ids: Iterable[str]):
    ids = [video_id for video_id in video_ids if video_id]
    if not ids:
        return []

    params = {
        "part": "snippet,contentDetails",
        "id": ",".join(ids[:50]),
        "key": api_key,
    }
    payload = _get("videos", params=params)
    videos = []
    for item in payload.get("items", []):
        snippet = item.get("snippet") or {}
        content_details = item.get("contentDetails") or {}
        video_id = (item.get("id") or "").strip()
        title = (snippet.get("title") or "").strip()
        if not (video_id and title):
            continue

        videos.append(
            YouTubeVideo(
                title=title,
                thumbnail=_best_thumbnail(snippet.get("thumbnails") or {}),
                videoId=video_id,
                channelName=(snippet.get("channelTitle") or "").strip(),
                duration_seconds=parse_iso8601_duration(content_details.get("duration") or ""),
            )
        )
    return videos


def _get(path, params):
    try:
        response = requests.get(urljoin(YOUTUBE_API_BASE, path), params=params, timeout=8)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        logger.warning("YouTube API request failed: %s", exc)
        raise YouTubeServiceError("Unable to fetch YouTube videos right now.") from exc
    except ValueError as exc:
        raise YouTubeServiceError("YouTube API returned an invalid response.") from exc


def _best_thumbnail(thumbnails):
    for key in ("maxres", "standard", "high", "medium", "default"):
        url = ((thumbnails.get(key) or {}).get("url") or "").strip()
        if url:
            return url
    return ""


def parse_iso8601_duration(value):
    match = re.fullmatch(
        r"P(?:(?P<days>\d+)D)?"
        r"(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?",
        value or "",
    )
    if not match:
        return 0
    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return days * 86400 + hours * 3600 + minutes * 60 + seconds
