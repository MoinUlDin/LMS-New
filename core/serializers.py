from rest_framework import serializers
from .models import AuditLog, Book, BookIssuance, BookReservation, Department,  Fine, Language,  NotificationLog, SessionSettings, User
import logging
from django.contrib.auth.models import Group, Permission

class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['id', 'codename', 'name', 'content_type']

class GroupSerializer(serializers.ModelSerializer):
    # permissions = PermissionSerializer(many=True)
    permissions = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Permission.objects.all()
    )

    class Meta:
        model = Group
        fields = ['id', 'name', 'permissions']
    
    def update(self, instance, validated_data):
        # 1. Pop out the permissions list (if supplied)
        perms = validated_data.pop('permissions', None)

        # 2. Update the name (and any other non-M2M fields)
        instance = super().update(instance, validated_data)

        # 3. If the client sent a permissions list, explicitly set it
        if perms is not None:
            instance.permissions.set(perms)

        return instance


logger = logging.getLogger(__name__)
class UserSerializer(serializers.ModelSerializer):
    member_id = serializers.CharField(
        source='profile.member_id', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'member_id']

class BookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = '__all__'

class FineSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        source='issued_book.member.username',
        read_only=True
    )
    user_id = serializers.CharField(
        source='issued_book.member.id',
        read_only=True
    )
    class Meta:
        model = Fine
        fields = ['id','issued_book', 'remaining_fines', 'user_id', 'username', 'amount', 'collected', 'collected_amount', 'discount', 'created_at', 'cash_in_hand']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        issuance_id = data.get('issued_book')
        if issuance_id is not None:
            try:
                issuance = BookIssuance.objects.select_related('book').get(pk=issuance_id)
                data['book_title'] = issuance.book.title
                data['book_id']    = issuance.book.id
            except BookIssuance.DoesNotExist:
                data['book_title'] = None
                data['book_id']    = None
        return data
    
class NotificationLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    class Meta:
        model = NotificationLog
        fields = ['username', 'message', 'sent_at', 'id' ]

class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = '__all__'
class BookReservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookReservation
        fields = '__all__'
        read_only_fields = ['user', 'reserved_at', 'status']

class IssuedBookHistorySerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source='book.title', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = BookIssuance
        fields = ['id', 'book_title', 'user_name',
                  'issue_date', 'due_date', 'returned_at']





class UpdateUserRoleSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    role = serializers.CharField()


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name']


class SessionSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionSettings
        fields = ['id', 'session_range']

class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = '__all__'