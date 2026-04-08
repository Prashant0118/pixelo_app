#!/usr/bin/env bash
set -o errexit

echo "==> Build: Installing dependencies..."
pip install -r requirements.txt

echo "==> Build: Collecting static files..."
python manage.py collectstatic --noinput --no-post-process --clear 2>&1 || true

# If collectstatic didn't work properly, manually copy static files
if [ ! -d "staticfiles/css" ]; then
    echo "==> Fallback: Manually copying static files..."
    mkdir -p staticfiles
    find myapp/static -type f -exec install -D "{}" "staticfiles/{}" \; 2>/dev/null || true
fi

echo "==> Build: Running database migrations..."
python manage.py migrate --noinput
