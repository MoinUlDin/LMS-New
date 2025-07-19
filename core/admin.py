from .models import Department, LibrarySettings, BookReservation, NotificationLog, SessionSettings, User, Book, Category, MemberProfile, BookIssuance, Fine
from django.contrib import admin
from django.contrib.auth.models import Permission

admin.site.register(Permission)

admin.site.register(User)
admin.site.register(Book)
admin.site.register(Category)
admin.site.register(MemberProfile)
admin.site.register(BookIssuance)
admin.site.register(NotificationLog)
admin.site.register(Department)
admin.site.register(SessionSettings)

@admin.register(Fine)
class FineAdmin(admin.ModelAdmin):
    list_display= ['issued_book', 'amount', 'collected_amount', 'collected', 'created_at']
    list_filter = ['collected', 'created_at']

@admin.register(BookReservation)
class BookReservationAdmin(admin.ModelAdmin):
    list_display = ('book', 'user', 'status' , 'reserved_from', 'reserved_to', 'reserved_at', 'agreed')
    list_filter = ('status', 'book')


@admin.register(LibrarySettings)
class LibrarySettingsAdmin(admin.ModelAdmin):
    list_display = ['max_books_per_member']

