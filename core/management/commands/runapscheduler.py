# core/management/commands/runapscheduler.py

from datetime import datetime
from django.utils import timezone
from django.conf import settings
from django.core.management.base import BaseCommand
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from core.emailServices import send_due_today_reminders, send_overdue_notices
from core.utils import cancel_stale_reservations

class Command(BaseCommand):
    help = "Runs APScheduler."

    def handle(self, *args, **options):
        tz = timezone.get_current_timezone()  # from TIME_ZONE
        scheduler = BlockingScheduler(timezone=tz)

        now = timezone.now()

        # 1) Reminders: run immediately now, then at 08:00 local every day
        scheduler.add_job(
            send_due_today_reminders,
            trigger=CronTrigger(hour=3, minute=0, timezone=tz),
            # trigger=CronTrigger(minute="*"),
            id="due_today",
            replace_existing=True,
        )
        self.stdout.write(f"Scheduled send_due_today_reminders: will run daily at 08:00")

        
        scheduler.add_job(
            send_overdue_notices,
            trigger=CronTrigger(hour=4, minute=0, timezone=tz),
            # trigger=CronTrigger(minute="*"),
            id="overdue_notices",
            replace_existing=True,
        )
        self.stdout.write(f"Scheduled send_overdue_notices: will run daily at 09:00")
        
        # 3a) cancel_stale_reservations at 00:00 local
        scheduler.add_job(
            cancel_stale_reservations,
            trigger=CronTrigger(hour=0, minute=0, timezone=tz),
            id="cancel_stale_midnight",
            replace_existing=True,
        )
        self.stdout.write("Scheduled cancel_stale_reservations: daily at 00:00")

        # 3b) cancel_stale_reservations at 12:00 local
        scheduler.add_job(
            cancel_stale_reservations,
            trigger=CronTrigger(hour=12, minute=0, timezone=tz),
            # trigger=CronTrigger(minute="*"),
            id="cancel_stale_noon",
            replace_existing=True,
        )
        self.stdout.write("Scheduled cancel_stale_reservations: daily at 12:00")

        self.stdout.write("Scheduler started… (Ctrl+C to stop)")
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown()
            self.stdout.write("Scheduler stopped.")
