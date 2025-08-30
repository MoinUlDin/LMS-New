from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from core import permissions
from core.models import User, MemberProfile, Fine, BookIssuance, BookReservation
from core.permissions import CanManageUsers, IsProfileOwner, AdminOrGroups,IsAdminOrSuperuser, IsAdminOrLibrarian
from core.utils import log_action
from .users_serializers import AdminUserSerializer, MangerProfileSerializer, FullMemberProfileSerializer,ManagerProfile , MemberProfileUpdateSerializer, UserSerializer, UpdateUserRoleSerializer, BulkMemberUploadSerializer
from io import TextIOWrapper
import csv
from django.utils import timezone
from rest_framework.parsers import MultiPartParser, FileUploadParser, FormParser
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models import Count, Sum, Q
from rest_framework.exceptions import NotFound
from core.scheduler import scheduler
from core.emailServices import send_welcome_email
from decimal import Decimal
from rest_framework.decorators import action
from core.models import MemberProfile

User = get_user_model()

class UpdateMemberProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsMember]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = MemberProfileUpdateSerializer
    def get_object(self):
        return self.request.user.profile
    
    def get_serializer_context(self):
        return { **super().get_serializer_context(), "request": self.request }

class UpdateManagerProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, IsProfileOwner]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = MangerProfileSerializer
    def get_object(self):
        try:
            return self.request.user.manager_profile
        except ManagerProfile.DoesNotExist:
            raise NotFound(detail="ManagerProfile does not exist for this user.")
        
    def get_serializer_context(self):
        return { **super().get_serializer_context(), "request": self.request }


@extend_schema(request=None, responses=None)
@api_view(['POST'])
@permission_classes([CanManageUsers])
def update_user_role(request):
    user_id = request.data.get('user_id')
    new_role = request.data.get('role')

    try:
        user = User.objects.get(id=user_id)
        user.role = new_role
        user.save()
        log_action(request.user, 'ROLE_CHANGE',
                   f"Updated role for {user.username} to {new_role}")
        return Response({'detail': f"Updated role for {user.username}"})
    except User.DoesNotExist:
        return Response({'detail': 'User not found'}, status=404)


@extend_schema(request=None, responses=None)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if user.role == "ADMIN" and not request.user.is_superuser:
        return Response({"detail": "Only superusers can delete admins."}, status=403)
    user.delete()
    return Response({"detail": "User deleted."})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def whoami(request):
    return Response({
        "user": str(request.user),
        "is_authenticated": request.user.is_authenticated,
        "is_superuser": request.user.is_superuser,
        "role": request.user.role
    })


