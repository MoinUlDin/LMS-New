import random
from rest_framework import status, generics, viewsets
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
from django.contrib.auth.tokens import default_token_generator
from core import permissions
from core.models import LibrarySettings, User, MemberProfile, ManagerProfile
from core.utils import log_action
from django.conf import settings
from drf_spectacular.utils import extend_schema
from core.scheduler import scheduler
from settings.settings_views import generate_unique_member_id
from .auth_serializers import CustomTokenObtainPairSerializer, MemberRegisterSerializer,  ManagerRegisterSerializer, SingleMemberRegisterSerializer, ManagerProfileSerializer
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.views import APIView
from django.utils import timezone
from django.core.exceptions import ValidationError
from core.emailServices import send_manger_activation_link, send_verification_email, send_account_approved_notice, send_password_reset_link
from core.permissions import AdminOrGroups, CanManageBooks, IsAdminOrLibrarian
from django.db.models import F
from core.scheduler import scheduler


class MemberRegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = MemberRegisterSerializer
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def perform_create(self, serializer):
        user = serializer.save()

        # Get library settings for member_id format
        settings_obj = LibrarySettings.objects.first()
        if settings_obj and settings_obj.member_id_format:
            try:
                member_profile = user.profile
                if member_profile.member_id == "unknown" or not member_profile.member_id.startswith(settings_obj.member_id_format):
                    # Generate the unique member_id using the format from settings
                    new_member_id = generate_unique_member_id(
                        user.id, settings_obj.member_id_format)
                    member_profile.member_id = new_member_id  # Assign to the correct field
                    member_profile.save()
            except Exception as e:
                print("Error assigning member_id:", str(e))

        # Send verification email
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        # Use FRONTEND_URL from settings.py
        verify_url = f"{settings.FRONTEND_URL}/auth/verify-email/{uid}/{token}/"
        job_id = f'verify_email_{verify_url}'
        print(f'\nscheduler added a job with {job_id}\n')
        scheduler.add_job(
            func=send_verification_email,
            args=[user.id, verify_url],
            next_run_time=timezone.now(),
            id=job_id,
            replace_existing=True,
        )


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class ManagerRegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = ManagerRegisterSerializer
    permission_classes = [permissions.IsAdminOrSuperuser]

    def perform_create(self, serializer):
        user = serializer.save()
        
        # Build the login link
        login_url = settings.FRONTEND_URL 

        # Access the raw password from the serializer's validated data
        raw_password = self.request.data.get('password')

        # Schedule email
        scheduler.add_job(
            func=send_manger_activation_link,
            args=[user.id, raw_password],
            next_run_time=timezone.now(),      # fire immediately
            id=f"Manger_{user.email}_{user.username}",
            replace_existing=True,
        )
            


@extend_schema(responses=None)
@api_view(['GET'])
@permission_classes([AllowAny])
def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except Exception:
        return Response({"detail": "Invalid link."}, status=400)

    if user and default_token_generator.check_token(user, token):
        user.is_verified = True
        user.save()
        payload = {"username": user.username, "is_active": user.is_active, "user_role": user.role, "user_id": user.id}
        return Response({"detail": "Email verified successfully.", "user_detail": payload})
    return Response({"detail": "Invalid or expired token."}, status=400)


@extend_schema(request=None, responses=None)
class ForgotPasswordView(generics.GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        print(f"UserName: {username}")
        try:
            user = User.objects.get(username=username)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"
            
            scheduler.add_job(
                func=send_password_reset_link,
                args=[user.id, reset_url],
                next_run_time=timezone.now(),
                id=f"Reset_Password_{user.username}",
                replace_existing=True,
            )
            return Response({"detail": "Reset link sent has been sent."})
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=404)


@extend_schema(request=None, responses=None)
class ResetPasswordView(generics.GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except Exception:
            return Response({"detail": "Invalid link."}, status=400)

        if not default_token_generator.check_token(user, token):
            return Response({"detail": "Invalid token."}, status=400)

        password = request.data.get("password")
        confirm = request.data.get("confirm_password")
        
        if password != confirm:
            return Response({"detail": "Passwords do not match."}, status=400)

        user.set_password(password)
        user.save()
        return Response({"detail": "Password reset successful."})



class ApproveUserView(APIView):
    """
    POST /approve-user/<int:user_id>/
    Only an admin or superuser may call this.
    """
    def get_permissions(self):
        return [AdminOrGroups(required_permission='core.change_memberprofile')]

    @extend_schema(request=None, responses=None)
    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id, is_active=False)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found or already approved."},
                status=status.HTTP_404_NOT_FOUND
            )

        user.is_active = True
        user.save()

        scheduler.add_job(
            func=send_account_approved_notice,
            args=[user.id],
            next_run_time=timezone.now(),
            id=f"Account_approved_{user.username}",
            replace_existing=True,
        )

        return Response({"detail": "User approved and notified via email."})
    


@extend_schema(request=None, responses=None)
@api_view(['POST'])
@permission_classes([permissions.IsAdminOrSuperuser])
def decline_user(request, user_id):
    try:
        user = User.objects.get(id=user_id, is_active=False)
        user.is_declined = True
        user.save()

        # Send decline email
        send_mail(
            "Your account request was declined",
            "We're sorry, your account registration has been declined. Please contact admin for further details.",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )

        return Response({"detail": "User has been declined and notified via email."})
    except User.DoesNotExist:
        return Response({"detail": "User not found or already processed."}, status=404)


@extend_schema(request=None, responses=None)
@api_view(['POST'])
@permission_classes([permissions.IsAdminOrSuperuser])
def restore_user(request, user_id):
    try:
        user = User.objects.get(id=user_id, is_declined=True)
        user.is_declined = False  # ✅ Undecline the user
        user.save()

        return Response({"detail": "User has been restored and moved back to pending approvals."})
    except User.DoesNotExist:
        return Response({"detail": "User not found or not declined."}, status=404)


class SingleRegisterMemberView(generics.CreateAPIView):
    serializer_class = SingleMemberRegisterSerializer
    permission_classes = [permissions.IsAdminOrSuperuser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]


class ManagerProfileViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ManagerProfile.objects.select_related('user').all()
    serializer_class = ManagerProfileSerializer
    permission_classes = [AllowAny]


