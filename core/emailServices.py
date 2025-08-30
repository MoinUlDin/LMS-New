from celery import shared_task
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
User = get_user_model()
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .utils import log_notification
from core.models import BookIssuance, LibrarySettings, NotificationSettings, BookReservation
import datetime
import time
import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def send_templated_email(
    template_path: str,
    subject: str,
    to_emails: list,
    context: dict = None,
    from_email: str = None,
    attempts: int = 5,
    initial_backoff: int = 10,
) -> bool:
    """
    Renders the given template (e.g. "emails/verification.html") with context,
    sends a multi-part (text+HTML) email to to_emails.
    Returns True on success, False if all retries fail.
    """
    from_email = from_email or settings.DEFAULT_FROM_EMAIL
    context = context or {}

    # 1) Render the full, standalone HTML template (no {% extends %> or blocks)
    html_content = render_to_string(template_path, context)

    # 2) Create a plain-text version by stripping HTML tags
    text_content = strip_tags(html_content)

    # 3) Build the EmailMultiAlternatives
    email_message = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_email,
        to=to_emails,
    )
    email_message.attach_alternative(html_content, "text/html")

    # 4) Try sending with exponential backoff
    backoff = initial_backoff
    for attempt in range(1, attempts + 1):
        try:
            email_message.send(fail_silently=False)
            return True
        except Exception as exc:
            logger.warning(
                f"[EmailRetry] Attempt {attempt}/{attempts} failed: {exc}; retrying in {backoff}s"
            )
            if attempt == attempts:
                logger.error(
                    "[EmailRetry] All attempts exhausted; giving up on email.",
                    exc_info=True,
                )
                return False
            time.sleep(backoff)
            backoff *= 2

    return False  # (should never reach here)


# def send_email_with_retry(subject, message, recipient_list,
#                           from_email=None, attempts=5, backoff=10):
#     """
#     Try to send the email up to `attempts` times,
#     sleeping `backoff` seconds (x2 each retry) on failure.
#     """
#     from_email = from_email or settings.DEFAULT_FROM_EMAIL
#     for i in range(1, attempts + 1):
#         try:
#             send_mail(
#                 subject,
#                 message,
#                 from_email,
#                 recipient_list,
#                 fail_silently=False,
#             )
#             return True
#         except Exception as exc:
#             logger.warning(
#                 f"Email send failed ({i}/{attempts}), retrying in {backoff}s: {exc}"
#             )
#             if i == attempts:
#                 logger.error("All retries exhausted; giving up on email.", exc_info=True)
#                 return False
#             time.sleep(backoff)
#             backoff *= 2

def send_welcome_email(user_id, raw_password):
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.error(f"send_welcome_email: user {user_id} does not exist.")
        return False

    frontendUrl=settings.FRONTEND_URL
    login_url = f"{frontendUrl}"

    subject = "Welcome to Library Management System"
    template_path = "emails/welcome.html"

    context = {
        "user": user,
        "raw_password": raw_password,
        "login_url": login_url,
    }

    success = send_templated_email(
        template_path,
        subject=subject,
        to_emails=[user.email],
        context=context,
    )
    if success:
        msg = f"Welcome email sent to {user.email}"
        log_notification(user=user, message=msg)
        logger.info(msg)
    else:
        logger.info('failed to send Welcome email')
    return success
          
