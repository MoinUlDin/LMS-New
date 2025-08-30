from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import AllowAny
from rest_framework.authentication import BasicAuthentication
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from core.views import healthz, internal_provision
from core.views import GetVersionInfo
schema_view = csrf_exempt(SpectacularAPIView.as_view(
    permission_classes=[AllowAny],
    authentication_classes=[],
))

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/schema/', schema_view, name='schema'),
    path('', SpectacularSwaggerView.as_view(
        url_name='schema'), name='swagger-ui'),
    path('books/', include('books.books_urls')),
    path('auth/', include('auth.auth_urls')),
    path('users/', include('users.users_urls')),
    path('reports/', include('reports.reports_urls')),
    path('settings/', include('settings.settings_urls')),
    path("notifications/", include("notifications.urls")),
    path("get_version/",GetVersionInfo.as_view(), name="get_version"),
    path('', include('core.urls')),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('healthz/', healthz),
    path('internal/provision/', internal_provision),
]
