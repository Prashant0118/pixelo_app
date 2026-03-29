web: daphne -b 0.0.0.0 -p $PORT --access-log - --proxy-headers myproject.asgi:application
release: python manage.py migrate --noinput
