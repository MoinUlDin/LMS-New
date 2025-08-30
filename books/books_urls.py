from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .books_views import BookRequestViewSet, BookViewSet, BookReservationViewSet, IssuedBookViewSet, lost_books_view, write_off_books_view, BulkBookUploadView

router = DefaultRouter()
router.register(r'books', BookViewSet)
router.register(r'issued-books', IssuedBookViewSet)
router.register(r'reservations', BookReservationViewSet)

router.register(r'requests', BookRequestViewSet)
urlpatterns = [
    path('', include(router.urls)),
    path('lost/', lost_books_view),
    path('write-off/', write_off_books_view),
    path('bulk-upload/', BulkBookUploadView.as_view({'post': 'create'})),
]
