from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q, UniqueConstraint
from django.conf import settings
from decimal import Decimal, ROUND_HALF_UP


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_USER = "SUPER USER", "Super User"
        MANAGER = "MANAGER", "Library Manager"
        MEMBER = "MEMBER", "Student/Faculty"
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.SUPER_USER)
    is_verified = models.BooleanField(default=False)
    is_declined = models.BooleanField(default=False)
    is_defaulter = models.BooleanField(default=False)
    profile_photo = models.ImageField(
        upload_to='profile_photos/', blank=True, null=True)

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'SUPER_USER')
        return self.create_user(username, email, password, **extra_fields)

    def __str__(self):
        return f"{self.username} - {self.role}"


class Category(models.Model):
    name = models.CharField(max_length=100)
    image = models.ImageField(
        upload_to='category_images/', blank=True, null=True)

    def __str__(self):
        return self.name


class Language(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


def get_today_date():
    return timezone.now().date()


class Book(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('WRITE_OFF', 'Write-off'),
        ('LOST', 'Lost'),
    ]

    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    isbn = models.CharField(max_length=13, unique=True)
    department = models.ForeignKey(
        'Department', on_delete=models.SET_NULL, null=True, blank=True)
    category = models.ForeignKey(
        'Category', on_delete=models.SET_NULL, null=True
    )
    language = models.ForeignKey(
        'Language', on_delete=models.SET_NULL, null=True)
    publisher = models.CharField(max_length=255, default='Unknown')
    edition = models.CharField(max_length=50, default='1st')
    total_copies = models.PositiveIntegerField(
    )
    available_copies = models.PositiveIntegerField(
        null=True, blank=True, default=0)
    rack_no = models.CharField(max_length=50, default='1')
    shelf_location = models.CharField(max_length=100, default='Main Shelf')
    date_of_entry = models.DateField(default=get_today_date)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='ACTIVE'
    )
    status_reason = models.TextField(blank=True, null=True)
    price = models.DecimalField(
        max_digits=8, decimal_places=2, default=0.00, blank=True, null=True)
    brief_description = models.TextField(max_length=100, blank=True)
    detailed_description = models.TextField(blank=True, null=True)
    cover_photo = models.ImageField(
        upload_to='book_covers/', blank=True, null=True)
    ebook_file = models.FileField(upload_to='ebooks/', blank=True, null=True)

    # def save(self, *args, **kwargs):
    #     if self.status in ['WRITE_OFF', 'LOST'] and self.available_copies > 0:
    #         self.available_copies -= 1
    #     super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.isbn})"


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class SessionSettings(models.Model):
    session_range = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.session_range


class MemberProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="profile")
    first_name = models.CharField(max_length=100, blank=True, null=True)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    profile_photo = models.ImageField(
        upload_to='profile_photos/', blank=True, null=True)
    class_name = models.CharField(max_length=50, blank=True, null=True)
    section = models.CharField(max_length=50, blank=True, null=True)
    father_first_name = models.CharField(max_length=100, blank=True, null=True)
    father_last_name = models.CharField(max_length=100, blank=True, null=True)
    is_defaulter = models.BooleanField(default=False)
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True)
    session = models.ForeignKey(
        SessionSettings, on_delete=models.SET_NULL, null=True, blank=True)
    registration_id = models.CharField(
        max_length=50, unique=True, null=True, blank=True)
    member_id = models.CharField(max_length=20, unique=True, default='unknown')
    roll_no = models.CharField(max_length=50, default=1)
    SHIFT_CHOICES = [
        ('DAY', 'Day'),
        ('EVENING', 'Evening')
    ]
    shift = models.CharField(
        max_length=10, choices=SHIFT_CHOICES, default='DAY')
    home_address = models.TextField(blank=True, null=True)
    emergency_contact = models.CharField(max_length=15, blank=True, null=True)
    library_membership_id = models.CharField(
        max_length=50, unique=True, blank=True, null=True)
    mobile_number = models.CharField(max_length=15)
    cnic = models.CharField(max_length=15, blank=True, null=True)
    security_fee = models.DecimalField(
        max_digits=8, decimal_places=2, default=0.00)
    payment_proof = models.ImageField(
        upload_to='payment_proofs/', blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.member_id}"


class ManagerProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="manager_profile")
    profile_photo = models.ImageField(
        upload_to='profile_photos/', blank=True, null=True)
    member_id = models.CharField(max_length=50, unique=True)
    contact_number = models.CharField(max_length=15, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.member_id}"


def get_due_date():
    return (timezone.now() + timedelta(days=14)).date()


class BookIssuance(models.Model):
    STATUS_CHOICES = [
        ('ISSUED', 'Issued'),
        ('RETURNED', 'Returned'),
        ('OVERDUE', 'Overdue'),
    ]
    returned_at = models.DateField(null=True, blank=True)
    book = models.ForeignKey(
        'Book', on_delete=models.CASCADE, related_name='issues')
    member = models.ForeignKey(
        'User', on_delete=models.CASCADE, related_name='issued_books')
    issue_date = models.DateField(default=get_today_date)
    due_date = models.DateField(default=get_due_date)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='ISSUED')
    fine_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Issue #{self.id} - {self.book.title} to {self.member.username}"


