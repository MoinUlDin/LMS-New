from rest_framework import serializers
from .models import WishlistItem, Notification, Book
from books.books_serializers import BookDetailSerializer

class WishlistItemSerializer(serializers.ModelSerializer):
    book = BookDetailSerializer(read_only=True)
    book_id = serializers.PrimaryKeyRelatedField(
        queryset=Book.objects.all(), source="book", write_only=True
    )

    class Meta:
        model = WishlistItem
        fields = ["id", "book", "book_id", "added_at"]

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Notification
        fields = ["id", "type", "message", "link_url", "created_at", "read"]
