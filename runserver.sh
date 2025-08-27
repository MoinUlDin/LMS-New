#!/bin/sh
set -e

echo " -> Collecting static files..."
python manage.py collectstatic --noinput

echo " -> Making & applying migrations..."
python manage.py makemigrations --noinput || true
python manage.py migrate --noinput

# Create superuser if ADMIN_EMAIL and ADMIN_PASSWORD are set
if [ -n "$ADMIN_EMAIL" ] && [ -n "$ADMIN_PASSWORD" ]; then
  echo " -> Ensuring superuser $ADMIN_EMAIL exists..."
  python - <<PY
import os
import django
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
email = os.getenv("ADMIN_EMAIL")
pwd = os.getenv("ADMIN_PASSWORD")
username = os.getenv("ADMIN_USERNAME") or (email.split("@")[0] if email else "admin")
if email and not User.objects.filter(email=email).exists():
    User.objects.create_superuser(username=username, email=email, password=pwd)
    print("Superuser created:", email)
else:
    print("Superuser already exists or ADMIN_EMAIL missing.")
PY
fi

echo " -> Starting Gunicorn..."
exec gunicorn lms.wsgi:application --bind 0.0.0.0:80 --workers 3
