from decimal import Decimal
from rest_framework import serializers
from auth.auth_serializers import send_verification_email
from core.models import Fine, User, MemberProfile, ManagerProfile
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _


class AdminUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    profile_photo = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "profile_photo",
        ]
        read_only_fields = ["id"]

    def update(self, instance, validated_data):

        password = validated_data.pop("password", None)
        new_photo = validated_data.pop("profile_photo", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        if new_photo is not None:
            instance.profile_photo = new_photo

        instance.save()
        return instance

class UserSerializer(serializers.ModelSerializer):
    member_id = serializers.CharField(
        source='profile.member_id', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email',
                  'role', 'member_id', 'is_verified', 'first_name', 'last_name', 'is_active']


class MemberProfileUpdateSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(
        source='user.first_name', required=False)
    last_name = serializers.CharField(source='user.last_name', required=False)
    role = serializers.ChoiceField(
        source='user.role',
        choices=User.Role.choices,
        required=False
    )
    class Meta:
        model = MemberProfile
        fields = [
            'first_name', 'role', 'last_name', 'middle_name', 'father_first_name', 'father_last_name', 'profile_photo', 'class_name', 'section', 'cnic',
            'department', 'session', 'registration_id', 'roll_no',
            'shift', 'mobile_number', 'security_fee', 'payment_proof', 'member_id', 'home_address', 'emergency_contact', 'library_membership_id'
        ]

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        user = instance.user
        user.first_name = user_data.get('first_name', user.first_name)
        user.last_name = user_data.get('last_name', user.last_name)
        user.save()
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance


class MangerProfileSerializer(serializers.ModelSerializer):
    # These fields pull from the related User model
    is_verified = serializers.BooleanField(source='user.is_verified', read_only=True)
    is_declined = serializers.BooleanField(source='user.is_declined', read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)

    # Writable fields on the User model
    first_name = serializers.CharField(source='user.first_name', required=True)
    last_name = serializers.CharField(source='user.last_name', required=True)
    username = serializers.CharField(source='user.username', required=True)
    email = serializers.EmailField(source='user.email', required=True)
    role = serializers.CharField(source='user.role', required=True)

    # Password fields (all optional)
    old_password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    new_password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    confirm_password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = ManagerProfile
        fields = [
            'role',
            'email',
            'username',
            'user_id',
            'profile_photo',
            'first_name',
            'last_name',
            'is_verified',
            'is_declined',
            'is_active',
            'member_id',
            'contact_number',
            'old_password',
            'new_password',
            'confirm_password',
        ]
        read_only_fields = ['user_id', 'is_verified', 'is_declined', 'is_active']

    def validate(self, attrs):
        """
        If any one of old_password/new_password/confirm_password is provided,
        require all three and validate them. Otherwise allow partial update.
        """
        old_pw = attrs.get('old_password')
        new_pw = attrs.get('new_password')
        confirm_pw = attrs.get('confirm_password')

        # Only run password logic if at least one is present and not blank
        if old_pw or new_pw or confirm_pw:
            missing = []
            if not old_pw:
                missing.append('old_password')
            if not new_pw:
                missing.append('new_password')
            if not confirm_pw:
                missing.append('confirm_password')
            if missing:
                raise ValidationError(
                    {field: "This field is required to change password." for field in missing}
                )

            # Verify old password is correct
            user = self.instance.user if self.instance else None
            if user and not user.check_password(old_pw):
                raise ValidationError({'old_password': 'Old password is not correct.'})

            # Ensure new_password and confirm_password match
            if new_pw != confirm_pw:
                raise ValidationError({'confirm_password': 'New password and confirm password must match.'})

        return super().validate(attrs)

    def update(self, instance: ManagerProfile, validated_data: dict) -> ManagerProfile:
        # Handle nested user fields first
        user_data = validated_data.pop('user', {})

        if user_data:
            user = instance.user
            for attr, value in user_data.items():
                setattr(user, attr, value)
            user.save()

        # Handle optional password change
        old_pw = validated_data.pop('old_password', None)
        new_pw = validated_data.pop('new_password', None)
        confirm_pw = validated_data.pop('confirm_password', None)

        if old_pw and new_pw and confirm_pw:
            user = instance.user
            # At this point, validate() already ensured old_pw is correct and new_pw == confirm_pw
            user.set_password(new_pw)
            user.save()

        # Update ManagerProfile fields (profile_photo, member_id, contact_number)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance

    def validate_username(self, value):
        """
        Ensure username uniqueness on User model.
        """
        user_qs = User.objects.filter(username=value)
        if self.instance and self.instance.user.username == value:
            return value
        if user_qs.exists():
            raise ValidationError("That username is already taken.")
        return value

    def validate_email(self, value):
        """
        Ensure email uniqueness on User model.
        """
        user_qs = User.objects.filter(email=value)
        if self.instance and self.instance.user.email == value:
            return value
        if user_qs.exists():
            raise ValidationError("That email is already in use.")
        return value
    
class FullMemberProfileSerializer(serializers.ModelSerializer):
    # Use BooleanField for boolean values
    is_verified = serializers.BooleanField(source='user.is_verified')
    is_declined = serializers.BooleanField(source='user.is_declined')
    is_active = serializers.BooleanField(source='user.is_active')
    # Include user_id instead of MemberProfile's ID
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    username = serializers.CharField(source='user.username')
    role = serializers.CharField(source='user.role')
    fine_amount = serializers.SerializerMethodField()

    class Meta:
        model = MemberProfile
        fields = [
            'role',
            'user_id',
            'first_name', 'last_name', 'middle_name',
            'father_first_name', 'father_last_name', 'profile_photo',
            'class_name', 'section', 'mobile_number', 'cnic', 'department',
            'session', 'registration_id', 'roll_no', 'shift', 'security_fee',
            'payment_proof', 'member_id', 'home_address', 'emergency_contact',
            'library_membership_id', 'username', 'is_verified', 'is_declined',
            'is_active', 'is_defaulter', 'fine_amount'
        ]

    def get_fine_amount(self, obj):
        # Fetch all fines for this member via related issued books
        fines = Fine.objects.filter(issued_book__member=obj.user)
        total_fine = fines.aggregate(total=Sum('amount'))[
            'total'] or Decimal(0)
        return str(total_fine)


class BulkMemberUploadSerializer(serializers.Serializer):
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    username = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField()
    department = serializers.IntegerField()
    session = serializers.IntegerField()


class UpdateUserRoleSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    role = serializers.CharField()
