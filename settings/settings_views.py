from decimal import Decimal, InvalidOperation
import random
from core import permissions
from core.models import Feature, LibrarySettings, MemberProfile, Module, RolePermission, NotificationSettings
from rest_framework.generics import RetrieveUpdateAPIView
from core.permissions import IsAdminOrSuperuser, AdminOrGroups
from settings.settings_serializers import FeatureSerializer, LibrarySettingsSerializer, ModuleSerializer, RolePermissionSerializer, NotificationSettingsSerializer
from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework import viewsets
from rest_framework.views import APIView
from django.db import transaction, IntegrityError


def generate_unique_member_id(user_id, format_string):
    prefix = format_string.split('-')[0]
    last_member = MemberProfile.objects.order_by('-id').first()
    last_member_number = int(
        last_member.member_id.split('-')[1]) if last_member else 0
    unique_number = last_member_number + 1
    return f"{prefix}-{unique_number:04d}"


@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAdminOrSuperuser])
def get_library_settings(request):
    settings = LibrarySettings.objects.first()

    if request.method == 'GET':
        return Response({
            "max_books_per_member": settings.max_books_per_member if settings else 3,
            "max_issue_duration": settings.max_issue_duration if settings else 14,
            "fine_per_day": str(settings.fine_per_day) if settings else "10.00"
        })

    if request.method == 'POST':
        max_books = request.data.get('max_books_per_member')
        max_issue_duration = request.data.get('max_issue_duration')
        fine_per_day = request.data.get('fine_per_day')

        errors = {}

        if max_books is None:
            errors['max_books_per_member'] = "This field is required."
        if max_issue_duration is None:
            errors['max_issue_duration'] = "This field is required."
        if fine_per_day is None:
            errors['fine_per_day'] = "This field is required."

        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            max_books = int(max_books)
            max_issue_duration = int(max_issue_duration)
            fine_per_day = Decimal(fine_per_day)
        except (ValueError, InvalidOperation):
            return Response({"error": "Invalid data format."}, status=status.HTTP_400_BAD_REQUEST)

        if settings:
            settings.max_books_per_member = max_books
            settings.max_issue_duration = max_issue_duration
            settings.fine_per_day = fine_per_day
            settings.save()
        else:
            settings = LibrarySettings.objects.create(
                max_books_per_member=max_books,
                max_issue_duration=max_issue_duration,
                fine_per_day=fine_per_day
            )

        return Response({
            "detail": "Library settings updated successfully.",
            "max_books_per_member": settings.max_books_per_member,
            "max_issue_duration": settings.max_issue_duration,
            "fine_per_day": str(settings.fine_per_day)
        }, status=status.HTTP_200_OK)


class LibrarySettingsView(APIView):
    permission_classes = [AllowAny]
    
    def get_permissions(self):
        if self.request.method in ["PUT", 'PATCH']:
            return [AdminOrGroups(required_permission='core.change_librarysettings')]
        return super().get_permissions()
    
    
class LibrarySettingsView(APIView):
    permission_classes = [AllowAny]
    
    def get_permissions(self):
        if self.request.method in ["PUT", 'PATCH']:
            return [AdminOrGroups(required_permission='core.change_librarysettings')]
        return super().get_permissions()
    
    def _get_or_create_settings():
        settings = LibrarySettings.objects.first()
        if settings:
            return settings

        with transaction.atomic():
            settings = LibrarySettings.objects.first()
            if settings:
                return settings
            try:
                settings = LibrarySettings.objects.create()
            except IntegrityError:
                # another process created it concurrently → fetch it
                settings = LibrarySettings.objects.first()
        return settings             
    
    def get(self, request):
        try:
            settings = self._get_or_create_settings()
            if not settings:
                return Response({"detail": "Unable to initialize settings."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            if settings:
                serializer = LibrarySettingsSerializer(settings)
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response({"detail": "Settings not found"}, status=status.HTTP_404_NOT_FOUND)
        except LibrarySettings.DoesNotExist:
            return Response({"detail": "Settings not found"}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request):
        try:
            settings = LibrarySettings.objects.first()  # Assuming one instance for settings
            if settings:
                serializer = LibrarySettingsSerializer(
                    settings, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    return Response(serializer.data, status=status.HTTP_200_OK)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": "Settings not found"}, status=status.HTTP_404_NOT_FOUND)
        except LibrarySettings.DoesNotExist:
            return Response({"detail": "Settings not found"}, status=status.HTTP_404_NOT_FOUND)



class ModuleViewSet(viewsets.ModelViewSet):
    queryset = Module.objects.all()
    serializer_class = ModuleSerializer


class FeatureViewSet(viewsets.ModelViewSet):
    queryset = Feature.objects.all()
    serializer_class = FeatureSerializer


class RolePermissionViewSet(viewsets.ModelViewSet):
    queryset = RolePermission.objects.all()
    serializer_class = RolePermissionSerializer
    permission_classes = [IsAdminOrSuperuser]

class NotificationSettingsView(RetrieveUpdateAPIView):
    """
    GET    → fetch the singleton
    PATCH  → partial update
    PUT    → full update (you can still use it, though PATCH is preferred)
    """
    queryset = NotificationSettings.objects.all()
    serializer_class = NotificationSettingsSerializer
    
    def get_permissions(self):
        if (self.request.method == "GET"):
            return [AdminOrGroups(required_permission="core.view_notificationsettings")]
        if (self.request.method in ["PUT", "PATCH"]):
            return [AdminOrGroups(required_permission="core.change_notificationsettings")]
        return super().get_permissions()

    def get_object(self):
        # Always create a single row with PK=1 if it doesn’t exist
        obj, _ = NotificationSettings.objects.get_or_create(pk=1)
        return obj