from .models import AuditLog, NotificationLog, BookReservation, User
from django.utils import timezone
import datetime

def log_action(user, action_type, description):
    try:
        from core.models import AuditLog
        AuditLog.objects.create(user=user, action_type=action_type, description=description)
    except Exception as e:
        print("Logging skipped (probably during migration):", e)

def log_notification(user, message):
    try:
        NotificationLog.objects.create(user=user, message=message)
    except Exception as e:
        print(f"NotificationLog skipped: {e}")


def cancel_stale_reservations():
    print(f"cancel Stale reservations Called in utils.py")
    threshold = timezone.now() - datetime.timedelta(hours=25)

    user = User.objects.filter(is_superuser=True).first()
    if user is None:
        user = User.objects.first()

    stale_qs = BookReservation.objects.filter(
        status='PENDING',
        reserved_from__lt=threshold
    )
    count = stale_qs.update(status='CANCELLED')

    if count:
        msg = f"Auto-cancelled {count} stale reservation{'s' if count != 1 else ''}."
        log_action(user=user,
                   action_type="RESERVATION CANCELLED",
                   description=msg)
        print(msg)