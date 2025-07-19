from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.conf import settings
from django.conf.urls.static import static
from books.books_views import CategoryViewSet
from .views import (
    AdminDepartmentViewSet, AdminSessionViewSet, AllHistoryViewSet, LanguageViewSet, MemberDepartmentViewSet, MemberSessionViewSet, NotificationLogViewSet,GroupViewSet, PermissionViewSet,UserFineListView,FineViewSet,
    UserHistoryViewSet, DashboardSummaryView, download_membership_card
)

router = DefaultRouter()

router.register(r'fines-viewset', FineViewSet, basename='fine-veiwset')
router.register(r'roles', GroupViewSet, basename='role')
router.register(r'permissions', PermissionViewSet, basename='permission')

router.register(r'categories', CategoryViewSet)
router.register('language', LanguageViewSet, basename='language')
router.register('admin-departments', AdminDepartmentViewSet,
                basename='admin-departments')
router.register('member-departments', MemberDepartmentViewSet,
                basename='member-departments')
router.register('admin-sessions', AdminSessionViewSet,
                basename='admin-sessions')
router.register('member-sessions', MemberSessionViewSet,
                basename='member-sessions')
router.register('notifications-logs', NotificationLogViewSet)
router.register('my-history', UserHistoryViewSet, basename='my-history')
router.register('all-history', AllHistoryViewSet, basename='all-history')

urlpatterns = [
    path('admin/members/<int:member_id>/card/',
         download_membership_card, name='download_card'),
    path('dashboard-summary/', DashboardSummaryView.as_view(), name='dashboard_summary'),
     path(
        'fines/user/<int:user_id>/',
        UserFineListView.as_view(),
        name='user-fine-list'
    ),
    path('', include(router.urls)),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
