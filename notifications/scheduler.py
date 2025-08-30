# import datetime
# from apscheduler.schedulers.background import BackgroundScheduler
# from django.utils import timezone
# from core.models import BookIssuance
# from .models import Notification

# def send_due_reminders():
#     today  = timezone.now().date()
#     # remind for books due tomorrow
#     target = today + datetime.timedelta(days=1)
#     issues = BookIssuance.objects.filter(
#         returned_at__isnull=True,
#         due_date=target
#     ).select_related("member__profile", "book")
#     for iss in issues:
#         member_profile = iss.member.profile
#         msg = f"Your book “{iss.book.title}” is due on {iss.due_date:%Y-%m-%d}."
#         Notification.objects.create(
#             recipient=member_profile,
#             type=Notification.DUE_REMINDER,
#             message=msg,
#             link_url=f"/dashboard/books/{iss.book.id}/",
#         )

# def start():
#     scheduler = BackgroundScheduler()
#     # run send_due_reminders every day at 8am
#     scheduler.add_job(
#         send_due_reminders,
#         trigger="cron",
#         hour=8,
#         minute=0,
#         id="due_reminders"
#     )
#     scheduler.start()
