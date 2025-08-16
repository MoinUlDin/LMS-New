from django.db.models import Count, Q, Sum, F
from .serializers import DepartmentSerializer, LanguageSerializer, SessionSettingsSerializer, UpdateUserRoleSerializer
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, status
from rest_framework.permissions import IsAuthenticated
from core import permissions
from .card_utils import generate_membership_card
from .utils import log_action
from .models import AuditLog, Book, BookIssuance,  BookReservation, Department,  Fine, Language, MemberProfile, NotificationLog, SessionSettings, User
from .serializers import AuditLogSerializer,  BookSerializer, IssuedBookHistorySerializer, NotificationLogSerializer,GroupSerializer, PermissionSerializer
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework import filters
from drf_spectacular.utils import extend_schema, OpenApiResponse
# core/api/views.py
from django.contrib.auth.models import Group, Permission
from rest_framework.decorators import action
from rest_framework.views import APIView
from .permissions import CanViewDashboard, AdminOrGroups
from users.users_serializers import UserSerializer
from rest_framework.generics import ListAPIView
from rest_framework.exceptions import ParseError
from .serializers import FineSerializer
from django.db import transaction
from books.books_serializers import BookDetailSerializer
from decimal import Decimal, ROUND_HALF_UP

    
class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List all permissions in the system.
    """
    queryset = Permission.objects.select_related('content_type').all()
    serializer_class = PermissionSerializer

class GroupViewSet(viewsets.ModelViewSet):
    """
    CRUD groups (roles), including reading & updating the list of permissions.
    """
    queryset = Group.objects.prefetch_related('permissions').all()
    serializer_class = GroupSerializer
    
    def perform_create(self, serializer):
        # 1) Save the new Group instance
        group = serializer.save()

        # 2) Log the “role created” action
        log_action(
            user=self.request.user,
            action_type='ROLE_CREATED',
            description=f"Role '{group.name}' was created."
        )

    def perform_update(self, serializer):
        # 1) Save changes on the existing Group instance
        group = serializer.save()

        # 2) Log the “role updated” action
        log_action(
            user=self.request.user,
            action_type='ROLE_UPDATED',
            description=f"Role '{group.name}' was updated."
        )
    
    def perform_destroy(self, instance):
        group_name = instance.name  # Capture before deletion
        instance.delete()
        
        # Log the "role deleted" action
        log_action(
            user=self.request.user,
            action_type='ROLE_DELETED',
            description=f"Role '{group_name}' was deleted."
        )
    
    @action(detail=True, methods=['post'], url_path='assign_user')
    def assign_user(self, request, pk=None):
        """
        POST /roles/{pk}/assign_user/
        Body: { "user_ids": [17, 23, ...] }
        """
        group = self.get_object()
        ids = request.data.get('user_ids', [])
        if not isinstance(ids, list) or not ids:
            return Response(
                {'detail': 'user_ids must be a non-empty list'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Fetch only existing users not already in this group
        users = User.objects.filter(pk__in=ids).exclude(groups=group)
        if not users:
            return Response(
                {'detail': 'No matching users found (or already in this group)'},
                status=status.HTTP_404_NOT_FOUND
            )

        group.user_set.add(*users)
        added = [u.username for u in users]
        for u in users:
            try:
                log_action(
                    user=self.request.user,
                    action_type='ROLE_ASSIGN_USER',
                    description=f"Added user '{u.username}' to role '{group.name}'."
                )
            except Exception as e:
                print(f'\nError assigning {e}\n')
                pass
        
        return Response(
            {'detail': f'Added users {added} to role {group.name}'},
            status=status.HTTP_200_OK
        )
        
    @action(detail=True, methods=['get'], url_path='users')
    def list_users(self, request, pk=None):
        """
        GET /roles/{pk}/users/
        Returns: list of all users in this group
        """
        group = self.get_object()
        users = group.user_set.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='permissions')
    def permissions(self, request, pk=None):
        """
        GET /roles/{user_pk}/permissions/
        Treats {pk} as a user ID and returns all that user’s permissions.
        """
        # 1) Load the user by that pk
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {'detail': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # 2) Gather direct + group permissions for *that* user
        if user.is_superuser:
            perms = Permission.objects.all()
        else:
            perms = Permission.objects.filter(
                Q(user=user) |
                Q(group__user=user)
            ).distinct()

        # 3) Serialize and return
        serializer = PermissionSerializer(perms, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], url_path='remove_user')
    def remove_user(self, request, pk=None):
        """
        POST /roles/{pk}/remove_user/
        Body: { "user_ids": [17, 23, ...] }
        """
        group = self.get_object()
        ids = request.data.get('user_ids', [])
        if not isinstance(ids, list) or not ids:
            return Response(
                {'detail': 'user_ids must be a non‑empty list'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Fetch only existing users in this group
        users = User.objects.filter(pk__in=ids, groups=group)
        if not users:
            return Response(
                {'detail': 'No matching users found in this group'},
                status=status.HTTP_404_NOT_FOUND
            )

        group.user_set.remove(*users)
        removed = [u.username for u in users]
        
        for u in users:
            try:
                log_action(
                    user=self.request.user,
                    action_type='ROLE_REMOVE_USER',
                    description=f"Removed user '{u.username}' from role '{group.name}'."
                )
            except Exception as e:
                print(f'\nError removing {e}\n')
                pass

        removed_usernames = [u.username for u in users]
        return Response(
            {'detail': f"Removed users {removed_usernames} from role {group.name}"},
            status=status.HTTP_200_OK
        )

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer

    def get_permissions(self):
        # Allow anyone (even Members) to view books
        if self.request.method in ['GET', 'HEAD', 'OPTIONS']:
            return [AllowAny()]
        # Only Admins and authorized Managers can modify
        return [permissions.CanManageBooks()]

    def update(self, request, *args, **kwargs):
        book = self.get_object()
        old_status = book.status
        response = super().update(request, *args, **kwargs)
        new_status = response.data.get('status')

        if old_status != new_status and new_status in ['WRITE_OFF', 'LOST']:
            log_action(
                request.user,
                'BOOK_STATUS_CHANGE',
                f"Book '{book.title}' (ID: {book.id}) marked as {new_status}."
            )

        return response

class NotificationLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NotificationLog.objects.all()
    serializer_class = NotificationLogSerializer
    def get_permissions(self):
        if self.request.method == "GET":
            return [AdminOrGroups(required_permission='core.view_notificationlog')]
        if self.request.method == "POST":
            return [AdminOrGroups(required_permission='core.add_notificationlog')]
        if self.request.method in ["PUT", "PATCH"]:
            return [AdminOrGroups(required_permission='core.change_notificationlog')]
        if self.request.method == "DELETE":
            return [AdminOrGroups(required_permission='core.delete_notificationlog')]
        return super().get_permissions()
    
    @action(
        detail=False,
        methods=['get'],
        url_path='notification-history',
    )
    def get_notification_history(self, request):
        THRESHHOLD = 3
        nqs = NotificationLog.objects.all()
        notifications = NotificationLogSerializer(nqs, many=True)
        b_qs = Book.objects.filter(available_copies__lt=THRESHHOLD)
        books = BookDetailSerializer(b_qs, many=True, context={'request': request})
        payload = {
            "books": books.data,
            "notification_logs": notifications.data
        }
        return Response(payload, status=status.HTTP_200_OK)
    
class UserHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IssuedBookHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return BookIssuance.objects.filter(member=self.request.user).order_by('-issue_date')

class AllHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IssuedBookHistorySerializer
    queryset = BookIssuance.objects.all().order_by('-issue_date')
    permission_classes = [IsAuthenticated, permissions.CanManageBooks]
    filter_backends = [filters.SearchFilter]
    search_fields = ['book__title', 'user__username']

class DashboardSummaryView(APIView):
    permission_classes = [CanViewDashboard]
    def get_permissions(self):
        return [AdminOrGroups(required_permission="core.view_dashboard_summary")]
    @extend_schema(request=None, responses=None)
    def get(self, request):
        total_books = Book.objects.count()
        total_users = User.objects.count()
        total_members = User.objects.filter(role='MEMBER').count()
        total_issued_books = BookIssuance.objects.filter(
            returned_at__isnull=True).count()
        total_reservations = BookReservation.objects.count()
        total_fines_unpaid = Fine.objects.filter(paid=False).count()

        department_stats = MemberProfile.objects.values('department').annotate(
            member_count=Count('id')
        ).order_by('department')

        return Response({
            "total_books": total_books,
            "total_users": total_users,
            "total_members": total_members,
            "total_issued_books": total_issued_books,
            "total_reservations": total_reservations,
            "total_fines_unpaid": total_fines_unpaid,
            "departments": list(department_stats)
        })

class AdminDepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    def get_permissions(self):
        if self.request.method == "GET":
            return [AdminOrGroups(required_permission='core.view_department')]
        if self.request.method == "POST":
            return [AdminOrGroups(required_permission='core.add_department')]
        if self.request.method in ["PUT", "PATCH"]:
            return [AdminOrGroups(required_permission='core.change_department')]
        if self.request.method == "DELETE":
            return [AdminOrGroups(required_permission='core.delete_department')]

class MemberDepartmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [AllowAny]  # or IsAuthenticated, IsMember

class AdminSessionViewSet(viewsets.ModelViewSet):
    queryset = SessionSettings.objects.all()
    serializer_class = SessionSettingsSerializer
    def get_permissions(self):
        if self.request.method == "GET":
            return [AdminOrGroups(required_permission='core.view_sessionsettings')]
        if self.request.method == "POST":
            return [AdminOrGroups(required_permission='core.add_sessionsettings')]
        if self.request.method in ["PUT", "PATCH"]:
            return [AdminOrGroups(required_permission='core.change_sessionsettings')]
        if self.request.method == "DELETE":
            return [AdminOrGroups(required_permission='core.delete_sessionsettings')]

class MemberSessionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SessionSettings.objects.all()
    serializer_class = SessionSettingsSerializer
    permission_classes = [AllowAny]  # or IsAuthenticated, IsMember

class LanguageViewSet(viewsets.ModelViewSet):
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer
    permission_classes = [permissions.IsAdminOrLibrarian]
    def get_permissions(self):
        if self.request.method == "POST":
            return [AdminOrGroups(required_permission='core.add_language')]
        if self.request.method in ["PUT", "PATCH"]:
            return [AdminOrGroups(required_permission='core.change_language')]
        if self.request.method == "DELETE":
            return [AdminOrGroups(required_permission='core.delete_language')]
        return super().get_permissions()

class UserFineListView(ListAPIView):
    """
    GET /api/fines/?user_id=<user_id>
    returns all Fine records for that user.
    """
    serializer_class = FineSerializer

    def get_queryset(self):
        user_id = self.kwargs.get('user_id')
        if not user_id:
            raise ParseError(detail="`user_id` query parameter is required.")
        # filter on the related BookIssuance.user
        return Fine.objects.filter(issued_book__member__id=user_id).order_by('-created_at')

class FineViewSet(viewsets.ModelViewSet):
    queryset = Fine.objects.all()
    serializer_class = FineSerializer
    
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AdminOrGroups(required_permission='core.view_reports')]
        return super().get_permissions()
    
    
    @action(detail=False, methods=['post'], url_path='collect') 
    @transaction.atomic
    def collect_fines(self, request):
        data = request.data
        member_id = data.get("member_id")
        issued_ids = data.get("issued_ids", [])
        raw_collected = data.get("collected_amount", 0)
        raw_discount  = data.get("discount", 0)
        full_payment = data.get("full_payment", False)

        # 1) Validate inputs
        if not member_id:
            return Response(
                {"detail": "member_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not issued_ids:
            return Response(
                {"detail": "issued_ids list is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2) Fetch Member
        try:
            member = User.objects.get(pk=member_id)
        except User.DoesNotExist:
            return Response(
                {"detail": "Member not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Convert request values into Decimal
        try:
            total_collected = Decimal(str(raw_collected))
        except (ValueError, TypeError):
            total_collected = Decimal("0.00")

        try:
            total_discount = Decimal(str(raw_discount))
        except (ValueError, TypeError):
            total_discount = Decimal("0.00")

        # 3) Fetch all Fine objects for those issued_book IDs
        fines = list(
            Fine.objects.filter(issued_book_id__in=issued_ids).select_for_update()
        )

        if not fines:
            return Response(
                {"detail": "No fines found for given issued_ids"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 4) Compute each fine's remaining balance = amount − collected_amount − discount (existing)
        fines_info = []
        for fine in fines:
            existing_collected = fine.collected_amount or Decimal("0.00")
            existing_discount = fine.discount or Decimal("0.00")
            remaining = fine.amount - existing_collected - existing_discount
            if remaining > Decimal("0.00"):
                fines_info.append({"fine": fine, "remaining": remaining})

        if not fines_info:
            return Response(
                {
                    "detail": "All specified fines are already fully paid or fully discounted."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 5) Distribute the total_discount across fines_info, one by one
        discount_left = total_discount
        for info in fines_info:
            if discount_left <= Decimal("0.00"):
                info["apply_discount"] = Decimal("0.00")
                continue
            alloc = min(discount_left, info["remaining"])
            info["apply_discount"] = alloc
            info["remaining"] -= alloc
            discount_left -= alloc

        # 6) Distribute the total_collected across the post-discount balances
        collect_left = total_collected
        for info in fines_info:
            post_discount_balance = info["remaining"]
            if collect_left <= Decimal("0.00"):
                info["apply_collect"] = Decimal("0.00")
                continue
            alloc = min(collect_left, post_discount_balance)
            info["apply_collect"] = alloc
            info["remaining"] -= alloc
            collect_left -= alloc

        # 7) Update each Fine instance
        for info in fines_info:
            fine = info["fine"]
            applied_disc = info.get("apply_discount", Decimal("0.00"))
            applied_col = info.get("apply_collect", Decimal("0.00"))

            existing_discount = fine.discount or Decimal("0.00")
            existing_collected = fine.collected_amount or Decimal("0.00")
            existing_cashInHand = fine.cash_in_hand or Decimal("0.00")

            fine.discount = (existing_discount + applied_disc).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            fine.cash_in_hand = (existing_cashInHand + applied_col).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            fine.collected_amount = (existing_collected + applied_col).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            # Recalculate remaining_fines and collected flag inside model.save()
            fine.save()

        # 8) Update member.is_defaulter
        if full_payment:
            member.profile.is_defaulter = False
            
        else:
            # If no Fine for this member has remaining_fines > 0, clear defaulter
            has_outstanding = Fine.objects.filter(
                issued_book__member=member,
                remaining_fines__gt=Decimal("0.00")
            ).exists()
            if not has_outstanding:
                member.profile.is_defaulter = False
                
        member.profile.save()
        member.refresh_from_db()
        return Response(
            {
                "detail": "Fines updated successfully.",
                "member_id": member_id,
                "full_payment": full_payment,
                "all_fully_paid_selected": not any(
                    info["remaining"] > Decimal("0.00") for info in fines_info
                )
            },
            status=status.HTTP_200_OK,
        )

        
    @action(detail=False, methods=['get'], url_path='collected')
    def get_collected(self, request):
        """
        GET /fines/collected/
        """
        fines = self.get_queryset().filter(collected=True, collected_amount__gt=0)
        serializer = self.get_serializer(fines, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='pending')
    def get_pending(self, request):
        """
        GET /fines/pending/
        """
        fines = self.get_queryset().filter(collected=False, amount__gt=0)
        serializer = self.get_serializer(fines, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='cash-in-hand')
    def get_cash_in_hand(self, request):
        """
        GET /fines/cash-in-hand/
        Returns:
          - list of all fines with collected_amount > 0
          - cash_in_hand_total: sum of the `cash_in_hand` field over those records
        """
        qs = self.get_queryset().filter(collected_amount__gt=0)
        serializer = self.get_serializer(qs, many=True)

        total = qs.aggregate(
            cash_in_hand_total=Sum('cash_in_hand')
        )['cash_in_hand_total'] or 0

        return Response({
            "records": serializer.data,
            "cash_in_hand_total": total
        })

    @action(detail=False, methods=['get'], url_path='financial-reports')
    def get_financial_reports(self, request):
        """
        GET /fines/financial-reports/
        Returns a combined payload of collected, pending, and cash-in-hand data.
        """
        # Collected
        collected_qs = self.get_queryset().filter(collected=True, collected_amount__gt=0)
        collected_data = self.get_serializer(collected_qs, many=True).data

        # Pending
        pending_qs = self.get_queryset().filter(collected=False)
        pending_data = self.get_serializer(pending_qs, many=True).data

        # Cash-in-hand
        cash_qs = self.get_queryset().filter(collected_amount__gt=0)
        cash_data = self.get_serializer(cash_qs, many=True).data
        cash_total = cash_qs.aggregate(
            cash_in_hand_total=Sum('cash_in_hand')
        )['cash_in_hand_total'] or 0

        return Response({
            "collected": collected_data,
            "pending": pending_data,
            "cash_in_hand": {
                "records": cash_data,
                "cash_in_hand_total": cash_total
            }
        }, status=status.HTTP_200_OK)

@extend_schema(request=None, responses=None)
@api_view(['POST'])
@permission_classes([permissions.CanManageUsers])
def update_user_role(request):
    user_id = request.data.get('user_id')
    new_role = request.data.get('role')
    if new_role == 'ADMIN' and not request.user.is_superuser:
        return Response({'detail': 'Only superusers can assign ADMIN role.'}, status=403)
    if not user_id or not new_role:
        return Response({'detail': 'user_id and role are required'}, status=400)
    try:
        user = User.objects.get(id=user_id)
        user.role = new_role
        user.save()
        # Log the action
        log_action(request.user, 'ROLE_CHANGE',
                   f"Updated role for {user.username} to {new_role}")
        return Response({'detail': f"Updated role to {new_role} for user {user.username}"})
    except User.DoesNotExist:
        return Response({'detail': 'User not found'}, status=404)

@extend_schema(
    responses=OpenApiResponse(
        description="PDF file response (membership card)")
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, permissions.CanManageUsers])
def download_membership_card(request, member_id):
    member = get_object_or_404(MemberProfile, id=member_id)
    pdf_buffer = generate_membership_card(member)
    return FileResponse(pdf_buffer, as_attachment=True, filename=f"{member.member_id}_card.pdf")


class GetVersionInfo(APIView):
    permission_classes=[AllowAny]

    def get(self, request, *args, **kwargs): 
        payload = {
            "version": "1.1.1",
            "last_updated": "16-08-2025",
            "details": "Migrated to new URL, and connecting to real PostgreSQL database",
            "created_by": "Moin ul din",
            "email": "moinuldinc@gmail.com",
        }
        return Response(payload, status=status.HTTP_200_OK)