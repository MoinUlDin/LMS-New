from rest_framework.routers import DefaultRouter
from .views import WishlistViewSet, NotificationViewSet
from django.urls import path, include


router = DefaultRouter()

router.register(r"wishlist", WishlistViewSet,     basename="wishlist")
router.register(r"alerts",   NotificationViewSet, basename="alert")


urlpatterns = [
    path("", include(router.urls)),
]