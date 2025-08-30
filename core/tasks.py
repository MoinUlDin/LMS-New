from celery import shared_task
from .models import IssuedBook, NotificationLog
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail


@shared_task
def check_overdue_books():
    today = timezone.now()
    overdue_books = IssuedBook.objects.filter(
        due_date__lt=today, returned_at__isnull=True)

    for issued in overdue_books:
        user = issued.user
        book = issued.book
        days_overdue = (today - issued.due_date).days

        subject = f"Overdue Book Reminder: {book.title}"
        message = f"Hi {user.username},\n\nYou have an overdue book:\n- Title: {book.title}\n- Due: {issued.due_date.date()}\n- Days Overdue: {days_overdue}\n\nPlease return it ASAP to avoid further fines."

       
        send_mail(subject, message, 'library@noreply.com', [user.email])

        
        NotificationLog.objects.create(user=user, message=message)

        print(f"[EMAIL SENT] To {user.email} - {book.title}")
