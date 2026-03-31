#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
# Run collectstatic without unsupported flags to avoid manage.py errors on Render
python manage.py collectstatic --noinput
python manage.py migrate --noinput
