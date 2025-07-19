#!/bin/sh

python manage.py collectstatic --no-input
python manage.py makemigrations
python manage.py migrate
python manage.py runapscheduler &
# gunicorn lms.wsgi --bind=0.0.0.0:80

 exec gunicorn lms.wsgi:application \
   --bind 0.0.0.0:3000 \
   --workers 3