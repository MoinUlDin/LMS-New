from django.urls import path
from .auth_views import (
    CustomTokenObtainPairView,
    MemberRegisterView,
    ManagerRegisterView,
    SingleRegisterMemberView,
    ApproveUserView,
    decline_user,
    restore_user,
    verify_email,
    ForgotPasswordView,
    ResetPasswordView,
    ManagerProfileViewSet
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'manager-profile', ManagerProfileViewSet, basename='manager-profile')
urlpatterns = [
    path('Single-Member-Register/', SingleRegisterMemberView.as_view(),
         name='admin-register-member'),
    path('login/', CustomTokenObtainPairView.as_view()),
    path('register/member/', MemberRegisterView.as_view()),
    path('register/manager/', ManagerRegisterView.as_view()),
    path('verify-email/<uidb64>/<token>/', verify_email),
    path('forgot-password/', ForgotPasswordView.as_view()),
    path('reset-password/<uidb64>/<token>/', ResetPasswordView.as_view()),
    path('approve-user/<int:user_id>/',
         ApproveUserView.as_view(), name='approve_user'),
    path('decline/<int:user_id>/', decline_user, name='decline-user'),
    path('restore/<int:user_id>/', restore_user, name='restore-user'),
]

urlpatterns += router.urls