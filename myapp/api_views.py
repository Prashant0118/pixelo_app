from django.http import JsonResponse
from django.views.decorators.http import require_GET
import logging

from myapp.services.youtube import (
    YouTubeServiceError,
    fetch_home_videos,
    fetch_reels_videos,
)

logger = logging.getLogger(__name__)


def _max_results(request):
    return request.GET.get("max_results") or request.GET.get("limit") or 12


def _query(request, default):
    return (request.GET.get("q") or default).strip()


@require_GET
def home_videos(request):
    try:
        videos = fetch_home_videos(
            max_results=_max_results(request),
            query=_query(request, "educational tutorial learning"),
        )
    except YouTubeServiceError as exc:
        # Return empty list (200) so frontend can continue to render other content.
        logger.warning("YouTube service error for home_videos: %s", exc)
        return JsonResponse({"videos": [], "error": str(exc)})
    return JsonResponse({"videos": videos})


@require_GET
def reels_videos(request):
    try:
        videos = fetch_reels_videos(
            max_results=_max_results(request),
            query=_query(request, "educational tutorial learning shorts"),
        )
    except YouTubeServiceError as exc:
        # Return empty list (200) so frontend can continue to render other content.
        logger.warning("YouTube service error for reels_videos: %s", exc)
        return JsonResponse({"videos": [], "error": str(exc)})
    return JsonResponse({"videos": videos})
