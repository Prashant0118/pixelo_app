#!/usr/bin/env bash
set -o errexit

echo "==> Startup: Running migrations with retry..."
max_attempts=5
attempt=1
until python manage.py migrate --noinput; do
  if [ "$attempt" -ge "$max_attempts" ]; then
    echo "Migration failed after ${max_attempts} attempts."
    exit 1
  fi
  echo "Migration attempt ${attempt} failed. Retrying in 5s..."
  attempt=$((attempt + 1))
  sleep 5
done
python manage.py collectstatic --noinput --no-post-process 2>/dev/null || true


# Create superuser safely using env variables
python manage.py shell <<EOF
import os
from django.contrib.auth import get_user_model
User = get_user_model()

username = os.getenv("DJANGO_SUPERUSER_USERNAME")
password = os.getenv("DJANGO_SUPERUSER_PASSWORD")
email = os.getenv("DJANGO_SUPERUSER_EMAIL")

if username and password and not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
EOF

# Optional: normalize stored media paths once during deploy
if [ "${RUN_MEDIA_PATH_FIX}" = "1" ]; then
  python manage.py fix_media_paths
fi

# Optional: migrate existing local media records into configured cloud storage
if [ "${RUN_MEDIA_MIGRATION}" = "1" ]; then
  python manage.py migrate_reel_media --all-posts
fi

# Optional: clear stale/broken media references so templates don't emit 404 URLs
if [ "${RUN_CLEAR_MISSING_MEDIA}" = "1" ]; then
  clear_args="--clear-invalid-names"
  if [ "${RUN_CLEAR_MISSING_MEDIA_REMOTE}" = "1" ]; then
    clear_args="$clear_args --check-remote"
  fi
  python manage.py clear_missing_media $clear_args
fi

# Start server
daphne -b 0.0.0.0 -p ${PORT} myproject.asgi:application
