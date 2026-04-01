#!/usr/bin/env bash
set -o errexit

echo "==> Build: using build.sh with no-post-process collectstatic"
pip install -r requirements.txt
# Avoid WhiteNoise post-processing to prevent missing-file build failures
python manage.py collectstatic --noinput --no-post-process --clear
python manage.py migrate --noinput
