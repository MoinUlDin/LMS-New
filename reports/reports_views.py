from decimal import Decimal
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from core.models import Book, BookIssuance, BookReservation, LibrarySettings, User, Fine, MemberProfile, AuditLog, ManagerProfile
from core.permissions import CanManageBooks, CanManageUsers, CanViewDashboard
from core.serializers import AuditLogSerializer, IssuedBookHistorySerializer
from books.books_serializers import BookDetailSerializer, BookIssuanceDetailSerializer
from users.users_serializers import FullMemberProfileSerializer, MangerProfileSerializer
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Count, Sum, Q
from rest_framework.views import APIView
from rest_framework import status
from django.db.models import Count, F, Sum, DecimalField
from core.permissions import CanManageBooks, AdminOrGroups


def get_date_trunc_and_range(filter_by):
    now = datetime.now()
    if filter_by == "day":
        return TruncDay("issue_date"), now - timedelta(days=1)
    elif filter_by == "week":
        return TruncWeek("issue_date"), now - timedelta(weeks=1)
    elif filter_by == "month":
        return TruncMonth("issue_date"), now - timedelta(days=30)
    return TruncMonth("issue_date"), now - timedelta(days=30)


class DashboardSummaryView(APIView):
    """
    Dashboard summary endpoint, protected by CanManageUsers.
    """
    def get_permissions(self):
        return [AdminOrGroups(required_permission='core.view_dashboard_summary')]

    def get(self, request, format=None):
        today = datetime.today().date()

        # Total counts
        total_books = Book.objects.count()
        available_books = Book.objects.aggregate(
            total=Sum('available_copies')
        )['total'] or 0
        issued_books = BookIssuance.objects.filter(
            returned_at__isnull=True
        ).count()
        
        lost_damaged_books = Book.objects.filter(
            status__in=['LOST', 'DAMAGED']
        ).count()

        # Total members
        total_members = User.objects.filter(role='MEMBER').count()

        # Charts: monthly issued/returned/registrations, reserved
        reserved_books = BookReservation.objects.filter(status='FULFILLED').count()
        issued_monthly = BookIssuance.objects.annotate(
            month=TruncMonth('issue_date')
        ).values('month').annotate(count=Count('id')).order_by('month')

        returned_monthly = BookIssuance.objects.filter(
            returned_at__isnull=False
        ).annotate(month=TruncMonth('returned_at')
        ).values('month').annotate(count=Count('id')).order_by('month')

        registration_monthly = User.objects.filter(role='MEMBER'
        ).annotate(month=TruncMonth('date_joined')
        ).values('month').annotate(count=Count('id')).order_by('month')

        registration_daily = User.objects.filter(role='MEMBER'
        ).annotate(day=TruncDay('date_joined')
        ).values('day').annotate(count=Count('id')).order_by('day')

        # Fines summary
        collected_fines = Fine.objects.filter(collected=True
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        pending_fines = Fine.objects.filter(collected=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        fine_collected_daily = Fine.objects.filter(collected=True
        ).annotate(day=TruncDay('created_at')
        ).values('day').annotate(total=Sum('amount')
        ).order_by('day')

        fine_collected_weekly = Fine.objects.filter(collected=True
        ).annotate(week=TruncWeek('created_at')
        ).values('week').annotate(total=Sum('amount')
        ).order_by('week')

        fine_collected_monthly = Fine.objects.filter(collected=True
        ).annotate(month=TruncMonth('created_at')
        ).values('month').annotate(total=Sum('amount')
        ).order_by('month')

        fine_pending_daily = Fine.objects.filter(collected=False
        ).annotate(day=TruncDay('created_at')
        ).values('day').annotate(total=Sum('amount')
        ).order_by('day')

        fine_pending_weekly = Fine.objects.filter(collected=False
        ).annotate(week=TruncWeek('created_at')
        ).values('week').annotate(total=Sum('amount')
        ).order_by('week')

        fine_pending_monthly = Fine.objects.filter(collected=False
        ).annotate(month=TruncMonth('created_at')
        ).values('month').annotate(total=Sum('amount')
        ).order_by('month')

        # Overdue
        overdue_books = BookIssuance.objects.filter(
            due_date__lt=today, returned_at__isnull=True
        ).count()

        # Recent activity
        recent_issues = BookIssuance.objects.select_related('book', 'member'
        ).order_by('-issue_date')[:5].values(
            'book__id', 'book__title',
            'member__id', 'member__username',
            'issue_date', 'due_date'
        )

        recent_members = User.objects.filter(role='MEMBER'
        ).order_by('-date_joined')[:5].values(
            'id', 'username', 'date_joined', 'is_active', 'is_verified'
        )

        defaulted_members = User.objects.filter(
            role='MEMBER',
            issued_books__fine__collected=False
        ).annotate(
            unpaid_fine=Sum(
                'issued_books__fine__amount',
                filter=Q(issued_books__fine__collected=False)
            )
        ).distinct().values(
            'id', 'username', 'is_active', 'is_verified', 'unpaid_fine'
        )

        return Response({
            "total_members": total_members,
            "cards": {
                "total_books": total_books,
                "available_books": available_books,
                "issued_books": issued_books,
                "reserved_books": reserved_books,
                "lost_damaged_books": lost_damaged_books,
            },
            "charts": {
                "line_chart": {
                    "issued_books": [
                        {"month": i["month"].strftime('%Y-%m'), "count": i["count"]}
                        for i in issued_monthly
                    ],
                    "returned_books": [
                        {"month": i["month"].strftime('%Y-%m'), "count": i["count"]}
                        for i in returned_monthly
                    ],
                    "overdue_books": overdue_books,
                    "reserved_books": reserved_books
                },
                "fine_summary": {
                    "collected": str(collected_fines),
                    "pending": str(pending_fines),
                    "collected_daily": [
                        {"day": i["day"].strftime('%Y-%m-%d'), "total": str(i["total"])}
                        for i in fine_collected_daily
                    ],
                    "collected_weekly": [
                        {"week": i["week"].strftime('%Y-%W'), "total": str(i["total"])}
                        for i in fine_collected_weekly
                    ],
                    "collected_monthly": [
                        {"month": i["month"].strftime('%Y-%m'), "total": str(i["total"])}
                        for i in fine_collected_monthly
                    ],
                    "pending_daily": [
                        {"day": i["day"].strftime('%Y-%m-%d'), "total": str(i["total"])}
                        for i in fine_pending_daily
                    ],
                    "pending_weekly": [
                        {"week": i["week"].strftime('%Y-%W'), "total": str(i["total"])}
                        for i in fine_pending_weekly
                    ],
                    "pending_monthly": [
                        {"month": i["month"].strftime('%Y-%m'), "total": str(i["total"])}
                        for i in fine_pending_monthly
                    ],
                },
                "registration_rate": [
                    {"month": i["month"].strftime('%Y-%m'), "count": i["count"]}
                    for i in registration_monthly
                ],
                "registration_rate_daily": [
                    {"day": i["day"].strftime('%Y-%m-%d'), "count": i["count"]}
                    for i in registration_daily
                ],
            },
            "tables": {
                "recent_issued_books": list(recent_issues),
                "recent_members": list(recent_members),
                "defaulted_members": list(defaulted_members),
            }
        }, status=status.HTTP_200_OK)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all().order_by('-timestamp')
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, CanManageUsers]


class AllHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IssuedBookHistorySerializer
    queryset = BookIssuance.objects.all().order_by('-issue_date')
    permission_classes = [IsAuthenticated, CanManageBooks]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def member_issued_books_view(request, member_id):
    member = get_object_or_404(User, id=member_id, role='MEMBER')

    issued_books = BookIssuance.objects.filter(
        member=member,
        returned_at__isnull=True
    ).select_related('book')

    # ✅ calculate total fine for the member
    fines = Fine.objects.filter(issued_book__member=member)
    total_fine = fines.aggregate(total=Sum('amount'))['total'] or Decimal(0)

    data = []
    for issuance in issued_books:
        book = issuance.book
        data.append({
            "issue_id": issuance.id,
            "issue_date": issuance.issue_date,
            "due_date": issuance.due_date,
            "status": issuance.status,
            "book": {
                "id": book.id,
                "title": book.title,
                "author": book.author,
                "isbn": book.isbn,
                "category": book.category.name if book.category else None,
                "language": book.language.name if book.language else None,
                "department": book.department.name if book.department else None,
                "publisher": book.publisher,
                "edition": book.edition,
                "price": book.price,
            }
        })

    return Response({
        "member": {
            "id": member.id,
            "username": member.username,
            "email": member.email,
            "member_id": getattr(member.profile, "member_id", None),
            "fine_amount": str(total_fine),
            # ✅ added here
            "isDefaulter": getattr(member.profile, "is_defaulter", False)
        },
        "issued_count": len(data),
        "issued_books": data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def book_issued_members_view(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    issuances = BookIssuance.objects.filter(
        book=book, returned_at__isnull=True).select_related('member', 'member__profile')

    data = []
    for issuance in issuances:
        member = issuance.member
        profile = getattr(member, 'profile', None)
        data.append({
            "issue_id": issuance.id,
            "issue_date": issuance.issue_date,
            "due_date": issuance.due_date,
            "status": issuance.status,
            "member": {
                "id": member.id,
                "username": member.username,
                "email": member.email,
                "member_id": getattr(profile, "member_id", None),
                "roll_no": getattr(profile, "roll_no", None),
                "class": getattr(profile, "class_name", None),
                "section": getattr(profile, "section", None),
            }
        })

    return Response({
        "book": {
            "id": book.id,
            "title": book.title,
            "isbn": book.isbn,
            "price": book.price,
        },
        "member_count": len(data),
        "issued_to": data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def returned_book_history_view(request, member_id=None):
    returned_issuances = BookIssuance.objects.filter(
        returned_at__isnull=False
    ).select_related('book', 'member', 'member__profile')

    if member_id:
        returned_issuances = returned_issuances.filter(member_id=member_id)

    history = []
    for issuance in returned_issuances:
        member = issuance.member
        profile = getattr(member, 'profile', None)
        book = issuance.book

        fine_obj = Fine.objects.filter(issued_book=issuance).first()
        fine_amount = fine_obj.amount if fine_obj else 0

        history.append({
            "issue_id": issuance.id,
            "return_date": issuance.returned_at,
            "issued_on": issuance.issue_date,
            "due_date": issuance.due_date,
            "fine_amount": float(fine_amount),
            "book": {
                "id": book.id,
                "title": book.title,
                "isbn": book.isbn,
                "author": book.author,
            },
            "member": {
                "id": member.id,
                "username": member.username,
                "email": member.email,
                "member_id": getattr(profile, "member_id", None),
                "roll_no": getattr(profile, "roll_no", None),
            }
        })

    return Response({
        "returned_count": len(history),
        "history": history
    })


class BookStatusReportView(APIView):
    """
    GET /reports/book-stats/
    """
    def get_permissions(self):
        return [AdminOrGroups(required_permission="core.view_book_report")]
    def get(self, request):
        today = timezone.localdate()

        # 1) All books
        book_qs = Book.objects.all()
        serializer = BookDetailSerializer(book_qs, many=True)
        book_record = serializer.data

        # 2) Currently issued books
        issued_qs = BookIssuance.objects.filter(returned_at__isnull=True)
        serializer = BookIssuanceDetailSerializer(issued_qs, many=True)
        issued_books = serializer.data

        # 3) Overdue books
        overdue_qs = issued_qs.filter(due_date__lt=today)
        overdue_books = [
            {
                "issue_id": i.id,
                "book": i.book.title,
                "member": i.member.username,
                "due_date": i.due_date,
                "days_over": (today - i.due_date).days,
            }
            for i in overdue_qs
        ]

        # 4) Top 10 books by issue count
        top_qs = Book.objects.annotate(
            issue_count=Count('issues')
        ).order_by('-issue_count')[:10]
        top_books = [
            {"id": b.id, "title": b.title, "issue_count": b.issue_count}
            for b in top_qs
        ]

        # 5) Reserved books (assumes you have a Reservation model)
        reserved_qs = BookReservation.objects.filter(status='FULFILLED')
        reserved_books = [
             {
                "reservation_id": r.id,
                "book_id":        r.book.id,
                "book":           r.book.title,
                "member_id":      r.user.id,
                "member":         r.user.username,
                "reserved_at":    r.reserved_at,
                "status":         r.status,
            }
            for r in reserved_qs
        ]

        # 6) Low stock: threshold from LibrarySettings.max_books_per_member? 
        #    Or define a percent threshold in settings, e.g. 10%
        settings_obj = LibrarySettings.objects.first()
        threshold = getattr(settings_obj, 'low_stock_threshold', 5)  # e.g. <=5 copies
        low_stock_qs = Book.objects.filter(available_copies__lte=threshold)
        low_stock = [
            {
                "id": b.id, 
                "title": b.title, 
                "author": b.author,
                "available_copies": b.available_copies, 
                'status': b.status
             }
            for b in low_stock_qs
        ]

        # 7) Inventory moment: total value of all available copies
        inv = Book.objects.aggregate(
            total_value=Sum(
                F('available_copies') * F('price'),
                output_field=DecimalField(max_digits=14, decimal_places=2)
            )
        )['total_value'] or 0

        return Response({
            "book_record":     book_record,
            "issued_books":    issued_books,
            "overdue_books":   overdue_books,
            "top_books":       top_books,
            "reserved_books":  reserved_books,
            "low_stock":       low_stock,
            "inventory_value": inv,
        })
        

class LibraryMembersReport(APIView):
    # 1. Members Record
    def get_permissions(self):
        return [AdminOrGroups(required_permission='core.view_member_report')]
    def get(self, request, *args, **kwargs):
        lib_settings, created = LibrarySettings.objects.get_or_create()
        MAX_BOOKS_PER_MEMBER = lib_settings.max_books_per_member
        members = MemberProfile.objects.select_related(
            'user', 'department', 'session'
        ).all()
        managers = ManagerProfile.objects.select_related('user').all()
        manger_serializer = MangerProfileSerializer(managers, many=True)
        serializer = FullMemberProfileSerializer(members, many=True)
        member_data = serializer.data + manger_serializer.data

        # 2. Defaulters Record
        defaulted_members = User.objects.filter(
            role='MEMBER',
            issued_books__fine__collected=False
        ).annotate(
            unpaid_fine=Sum(
                'issued_books__fine__amount',
                filter=Q(issued_books__fine__collected=False)
            )
        ).distinct().values(
            'id', 'username', 'is_active', 'is_verified', 'unpaid_fine'
        )
        

        # 3. Capped Borrowers (those who have issued MAX_BOOKS_PER_MEMBER)
        capped = (
            MemberProfile.objects
            .annotate(
                issued_count=Count(
                    'user__issued_books',
                    filter=Q(user__issued_books__status='ISSUED')
                )
            )
            .filter(issued_count__gte=MAX_BOOKS_PER_MEMBER)
            .values(
                userId=F('user__id'),
                username=F('user__username'),
                memberId=F('member_id'),
                phone_number=F('mobile_number'),
                defaulter=F('is_defaulter'),
                verified=F('user__is_verified'),
                issued_count=F('issued_count'),
            )
        )


        # 4. Top Readers (based on total number of books ever issued)
        top_readers = BookIssuance.objects.values(
            userId      = F('member__id'),           # the User PK
            username    = F('member__username'),
            memberId    = F('member_id'),            # same as member__id, or your own member_id field
            phone_number= F('member__profile__mobile_number'),
            defaulter   = F('member__profile__is_defaulter'),
            verified    = F('member__is_verified'),)\
            .annotate(total_issued=Count('id'))\
            .order_by('-total_issued')[:15]

        return Response({
            'members': member_data,
            'defaulters': defaulted_members,
            'capped_borrowers': list(capped),
            'top_readers': list(top_readers),
        }, status=status.HTTP_200_OK)
