# core/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from django_apscheduler.jobstores import DjangoJobStore
from django.utils import timezone
from core.models import BookReservation
import datetime
from django.conf import settings

# configure a thread‐pool executor so multiple emails can fly in parallel:
jobstores = {
    'default': DjangoJobStore(),
}
executors = {
    "default": ThreadPoolExecutor(max_workers=10),
}

job_defaults = {
    "coalesce": False,     # don’t collapse multiple pending runs
    "max_instances": 3,    # allow up to 3 simultaneous runs of the same job
}


scheduler = BackgroundScheduler(
    executors=executors,
    job_defaults=job_defaults,
    timezone=settings.TIME_ZONE,
)
scheduler.start()
