from django.conf import settings
import asyncio
from django.http import HttpResponse
from asgiref.sync import iscoroutinefunction, markcoroutinefunction


class ClientDisconnectMiddleware:
    """
    Gracefully handle client disconnects/timeouts under ASGI.
    Instead of surfacing asyncio.CancelledError as a 500-style traceback,
    return a non-standard 499 (Client Closed Request) response.
    """

    sync_capable = True
    async_capable = True

    def __init__(self, get_response):
        self.get_response = get_response
        self._is_async = iscoroutinefunction(get_response)
        if self._is_async:
            markcoroutinefunction(self)

    def _cancelled_response(self):
        return HttpResponse("Client Closed Request", status=499)

    def __call__(self, request):
        if self._is_async:
            return self.__acall__(request)
        try:
            return self.get_response(request)
        except asyncio.CancelledError:
            return self._cancelled_response()

    async def __acall__(self, request):
        try:
            return await self.get_response(request)
        except asyncio.CancelledError:
            return self._cancelled_response()


class AllowFrameAncestorsMiddleware:
    """Middleware to add a Content-Security-Policy frame-ancestors header
    when `ALLOW_FRAMING_FROM` is set in settings (list of origins or 'self').

    Example env: ALLOW_FRAMING_FROM="https://example.com https://partner.example"
    """

    def __init__(self, get_response):
        self.get_response = get_response
        allowed = getattr(settings, "ALLOW_FRAMING_FROM", None) or []
        if isinstance(allowed, str):
            allowed = [allowed]
        self.allowed = [a for a in allowed if a]

    def __call__(self, request):
        response = self.get_response(request)

        if not self.allowed:
            return response

        # Normalize entries: accept 'self' or scheme://host values.
        normalized = []
        for a in self.allowed:
            a = a.strip()
            if not a:
                continue
            if a in ("'self'", "self"):
                normalized.append("'self'")
            elif a.startswith("'") and a.endswith("'"):
                normalized.append(a)
            elif "://" in a:
                normalized.append(a)
            else:
                # Assume https if scheme not provided
                normalized.append(f"https://{a}")

        if normalized:
            header_value = "frame-ancestors " + " ".join(normalized) + ";"
            # If a CSP header already exists, append the directive to it.
            existing = response.get("Content-Security-Policy")
            if existing:
                # Avoid duplicate directive
                if "frame-ancestors" not in existing:
                    response["Content-Security-Policy"] = existing.rstrip(";") + "; " + header_value
            else:
                response["Content-Security-Policy"] = header_value

        # If a single explicit origin is allowed, provide minimal CORS headers
        # for upload endpoints so cross-origin POSTs from that origin succeed.
        allowed_origins = [a for a in normalized if a and a != "'self'" and "://" in a]
        single_origin = allowed_origins[0] if len(allowed_origins) == 1 else None
        if single_origin and request.path.startswith("/upload"):
            response.setdefault("Access-Control-Allow-Origin", single_origin)
            response.setdefault("Access-Control-Allow-Credentials", "true")
            if request.method == "OPTIONS":
                response.setdefault("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                response.setdefault(
                    "Access-Control-Allow-Headers",
                    "Content-Type, X-CSRFToken, Authorization, X-Requested-With",
                )

        return response
