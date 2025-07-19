from django.urls import path
from .settings_views import FeatureViewSet,  LibrarySettingsView, ModuleViewSet, NotificationSettingsView, RolePermissionViewSet, get_library_settings
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'role-permissions', RolePermissionViewSet,
                basename='role-permission')
router.register(r'modules', ModuleViewSet, basename='module')
router.register(r'features', FeatureViewSet, basename='feature')
urlpatterns = [

    path('Books_settings/', get_library_settings, name='setting_book_limit'),
    path('notifications/', NotificationSettingsView.as_view(), name='notification-settings'),
    path('library/', LibrarySettingsView.as_view(),
         name='library-settings'),
]
