from django.urls import path
from .reports_views import book_issued_members_view, BookStatusReportView, LibraryMembersReport, DashboardSummaryView, AuditLogViewSet, AllHistoryViewSet, member_issued_books_view, returned_book_history_view
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'audit-logs', AuditLogViewSet)
router.register(r'issue-history', AllHistoryViewSet)

urlpatterns = [
    path('dashboard/', DashboardSummaryView.as_view(), name="dashboard"),
    path('reports/member', LibraryMembersReport.as_view(), name="member-reports"),
    path('members/<int:member_id>/issued-books/', member_issued_books_view),
    path('books/<int:book_id>/issued-members/', book_issued_members_view),
    path('books/returned-history/', returned_book_history_view),
    path('returned-books/<int:member_id>/', returned_book_history_view,
         name='returned-book-history-member'),
    path('book-status/', BookStatusReportView.as_view(), name="report-book-status")

] + router.urls
