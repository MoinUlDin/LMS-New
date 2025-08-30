from django.db import models
from core.models import MemberProfile, Book

# Create your models here.

class WishlistItem(models.Model):
    member = models.ForeignKey(MemberProfile,on_delete=models.CASCADE, related_name="member_wishlist")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="member_wishlisted_by")
    added_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = (("member", "book"),)
        ordering        = ["-added_at"]

    def __str__(self):
        return f"{self.member} → {self.book.title}"


class Notification(models.Model):
    MEMBER_ALERT    = "MEMBER_ALERT"
    RESERVATION     = "RESERVATION"
    ANNOUNCEMENT    = "ANNOUNCEMENT"
    DUE_REMINDER    = "DUE_REMINDER"

    TYPE_CHOICES = [
        (MEMBER_ALERT, "Member-specific alert"),
        (RESERVATION,  "Reservation ready"),
        (ANNOUNCEMENT, "General announcement"),
        (DUE_REMINDER, "Due date reminder"),
    ]
    

    recipient   = models.ForeignKey(MemberProfile, on_delete=models.CASCADE,related_name="member_notifications")
    type        = models.CharField(max_length=20, choices=TYPE_CHOICES)
    message     = models.TextField()
    link_url    = models.URLField(blank=True, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    read        = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.get_type_display()}] {self.recipient}: {self.message[:30]}"
        
        