class Fine(models.Model):
    issued_book = models.OneToOneField(BookIssuance, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    cash_in_hand = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    collected_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0.00, blank=True, null=True
    )
    collected = models.BooleanField(default=False)
    discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    remaining_fines = models.DecimalField(
        max_digits=15, decimal_places=2,
        editable=False,
        default=Decimal("0.00")
    )
    
    def save(self, *args, **kwargs):

        collected = self.collected_amount or Decimal("0.00")
        disc = self.discount or Decimal("0.00")

        raw_remaining = self.amount - collected - disc

        if raw_remaining < 0:
            raw_remaining = Decimal("0.00")

        self.remaining_fines = raw_remaining.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if self.remaining_fines == Decimal("0.00"):
            self.collected = True

        super().save(*args, **kwargs)


    def __str__(self):
        return f"Fine for {self.issued_book.member.username} - ${self.amount}"


class NotificationLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification to {self.user.username} at {self.sent_at}"


class NotificationSettings(models.Model):
    on_book_issue             = models.BooleanField(default=False)
    on_due_date               = models.BooleanField(default=False)
    on_reservation_request    = models.BooleanField(default=False)
    on_fine_imposition        = models.BooleanField(default=False)

    on_fine_collection        = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Notification Settings"
        verbose_name_plural = "Notification Settings"

    def __str__(self):
        return "Global Notification Settings"


class BookRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected')
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True, null=True)
    isbn = models.CharField(max_length=13, blank=True, null=True)
    reason = models.TextField()
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='PENDING')
    requested_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} - {self.user.username} ({self.status})"


class AuditLog(models.Model):
    ACTION_TYPES = [
        ('ISSUE', 'Book Issued'),
        ('RETURN', 'Book Returned'),
        ('FINE', 'Fine Applied'),
        ('ROLE_CHANGE', 'User Role Changed'),
        ('REQUEST', 'Book Request'),
        ('LOGIN', 'User Login'),
    ]
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        # only generate the "view" permission
        default_permissions = ('view',)

    def __str__(self):
        return f"[{self.action_type}] {self.user} @ {self.timestamp}"


class BookReservation(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('FULFILLED', 'Fulfilled'),
        ('ISSUED', 'Issued'),
        ('CANCELLED', 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    reserved_at = models.DateTimeField(auto_now_add=True)
    reserved_from = models.DateTimeField(null=True, blank=True)
    reserved_to   = models.DateTimeField(null=True, blank=True)
    pickup_duration = models.PositiveSmallIntegerField(default=2)  # in days
    notes = models.TextField(blank=True)
    agreed = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')

    
    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["user", "book"],
                condition=Q(status="PENDING"),
                name="unique_pending_reservation_per_user_book"
            )
        ]
    def __str__(self):
        return f"{self.book.title} - {self.user.username} ({self.status})"


class LibrarySettings(models.Model):
    # General Settings
    library_name = models.CharField(max_length=255, default="My Library")
    logo = models.ImageField(upload_to='logos/', null=True, blank=True)
    favicon = models.ImageField(
        upload_to='favicon/', null=True, blank=True)
    theme = models.CharField(max_length=10, choices=[(
        'light', 'Light'), ('dark', 'Dark')], default='light')
    timezone = models.CharField(max_length=100, default='Asia/Karachi')
    date_format = models.CharField(max_length=20, choices=[(
        'DD/MM/YYYY', 'DD/MM/YYYY'), ('MM/DD/YYYY', 'MM/DD/YYYY')])
    time_format = models.CharField(max_length=10, choices=[
                                   ('12hr', '12 Hour'), ('24hr', '24 Hour')])
    max_books_per_member = models.PositiveIntegerField(
        default=3, help_text="Maximum number of books a member can issue.")
    max_issue_duration = models.IntegerField(default=14)
    fine_per_day = models.DecimalField(max_digits=6, decimal_places=2, default=10.00)
    low_stock_threshold =  models.SmallIntegerField(default=3)

    rack_number_format = models.CharField(
        max_length=50, default='KFGC-000', help_text="Format like PREFIX-000 (e.g., KFGC-000)")
    member_id_format = models.CharField(
        max_length=50, default='MBR-2025-000', help_text="Format like PREFIX-YYYY-000")
    frontend_url = models.URLField(
        max_length=200, default='http://localhost:3000', help_text="URL of the frontend application.")
    class Meta:
        verbose_name = "Library Setting"
        verbose_name_plural = "Library Settings"
        default_permissions = ('view', 'change')

        
    def __str__(self):
        return f"Library Settings for {self.library_name}"


class Module(models.Model):
    name = models.CharField(max_length=100)


class Feature(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='features')
    name = models.CharField(max_length=100)


class RolePermission(models.Model):
    ROLE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('SUPER USER', 'Super User'),
        ('MANAGER', 'Manager'),
        ('MEMBER', 'Member'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    feature = models.ForeignKey(Feature, on_delete=models.CASCADE)
    can_view = models.BooleanField(default=False)
    can_add = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    

# Dummy Model to register view in permissions group
class SystemFeature(models.Model):
    class Meta:
        managed = False
        permissions = [
            ("view_dashboard_summary", "Can view dashboard summary"),
            ("view_reports", "Can view all members"),
            ("view_members", "Can view all members"),
            ("add_members", "Can view all members"),
            ("change_members", "Can view all members"),
            ("view_book_report", "Can view book reports"),
            ("view_member_report", "Can view member reports"),
            ("view_financial_report", "Can view financial reports"),
        ]
        

