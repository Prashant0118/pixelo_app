from django.http import JsonResponse
from django.views.decorators.http import require_GET

from myapp.services.youtube import (
    YouTubeServiceError,
    fetch_home_videos,
    fetch_reels_videos,
)


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
        return JsonResponse({"videos": [], "error": str(exc)}, status=503)
    return JsonResponse({"videos": videos})


@require_GET
def reels_videos(request):
    try:
        videos = fetch_reels_videos(
            max_results=_max_results(request),
            query=_query(request, "educational tutorial learning shorts"),
        )
    except YouTubeServiceError as exc:
        return JsonResponse({"videos": [], "error": str(exc)}, status=503)
    return JsonResponse({"videos": videos})
