from django.urls import path
from .users_views import (
    AdminUserUpdateView,
    BulkMemberUploadView,
    UpdateMemberProfileView,
    AllMembersView,
    MemberViewSet,
    SingleMemberProfileView,
    DisabledMembersList,
    ToggleMemberStatus,
    UpdateManagerProfileView,
    approved_members,
    declined_users,
    pending_users,
    update_user_role,
    delete_user,
    whoami,
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

router.register(r'meberview', MemberViewSet, basename='memberView')

urlpatterns = [
    path('disabled-members/', DisabledMembersList.as_view(), name='disabled-members'),
    path('bulk-upload-members/', BulkMemberUploadView.as_view(),
         name='bulk-member-upload'),
    path("member/<int:user_id>/disable_enable/",
         ToggleMemberStatus.as_view(), name="toggle-member-status"),
    path("all-members/",  AllMembersView.as_view(), name='all-members'),
    path('members/<int:user_id>/profile/', SingleMemberProfileView.as_view(), name='single-member-profile'),
    path("update-profile/", UpdateMemberProfileView.as_view(),
         name="update-member-profile"),
    path("update-manager-profile/", UpdateManagerProfileView.as_view(),
         name="update-manager-profile"),
    path('update-role/', update_user_role),
    path('delete/<int:user_id>/', delete_user),
    path('pending-users/', pending_users, name='pending_users'),
    path('declined/', declined_users, name='declined-users'),
    path('approved/', approved_members, name='approved-members'),
    path('admin/profile/', AdminUserUpdateView.as_view()),

    path('whoami/', whoami),
] + router.urls
