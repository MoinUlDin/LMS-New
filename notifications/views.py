from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import WishlistItem, Notification
from .serializers import WishlistItemSerializer, NotificationSerializer
from django.db.models import QuerySet
from django.db import IntegrityError
from rest_framework.exceptions import ValidationError

class WishlistViewSet(viewsets.ModelViewSet):
    serializer_class = WishlistItemSerializer
    permission_classes = [IsAuthenticated]

    
    def get_queryset(self) -> QuerySet:
        user = self.request.user
        # If the user has no .profile, return an empty queryset
        if not hasattr(user, "profile"):
            return WishlistItem.objects.none()
        return WishlistItem.objects.filter(member=user.profile)

    def perform_create(self, serializer):
        user = self.request.user
        if not hasattr(user, "profile"):
            # refuse to create if there's no profile
            raise ValidationError({"detail": "You must have a profile to add wishlist items."})

        profile = user.profile
        try:
            serializer.save( member=profile)
        except IntegrityError:
            # now ValidationError is in scope
            raise ValidationError({"detail": "This book is already in your wishlist."})
        
    def  post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user.profile)
        if self.request.query_params.get("unread") == "true":
            qs = qs.filter(read=False)
        return qs

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        notif = self.get_object()
        notif.read = True
        notif.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        Notification.objects.filter(
            recipient=request.user.profile, read=False
        ).update(read=True)
        return Response(status=status.HTTP_204_NO_CONTENT)
