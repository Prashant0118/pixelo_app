#!/usr/bin/env bash
set -o errexit

python manage.py migrate --noinput

# Start ASGI server (channels/daphne)
daphne -b 0.0.0.0 -p ${PORT} myproject.asgi:application
