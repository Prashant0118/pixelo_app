#!/usr/bin/env bash
set -o errexit

python manage.py migrate --noinput





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

# Start server
daphne -b 0.0.0.0 -p ${PORT} myproject.asgi:application
