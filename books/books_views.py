from decimal import Decimal
from rest_framework import viewsets, status
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from django.shortcuts import get_object_or_404
from io import TextIOWrapper
from django.utils import timezone
from datetime import datetime
import csv
from rest_framework import serializers
from core.models import Book, User, BookIssuance, BookRequest, BookReservation, Category, Department, Fine, Language, LibrarySettings, NotificationSettings
from core.permissions import CanHandleFines, CanManageBooks, IsAdminOrLibrarian, IsAdminOrSuperuser, ManagerOrGroups, AdminOrGroups
from core.utils import log_action
from .books_serializers import BookDetailSerializer, BookIssuanceDetailSerializer, BookIssuanceSerializer, BookRequestSerializer, BookSerializer, BookReservationSerializer, BulkBookUploadSerializer, CategorySerializer, FineSerializer
from drf_spectacular.utils import extend_schema
from django.contrib.auth import authenticate
from core.scheduler import scheduler
from core.emailServices import send_book_issue_notification, send_reservation_fulfill_email
from rest_framework.response import Response
from .books_serializers import BookDetailSerializer
from core.models import Book, BookIssuance, BookReservation, LibrarySettings
from django.db import IntegrityError


class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()

    def get_serializer_class(self):
        if self.request.method in ['GET', 'HEAD', 'OPTIONS']:
            return BookDetailSerializer
        return BookSerializer

    def get_permissions(self):
        if self.request.method in ['GET', 'HEAD', 'OPTIONS']:
            return [AllowAny()]
        return [CanManageBooks()]

    def perform_create(self, serializer):
        book = serializer.save()
        book.available_copies = book.total_copies

        # Apply rack_no prefix
        settings = LibrarySettings.objects.first()
        if settings and settings.rack_number_format:
            if book.rack_no.isdigit() or not book.rack_no.startswith(settings.rack_number_format):
                book.rack_no = f"{settings.rack_number_format}{book.rack_no}"

        book.save()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        book = serializer.save()
        book.available_copies = book.total_copies

        # Apply rack_no prefix
        settings = LibrarySettings.objects.first()
        if settings and settings.rack_number_format:
            if book.rack_no.isdigit() or not book.rack_no.startswith(settings.rack_number_format):
                book.rack_no = f"{settings.rack_number_format}{book.rack_no}"

        book.save()
        detail_serializer = BookDetailSerializer(book)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='confirm-delete')
    def confirm_delete(self, request, pk=None):
        # Step 1: Get password from request body
        password = request.data.get('password')

        if not password:
            return Response(
                {"detail": "Password is required to delete a book."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Step 2: Authenticate user
        user = authenticate(username=request.user.username, password=password)

        if user is None:
            return Response(
                {"detail": "Password is incorrect."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Step 3: If password is correct, delete the book
        instance = self.get_object()
        self.perform_destroy(instance)

        log_action(
            request.user,
            'BOOK_DELETED',
            f"Book '{instance.title}' has been deleted."
        )

        return Response({"detail": "Book deleted successfully."}, status=status.HTTP_204_NO_CONTENT)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        old_status = instance.status

        serializer = self.get_serializer(
            instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data.get('status', old_status)

        # ✅ Check if status is changing to LOST or WRITE_OFF
        if new_status in ['LOST', 'WRITE_OFF'] and old_status != new_status:
            reason = request.data.get('reason')
            if not reason:
                return Response(
                    {"detail": "Reason is required when changing status to LOST or WRITE_OFF."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            instance.status_reason = reason  # ✅ save reason

        self.perform_update(serializer)

        instance.refresh_from_db()
        new_status = instance.status

        if old_status != new_status:
            if old_status in ['WRITE_OFF', 'LOST'] and new_status == 'ACTIVE':
                instance.available_copies += 1
            elif new_status in ['WRITE_OFF', 'LOST'] and instance.available_copies > 0:
                instance.available_copies -= 1
            instance.save()
            log_action(
                self.request.user,
                'BOOK_STATUS_CHANGE',
                f"Book '{instance.title}' status changed from {old_status} to {new_status}. Reason: {instance.status_reason if new_status in ['LOST', 'WRITE_OFF'] else 'N/A'}"
            )

        detail_serializer = BookDetailSerializer(instance)
        return Response(detail_serializer.data)


@extend_schema(request=None, responses=None)
@api_view(['GET'])
@permission_classes([IsAdminOrSuperuser])
def lost_books_view(request):
    books = Book.objects.filter(status='LOST')
    return Response(BookSerializer(books, many=True).data)


@extend_schema(request=None, responses=None)
class BulkBookUploadView(viewsets.ViewSet):
    parser_classes = [MultiPartParser]
    permission_classes = [IsAuthenticated, CanManageBooks]

    def create(self, request):
        csv_file = request.FILES.get('file')
        if not csv_file:
            return Response({'detail': 'No file provided'}, status=400)

        decoded = TextIOWrapper(csv_file.file, encoding='utf-8')
        reader = csv.DictReader(decoded)
        created, errors = 0, []

        for i, row in enumerate(reader, start=1):
            cleaned_row = {k: (v.strip() if v else '') for k, v in row.items()}
            serializer = BulkBookUploadSerializer(data=cleaned_row)

            if serializer.is_valid():
                category_name = cleaned_row.get('category', '')
                department_name = cleaned_row.get('department', '')
                language_name = cleaned_row.get('language', '')

                # Match case-insensitive and only allow existing values
                category = Category.objects.filter(
                    name__iexact=category_name).first()
                department = Department.objects.filter(
                    name__iexact=department_name).first()
                language = Language.objects.filter(
                    name__iexact=language_name).first()

                if not category or not department or not language:
                    errors.append({
                        f'Row {i}': f"Invalid or missing value(s): "
                        f"{'Category' if not category else ''} "
                        f"{'Department' if not department else ''} "
                        f"{'Language' if not language else ''}".strip()
                    })
                    continue

                try:
                    Book.objects.create(
                        title=cleaned_row['title'],
                        author=cleaned_row['author'],
                        isbn=cleaned_row['isbn'],
                        publisher=cleaned_row.get('publisher', ''),
                        edition=cleaned_row.get('edition', ''),
                        total_copies=int(cleaned_row.get('total_copies', 1)),
                        available_copies=int(
                            cleaned_row.get('total_copies', 1)),
                        rack_no=cleaned_row.get('rack_no', ''),
                        shelf_location=cleaned_row.get('shelf_location', ''),
                        brief_description=cleaned_row.get(
                            'brief_description', ''),
                        category=category,
                        department=department,
                        language=language,
                    )
                    created += 1
                except Exception as e:
                    errors.append({f"Row {i}": f"Unexpected error: {str(e)}"})
            else:
                errors.append({f'Row {i}': serializer.errors})

        log_action(request.user, 'REQUEST', f"Bulk uploaded {created} books")
        return Response({
            'detail': f"{created} books uploaded.",
            'errors': errors
        }, status=status.HTTP_207_MULTI_STATUS if errors else 200)


class BookReservationViewSet(viewsets.ModelViewSet):
    queryset = BookReservation.objects.all()
    serializer_class = BookReservationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_permissions(self):
        # for the `issue` action, return an instance of AdminOrGroups:
        if self.action == 'issue':
            return [AdminOrGroups(required_permission='core.add_bookissuance')]
        if self.action == 'fulfill':
            return [AdminOrGroups(required_permission='core.change_bookreservation')]
        return super().get_permissions()
    @action(
        detail=True,
        methods=['post'],
        url_path='issue',
    )
    def issue(self, request, pk=None):
        """
        POST /bookreservations/{pk}/issue/
        {
          "issue_date": "2025-05-24",
          "due_date":   "2025-05-31"
        }
        """
        reservation = self.get_object()

        # 1) Only pending reservations can be issued
        if reservation.status != 'FULFILLED':
            return Response(
                {"detail": "Only fullfilled reservations can be issued."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2) Extract & parse dates
        issue_str = request.data.get("issue_date")
        due_str   = request.data.get("due_date")
        if not issue_str or not due_str:
            return Response(
                {"detail": "Both issue_date and due_date are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            issue_date = datetime.strptime(issue_str, "%Y-%m-%d").date()
            due_date   = datetime.strptime(due_str,   "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"detail": "Dates must be in YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3) Validate ordering & max duration
        if due_date <= issue_date:
            return Response(
                {"detail": "due_date must be after issue_date."},
                status=status.HTTP_400_BAD_REQUEST
            )

        lib_settings = LibrarySettings.objects.first()
        if not lib_settings:
            return Response(
                {"detail": "Library settings not configured."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        max_days = lib_settings.max_issue_duration
        if (due_date - issue_date).days > max_days:
            return Response(
                {"detail": f"Issuance cannot exceed {max_days} days."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 4) Create the BookIssuance record
        
        try:
            issuance = BookIssuance.objects.create(
                book=reservation.book,
                member=reservation.user,
                issue_date=issue_date,
                due_date=due_date,
            )
        except Exception as e:
            raise serializers.ValidationError({
                "non_field_errors": [str(e)]
            })

        # 5) Update reservation status
        reservation.status = 'ISSUED'
        reservation.save()
        
        try:
            log_action(
                user=self.request.user,
                action_type='BOOK_ISSUED',
                description=f"Reserved book '{reservation.book.title}' Issued to '{reservation.user.username}'."
            )
        except Exception as e:
            print(f'\nError Issuance log in reservation {e}\n')
            pass

        # 6) Return the newly‐issued object (or just a detail message)
        return Response(
            {
                "detail": "Reservation successfully issued.",
                "issuance_id": issuance.id
            },
            status=status.HTTP_201_CREATED
        )

    def create(self, request, *args, **kwargs):
        data = request.data
        book = data['book']
        member = request.user
        r_from = data.get('reserved_from')
        r_to = data.get('reserved_to')

        if not r_from or not r_to:
            return Response(
                {"detail": "reserved_from and reserved_to fields are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            reserved_from = datetime.strptime(r_from, "%Y-%m-%d").date()
            reserved_to = datetime.strptime(r_to, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"detail": "Dates must be in YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if reserved_from >= reserved_to:
            return Response(
                {"detail": "reserved_from must be earlier than reserved_to."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        today = timezone.now().date()

        if reserved_from < today:
            return Response(
                {"detail": "reserved_from date must be in the future."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        lib_settings = LibrarySettings.objects.first()
        if not lib_settings:
            return Response(
                {"detail": "Library settings are not configured."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        max_days = lib_settings.max_issue_duration
        delta_days = (reserved_to - reserved_from).days

        if delta_days > max_days:
            return Response(
                {"detail": f"Reservation duration cannot exceed {max_days} days."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        has_one = BookIssuance.objects.filter( 
                book=book,
                member=member,
                returned_at__isnull=True
                )
        if has_one:
            return Response({"detail": "You already has this book issued and not yet returned."}, status=status.HTTP_400_BAD_REQUEST)

        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        book = serializer.validated_data['book']
        try:
            reservation = serializer.save(user=self.request.user)
            
            try:
                log_action(
                    user=self.request.user,
                    action_type='Reservation Request',
                    description=(
                    f"Reservation request created for Book '{reservation.book.title}' "
                    f"by user '{reservation.user.username}'. "
                    f"Status is '{reservation.status}'."
                )
                )
            except Exception as e:
                print(f'\nError reservation request log {e}\n')
                pass
            
        except IntegrityError:
            raise serializers.ValidationError({
              "book": "You already have an active reservation for this book."
            })
    
    @action(detail=False, methods=['get'], url_path='by-member/(?P<user_id>[^/.]+)')
    def by_member(self, request, user_id=None):
        """
        Return all reservations for a given member (user ID).
        Only accessible by admins or the user themself.
        """
        try:
            member = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if request.user != member and not request.user.is_staff:
            return Response({"detail": "Not authorized to view this user's reservations."}, status=403)

        reservations = BookReservation.objects.filter(user=member)
        serializer = self.get_serializer(reservations, many=True)
        return Response(serializer.data)
        
    @action(detail=True, methods=['post'])
    def fulfill(self, request, pk=None):
        reservation = self.get_object()
        book = reservation.book
        
        if reservation.status != 'PENDING':
            return Response({'detail': 'Already fulfilled/cancelled'}, status=400)
        
        print("book", book, "id", book.id, "\navailable: ", book.available_copies ,'\n')
        if book.available_copies <= 0:
            return Response({'detail': 'No Availabel Copeis, cannot be fulfilled'}, status=400)
        
        book.available_copies -= 1
        book.save()
        
        reservation.status = 'FULFILLED'
        reservation.save()
        
        job_id = f"reservation_notify_{reservation.pk}"
        # remove any existing duplicate
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)

        # schedule it to run right now, one-off
        scheduler.add_job(
            func=send_reservation_fulfill_email,
            args=[reservation.pk],
            next_run_time=timezone.now(),
            id=job_id,
            replace_existing=True,
        )
        
        try:
            log_action(
                user=self.request.user,
                action_type='Reservation Fulfilled',
                description=f"Book '{reservation.book.title}' reservation Request by '{reservation.user.username}' fulfilled(Accepted)."
            )
        except Exception as e:
            print(f'\nError Issuance log in reservation {e}\n')
            pass
        return Response({'detail': 'Reservation fulfilled and user will be notified'})
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        Allows the owner to cancel a PENDING reservation.
        """
        reservation = self.get_object()
        if reservation.user != request.user:
            return Response({"detail": "Not your reservation."}, status=403)

        if reservation.status != 'PENDING':
            return Response(
                {"detail": "Only pending reservations can be cancelled."},
                status=400
            )

        reservation.status = 'CANCELLED'
        reservation.save()
        try:
            log_action(
                user=self.request.user,
                action_type='RESERVATION CANCELLED',
                description=(
                f"Reservation request for Book '{reservation.book.title}' "
                f"Cancelled by user '{reservation.user.username}'. "
            )
            )
        except Exception as e:
            print(f'\nError reservation request log {e}\n')
            pass
        return Response(
            BookReservationSerializer(reservation).data,
            status=200
        )


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    def get_permissions(self):
        if self.request.method == "POST":
            return [AdminOrGroups(required_permission='core.add_category')]
        if self.request.method in ["PUT", "PATCH"]:
            return [AdminOrGroups(required_permission='core.change_ategory')]
        if self.request.method == "DELETE":
            return [AdminOrGroups(required_permission='core.delete_ategory')]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        print("✅ POST request received for Category")
        return super().create(request, *args, **kwargs)


class FineViewSet(viewsets.ModelViewSet):
    queryset = Fine.objects.all()
    serializer_class = FineSerializer
    permission_classes = [IsAuthenticated, CanHandleFines]


@api_view(['GET'])
@permission_classes([IsAdminOrSuperuser])
def lost_books_view(request):
    books = Book.objects.filter(status='LOST')
    serializer = BookSerializer(books, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAdminOrSuperuser])
def write_off_books_view(request):
    books = Book.objects.filter(status='WRITE_OFF')
    serializer = BookSerializer(books, many=True)
    return Response(serializer.data)


class BookRequestViewSet(viewsets.ModelViewSet):
    queryset = BookRequest.objects.all()
    serializer_class = BookRequestSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrLibrarian])
    def approve(self, request, pk=None):
        request_obj = self.get_object()
        if request_obj.status != 'PENDING':
            return Response({'detail': 'Request already handled.'}, status=400)
        request_obj.status = 'APPROVED'
        request_obj.responded_at = timezone.now()
        request_obj.save()
        
        return Response({'detail': 'Request approved.'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrLibrarian])
    def reject(self, request, pk=None):
        request_obj = self.get_object()
        if request_obj.status != 'PENDING':
            return Response({'detail': 'Request already handled.'}, status=400)
        request_obj.status = 'REJECTED'
        request_obj.responded_at = timezone.now()
        request_obj.save()
        return Response({'detail': 'Request rejected.'})


class IssuedBookViewSet(viewsets.ModelViewSet):
    queryset = BookIssuance.objects.filter(returned_at__isnull=True)
    method_permissions = {
      'GET':    'core.view_bookissuance',
      'POST':   'core.add_bookissuance',
      'PUT':    'core.change_bookissuance',
      'PATCH':  'core.change_bookissuance',
      'DELETE': 'core.delete_bookissuance',
    }

    def get_serializer_class(self):
        if self.request.method in ['GET', 'HEAD', 'OPTIONS']:
            return BookIssuanceDetailSerializer  # show full info
        return BookIssuanceSerializer

    @action(detail=True, methods=['post'], url_path='return')
    def return_book(self, request, pk=None):
        issued = self.get_object()

        # If the book is already returned
        if issued.returned_at:
            return Response(
                {"detail": "Book has already been returned."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 🎯 Get input values
        fine_collected_amount = Decimal(
            request.data.get('fine_collected_amount', 0))
        discount = Decimal(request.data.get('discount', 0))
        # The status can be 'LOST', 'WRITE_OFF', or 'RETURNED'
        book_status = request.data.get('status', 'RETURNED')
        return_date_str = request.data.get('returnDate')

        # Validate return date
        if return_date_str:
            try:
                return_date = datetime.strptime(
                    return_date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response({"detail": "Invalid returnDate format. Use YYYY-MM-DD."},
                                status=status.HTTP_400_BAD_REQUEST)
        else:
            return_date = timezone.now().date()

        # Update issuance status and return date
        issued.returned_at = return_date
        issued.status = book_status
        issued.save()

        # Handle book availability based on the status
        book = issued.book

        if book_status == 'RETURNED':
            # Only increase available copies if the book is returned and not lost or written off
            book.available_copies += 1

        # Save the updated book status and available copies
        if book_status in ['LOST', 'WRITE_OFF']:
            book.status = book_status
        book.save()
        # 🎯 Calculate fines if overdue
        overdue_fine = Decimal(0)
        library_obj = LibrarySettings.objects.first()
        fine_per_day = library_obj.fine_per_day or 0
        if return_date > issued.due_date:
            days_late = (return_date - issued.due_date).days
            overdue_fine = Decimal(days_late * fine_per_day)

        # 🎯 Book price
        book_price = Decimal(book.price or 0)

        total_fine = overdue_fine
        if book_status in ['LOST', 'WRITE_OFF']:
            total_fine += book_price

        remaining_fine = total_fine - (fine_collected_amount + discount)
        remaining_fine = max(Decimal(0), remaining_fine)

        # 🎯 Save fine record
        fine_obj, created = Fine.objects.update_or_create(
            issued_book=issued,
            defaults={
                'amount': total_fine,
                'cash_in_hand': fine_collected_amount,
                'collected_amount': fine_collected_amount,
                'discount': discount,
                'collected': remaining_fine <= 0
            }
        )

        # 🎯 Update defaulter status
        if remaining_fine > 0:
            issued.member.profile.is_defaulter = True
        
        issued.member.profile.save()
        issued.member.refresh_from_db()

        # 🎯 Logging and response
        return Response({
            "book": book.id,
            "member": issued.member.id,
            "returnDate": issued.returned_at,
            "status": book_status,  # 'LOST', 'WRITE_OFF', or 'RETURNED'
            "fine_details": {
                "overdue_fine": str(overdue_fine),
                "book_price": str(book_price) if book_status in ['LOST', 'WRITE_OFF'] else None,
                "total_fine": str(total_fine),
                "fineCollectedAmount": str(fine_collected_amount),
                "discount": str(discount),
                "remaining_fine": str(remaining_fine)
            },
            "isDefaulter": issued.member.profile.is_defaulter
        }, status=status.HTTP_200_OK)  # This line should work now

    def get_permissions(self):
        perm = self.method_permissions.get(self.request.method)
        if not perm:
            return [IsAuthenticated()]  # or deny by default
        return [AdminOrGroups(required_permission=perm)]

    def perform_create(self, serializer):
        book = serializer.validated_data['book']
        member = serializer.validated_data['member']

        if book.available_copies < 1:
            raise ValidationError("No available copies for this book.")

        if BookIssuance.objects.filter(book=book, member=member, returned_at__isnull=True).exists():
            raise ValidationError(
                "This member already has this book issued and not yet returned.")

        # ✅ Check max allowed issuance
        settings = LibrarySettings.objects.first()
        max_allowed = settings.max_books_per_member if settings else 3

        currently_issued = BookIssuance.objects.filter(
            member=member, returned_at__isnull=True).count()
        if currently_issued >= max_allowed:
            raise ValidationError(
                f"This member already has {currently_issued} books issued. Max allowed is {max_allowed}.")

        book.available_copies -= 1
        book.save()

        serializer.save()
        issued = serializer.instance
        log_action(
            self.request.user,
            'BOOK_ISSUED',
            f"Book '{book.title}' issued to {member.username}."
        )
        
        notif_settings = NotificationSettings.objects.first()
        if notif_settings and notif_settings.on_book_issue:
            scheduler.add_job(
                send_book_issue_notification,
                args=[issued.id],
                next_run_time=timezone.now(),
                id=f"issue_notify_{issued.id}",
                replace_existing=True,)
            

