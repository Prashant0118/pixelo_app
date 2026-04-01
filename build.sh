#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
# Avoid WhiteNoise post-processing to prevent missing-file build failures
python manage.py collectstatic --noinput --no-post-process
python manage.py migrate --noinput