def send_account_approved_notice(user_id):
    """
    Fetches the User, builds a login URL, and sends an approval-notice
    email using the standalone template at emails/account_approved.html.
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.error(f"send_account_approved_notice: User {user_id} does not exist.")
        return False


    login_url = settings.FRONTEND_URL

    subject = "Your account has been approved"
    template_path = "emails/account_approved.html"

    context = {
        "user": user,
        "login_url": login_url,
    }

    success = send_templated_email(
        template_path=template_path,
        subject=subject,
        to_emails=[user.email],
        context=context,
    )

    if success:
        msg = f"Account-approved email sent to {user.email}"
        log_notification(user=user, message=msg)
        logger.info(msg)
    else:
        logger.error(f"Failed to send account-approved email to {user.email}")
    return success 
          
def send_password_reset_link(user_id, reset_url):
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.error(f"send_password_reset_link: User {user_id} does not exist.")
        return False

    subject = "Reset Your Library Management System Password"
    template_path = "emails/password_reset.html"  

    context = {
        "user": user,
        "reset_url": reset_url,
    }

    success = send_templated_email(
        template_path,
        subject=subject,
        to_emails=[user.email],
        context=context,
    )
    if success:
        msg = f"Password reset email sent to {user.email}"
        log_notification(user=user, message=msg)
        logger.info(msg)
    else:
        logger.error(f"Failed to send password reset email to {user.email}")
    return success      

def send_verification_email(user_id, verify_url):
    user = User.objects.get(pk=user_id)
    subject = "Verify Your Email Address"
    template_path = "emails/verification.html"
    context = {
        "user": user,
        "verify_url": verify_url,
    }

    print(f'\n\n Sending Email for email verifications\n')
    success =  send_templated_email(
        template_path=template_path,
        subject=subject,
        to_emails=[user.email],
        context=context,
    )
    if success:
        msg = f'Verification email sent to {user.email}'
        log_notification(user=user, message=msg)
        logger.info(msg)
    else:
        msg = f'Error sending verification email sent to {user.email}'
        logger.info(msg)
    # send_email_with_retry(subject, message, [user.email])        

def send_reservation_fulfill_email(reservation_id):
    """
    Pulls the BookReservation and sends the 'your hold is ready' message
    using the stand-alone HTML template at emails/reservation_fulfill.html.
    """
    print(f"[Scheduler] send_reservation_fulfill_email({reservation_id})")
    try:
        res = BookReservation.objects.get(pk=reservation_id)
    except BookReservation.DoesNotExist:
        # nothing to do
        return False

    user = res.user
    # Format reserved_from as a human-readable string
    reserved_date = res.reserved_from.strftime("%B %d, %Y at %H:%M")
    # Deadline is 24 hours after reserved_from
    pickup_deadline = res.reserved_from + datetime.timedelta(hours=24)
    deadline_str = pickup_deadline.strftime("%B %d, %Y at %H:%M")

    # LibrarySettings to get library_name
    obj = LibrarySettings.objects.first()
    library_name = obj.library_name if obj else "Library"

    subject = "Your reservation is ready for pickup"
    template_path = "emails/reservation_fulfill.html"

    context = {
        "user": user,
        "book_title": res.book.title,
        "reserved_date": reserved_date,
        "deadline_str": deadline_str,
        "library_name": library_name,
    }

    success = send_templated_email(
        template_path,
        subject=subject,
        to_emails=[user.email],
        context=context,
    )
    if success:
        logger.info(f"Sent reservation‐fulfill email to {user.email}")
        log_notification(user=user, message=f"Sent reservation‐fulfill email to {user.email}")
    else:
        logger.error(f"Failed to send reservation‐fulfill email to {user.email}")

    return success

def send_due_today_reminders():
    """
    Send “due today” reminders for all books that are due today (status = ISSUED).
    Uses the standalone template at emails/due_today_reminder.html.
    """
    today = timezone.localdate()
    notification = NotificationSettings.objects.first()
    if notification is not None and not notification.on_due_date:
        # If notifications for due_date are disabled, skip
        return

    library_obj = LibrarySettings.objects.first()
    library_name = library_obj.library_name if library_obj else "Library"

    for issue in BookIssuance.objects.filter(due_date=today, status="ISSUED"):
        member = issue.member
        book = issue.book

        subject = f"Reminder: “{book.title}” is due today"
        template_path = "emails/due_today_reminder.html"

        context = {
            "user": member,
            "book_title": book.title,
            "today": today.strftime("%B %d, %Y"),
            "library_name": library_name,
        }


        success = send_templated_email(
            template_path,
            subject=subject,
            to_emails=[member.email],
            context=context,
        )
        if success:
            log_notification(user=member, message="Due-today reminder sent to {member.email}")
            logger.info(f"Due-today reminder sent to {member.email}")
        else:
            logger.error(f"Failed to send due-today reminder to {member.email}")

def send_overdue_notices():
    """
    Find all issued books whose due_date < today and not yet returned,
    update status to OVERDUE, calculate fine, save & send an email using
    emails/overdue_notice.html.
    """
    notification, _ = NotificationSettings.objects.get_or_create()

    # 2) If “on_fine_imposition” is disabled, bail out
    if not notification.on_fine_imposition:
        return

    # 3) Ensure there’s always exactly one LibrarySettings row
    library_obj, _ = LibrarySettings.objects.get_or_create()

    daily_fine_rate = float(library_obj.fine_per_day or 10)
    library_name = library_obj.library_name or "Library"
    today = timezone.localdate()

    # 1) Filter: due_date < today AND returned_at is null
    overdue_qs = BookIssuance.objects.filter(
        due_date__lt=today,
        returned_at__isnull=True
    )

    for issue in overdue_qs:
        member = issue.member
        book = issue.book

        # 2) Compute days overdue & fine
        days_over = (today - issue.due_date).days
        fine_amount = days_over * daily_fine_rate

        # 3) Persist status/fine
        issue.status = "OVERDUE"
        issue.fine_amount = fine_amount
        issue.save(update_fields=["status", "fine_amount"])

        # 4) Email subject & template
        subject = f"Overdue Notice: “{book.title}” is {days_over} day(s) late"
        template_path = "emails/overdue_notice.html"

        context = {
            "user": member,
            "book_title": book.title,
            "issue_date": issue.issue_date.strftime("%B %d, %Y"),
            "due_date": issue.due_date.strftime("%B %d, %Y"),
            "days_over": days_over,
            "fine": f"{fine_amount:.2f}",
            "library_name": library_name,
        }

        success = send_templated_email(
            template_path,
            subject=subject,
            to_emails=[member.email],
            context=context,
        )
        if success:
            msg = f"Overdue notice sent to {member.email}"
            log_notification(user=member, message=msg)
            logger.info(msg)
        else:
            logger.error(f"Failed to send overdue notice to {member.email}")

def send_book_issue_notification(issue_id):
    """
    Lookup the issuance, build the context, and send with the HTML template
    at emails/book_issue_notification.html.
    """
    print("\n[Scheduler] Sending book-issue notification…")
    try:
        issue = BookIssuance.objects.select_related('member', 'book').get(pk=issue_id)
    except BookIssuance.DoesNotExist:
        logger.error(f"IssuedBook #{issue_id} not found, cannot send notification.")
        return False

    member = issue.member
    book = issue.book

    lib_settings = LibrarySettings.objects.first()
    library_name = lib_settings.library_name if lib_settings else "Your Library"

    subject = f"{library_name}: Book Issued — {book.title}"
    template_path = "emails/book_issue_notification.html"

    # Compute author if available (might be an empty string if no author field)
    author = book.author if hasattr(book, "author") else ""

    context = {
        "user": member,
        "book_title": book.title,
        "author": author,
        "issue_date": issue.issue_date.strftime("%B %d, %Y"),
        "due_date": issue.due_date.strftime("%B %d, %Y"),
        "library_name": library_name,
    }

    success = send_templated_email(
        template_path,
        subject=subject,
        to_emails=[member.email],
        context=context,
    )
    if success:
        msg = f"Book issue notification sent to {member.email}"
        log_notification(user=member, message=msg)
        logger.info(msg)
    else:
        logger.error(f"Failed to send book issue notification to {member.email}")
    return success

def send_manger_activation_link(user_id, raw_password):
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.error(f"send_welcome_email: user {user_id} does not exist.")
        return False
    frontendUrl=settings.FRONTEND_URL
    login_url = f"{frontendUrl}"

    template_path = "emails/welcome.html"
    subject = "Your Manager Account Login Credentials"
    context = {
        "user": user,
        "raw_password": raw_password,
        "login_url": login_url,
    }
    success = send_templated_email(
        template_path,
        subject=subject,
        to_emails=[user.email],
        context=context,
    )
    if success:
        msg = f"Welcome email sent to Manager with credentials Email: {user.email}"
        log_notification(user=user, message=msg)
        logger.info(msg)
    else:
        print("Failed to send welcome email to", user.email)
    return success


