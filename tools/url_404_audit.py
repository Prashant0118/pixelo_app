import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

import django
from django.db import OperationalError, ProgrammingError
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import get_resolver
from django.urls.resolvers import URLPattern, URLResolver


def walk_patterns(patterns, prefix=""):
    for item in patterns:
        if isinstance(item, URLPattern):
            route = prefix + str(item.pattern)
            yield "/" + route.lstrip("^").rstrip("$")
        elif isinstance(item, URLResolver):
            yield from walk_patterns(item.url_patterns, prefix + str(item.pattern))


def is_concrete_path(path):
    markers = ["<", "(", "[", "|", "?"]
    return not any(m in path for m in markers)


def main():
    django.setup()

    client = Client()
    client.raise_request_exception = False
    user_model = get_user_model()
    user = None

    try:
        user = (
            user_model.objects.filter(is_superuser=True).first()
            or user_model.objects.filter(is_staff=True).first()
            or user_model.objects.first()
        )
    except (OperationalError, ProgrammingError):
        user = None

    if user:
        client.force_login(user)

    resolver = get_resolver()
    paths = set()

    for raw in walk_patterns(resolver.url_patterns):
        normalized = raw.replace("\\\\", "/")
        if not normalized.startswith("/"):
            normalized = "/" + normalized
        if is_concrete_path(normalized):
            paths.add(normalized)

    # Extra hardcoded routes found in templates/js that should be reachable.
    extras = {
        "/favicon.ico",
        "/saved-posts/",
        "/liked-reels/",
        "/story/archive/",
        "/notifications/",
        "/profile-menu/",
        "/upload/chunk/",
        "/upload/chunk/complete/",
    }
    paths.update(extras)

    bad = []
    for path in sorted(paths):
        try:
            response = client.get(path, follow=False, HTTP_HOST="127.0.0.1")
            if response.status_code == 404:
                bad.append((path, response.status_code))
        except Exception as exc:
            bad.append((path, f"EXC:{exc}"))

    print(f"AUTH_USER={bool(user)}")
    print(f"TOTAL_CHECKED={len(paths)}")
    print(f"BAD_COUNT={len(bad)}")
    for path, code in bad:
        print(f"BAD {path} {code}")


if __name__ == "__main__":
    main()