class BulkMemberUploadView(APIView):
    parser_classes = [MultiPartParser]
    permission_classes = [permissions.IsAdminOrSuperuser]
    serializer_class = BulkMemberUploadSerializer

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({"detail": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        decoded_file = TextIOWrapper(file, encoding='utf-8')
        reader = csv.DictReader(decoded_file)

        created, failed = 0, []

        for index, row in enumerate(reader, start=1):
            try:
                if User.objects.filter(username=row['username']).exists():
                    failed.append({f"Row {index}": "Username already exists"})
                    continue

                user = User.objects.create_user(
                    username=row['username'],
                    email=row['email'],
                    password=row['password'],
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    role='MEMBER',
                    is_active=True,
                    is_verified=True
                )

                last_profile = MemberProfile.objects.order_by('-id').first()
                member_id = f"MBR-{(last_profile.id + 1) if last_profile else 1:04d}"

                MemberProfile.objects.create(
                    user=user,
                    member_id=member_id,
                    middle_name=row.get('middle_name', ''),
                    father_first_name=row.get('father_first_name', ''),
                    father_last_name=row.get('father_last_name', ''),
                    class_name=row.get('class_name', ''),
                    section=row.get('section', ''),
                    mobile_number=row.get('mobile_number', ''),
                    cnic=row.get('cnic', ''),
                    department_id=row['department'],
                    session_id=row['session'],
                    registration_id=row.get('registration_id', ''),
                    roll_no=row.get('roll_no', ''),
                    shift=row.get('shift', 'DAY'),
                    security_fee=row.get('security_fee', 0.00),
                    home_address=row.get('home_address', ''),
                    emergency_contact=row.get('emergency_contact', ''),
                    library_membership_id=row.get('library_membership_id', '')
                )
                scheduler.add_job(
                send_welcome_email,
                args=[user.id, row["password"]],
                next_run_time=timezone.now(),      # fire immediately
                id=f"welcome_{user.id}",
                replace_existing=True,
                )

                created += 1

            except Exception as e:
                failed.append({f"Row {index}": str(e)})

        return Response({
            "detail": f"{created} members created successfully.",
            "errors": failed
        }, status=207 if failed else 200)


@extend_schema(request=None, responses=None)
@api_view(['GET'])
@permission_classes([permissions.IsAdminOrSuperuser])
def pending_users(request):
    pending = User.objects.filter(
        is_active=False, is_declined=False, role='MEMBER')
    serialized = UserSerializer(pending, many=True)
    return Response(serialized.data)


@extend_schema(request=None, responses=None)
@api_view(['GET'])
@permission_classes([permissions.IsAdminOrSuperuser])
def declined_users(request):
    declined = User.objects.filter(is_declined=True)
    serializer = UserSerializer(declined, many=True)
    return Response(serializer.data)


@extend_schema(request=None, responses=None)
@api_view(['GET'])
@permission_classes([permissions.IsAdminOrSuperuser])
def approved_members(request):
    approved = User.objects.filter(
        is_active=True,
        is_declined=False,
        role='MEMBER'
    )
    serializer = UserSerializer(approved, many=True)
    return Response(serializer.data)


extend_schema(request=None, responses=FullMemberProfileSerializer(many=True))
class AllMembersView(APIView):
    def get_permissions(self):
        return [AdminOrGroups(required_permission='core.view_members')]
    def get(self, request, format=None):
        members = MemberProfile.objects.select_related(
            'user', 'department', 'session'
        ).all()
        serializer = FullMemberProfileSerializer(members, many=True)
        return Response(serializer.data)


class SingleMemberProfileView(APIView):
    permission_classes = [IsAuthenticated]  # Equivalent to IsAdminOrSuperuser
    serializer_class = FullMemberProfileSerializer
    def get(self, request, user_id):
        requesting_user = request.user  
        print("\n\nsingleMembergetCalled")
        profile = get_object_or_404(
            MemberProfile.objects.select_related('user', 'department', 'session'),
            user__id=user_id
        )
        serializer = FullMemberProfileSerializer(
            profile,
            context={'request': request}
        )
        data = serializer.data
        user_id_from_data = data['user_id']  # ✅ Corrected line
    
        if requesting_user.role != 'SUPER USER' and requesting_user.id != user_id_from_data:
            return Response({'detail': 'You do not have permissions to perform this action'}, status=403)
        return Response(serializer.data)

class AdminUserUpdateView(generics.RetrieveUpdateAPIView):
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminOrSuperuser]
    parser_classes = [MultiPartParser, FormParser]

    def get_object(self):
        return self.request.user

@extend_schema(
    request=None,
    responses={
        200: None, 
        404: None
    }
)
class ToggleMemberStatus(APIView):
    
    def get_permissions(self):
        return [AdminOrGroups(required_permission="core.change_members")]
    def post(self, request, user_id, format=None):
        try:
            user = User.objects.get(Q(id=user_id) & Q(role__iexact='MEMBER'))
        except User.DoesNotExist:
            return Response(
                {"detail": "Member not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        user.is_active = not user.is_active
        user.save()

        status_str = "enabled" if user.is_active else "disabled"
        return Response({
            "detail": f"Member '{user.username}' has been {status_str}.",
            "is_active": user.is_active
        }, status=status.HTTP_200_OK)


class DisabledMembersList(APIView):
    def get_permissions(self):
        return [ AdminOrGroups(required_permission='core.change_members') ]

    def get(self, request, *args, **kwargs):
        disabled_members = User.objects.filter(
            role__iexact='MEMBER',
            is_active=False
        )
        serializer = UserSerializer(disabled_members, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class MemberViewSet(viewsets.ModelViewSet):
    queryset = MemberProfile.objects.all()
    serializer_class = FullMemberProfileSerializer
    # … your other actions …

    @action(detail=True, methods=['get'], url_path='dashboard')
    def dashboard(self, request, pk=None):
        if pk is None:
            return Response({"detail": "No Id given"}, status=status.HTTP_400_BAD_REQUEST)
        member = User.objects.filter(pk=pk).first()
        
        
        
        # return Response({"message": "wowo"},status=status.HTTP_200_OK)
        # --- Issued books (not yet returned) ---
        issued_qs = BookIssuance.objects.filter(member=member)
        issued_count = issued_qs.filter(returned_at__isnull=True).count()

        # --- Overdue (still not returned, due_date in the past) ---
        today = timezone.now().date()
        overdue_count = issued_qs.filter(
            returned_at__isnull=True,
            due_date__lt=today
        ).count()

        # --- Active reservations ---
        reserved_count = BookReservation.objects.filter(
            user=member,
            status='FULFILLED' 
        ).count()

        # --- Fines ---
        fines = Fine.objects.filter(issued_book__member=member)
        agg   = fines.aggregate(
            total_amount=Sum('amount'),
            paid_amount=Sum('collected_amount'),
        )
        total_fine = agg['total_amount'] or Decimal(0)
        paid_fine  = agg['paid_amount']  or Decimal(0)
        pending_fine = max(total_fine - paid_fine, Decimal(0))

        # # --- Unread notifications (if you have a Notification model) ---
        # notifications_count = Notification.objects.filter(
        #     member=member,
        #     read=False
        # ).count()

        return Response({
            "issued_count":       issued_count,
            "overdue_count":      overdue_count,
            "reserved_count":     reserved_count,
            "fines": {
                "total":   str(total_fine),
                "paid":    str(paid_fine),
                "pending": str(pending_fine),
            },
            # "unread_notifications": notifications_count,
        }, status=status.HTTP_200_OK)
