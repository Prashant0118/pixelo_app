#!/usr/bin/env bash
set -o errexit

python manage.py migrate --noinput
python manage.py collectstatic --noinput




# Create superuser safely using env variables
python manage.py shell <<EOF
import os
from django.contrib.auth import get_user_model
User = get_user_model()

username = os.getenv("Prashant_kasuhik")
password = os.getenv("pkt0115n")
email = os.getenv("prashantkasuhik118@gmail.com")

if username and password and not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
EOF
# Start ASGI server (channels/daphne)
daphne -b 0.0.0.0 -p ${PORT} myproject.asgi:application