from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from core.models import Department, User, MemberProfile, ManagerProfile
from django.core.mail import send_mail
from django.db import IntegrityError
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from core.scheduler import scheduler
from core.emailServices import send_welcome_email
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging

from core.utils import log_action
logger = logging.getLogger(__name__)

User = get_user_model()


def send_verification_email(user):
    try:
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        verification_link = f"{settings.FRONTEND_URL}auth/verify-email/{uid}/{token}/"

        send_mail(
            subject="Verify Your Email",
            message=f"Click the link to verify your account: {verification_link}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(f"Verification email sent to {user.email}")
    except Exception as e:
        logger.error(f"Error sending verification email: {e}")


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)

        if not self.user.is_verified and not (self.user.is_superuser or self.user.is_staff):
            raise serializers.ValidationError(
                "Please verify your email before logging in."
            )

        if not self.user.is_active:
            raise serializers.ValidationError(
                "Your account is pending admin approval."
            )
        if self.user.is_declined:
            raise serializers.ValidationError(
                "Your account has been declined by the admin.")

        data.update({'username': self.user.username,'role': self.user.role, "id": self.user.id})
        return data


class MemberRegisterSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all())
    session = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), source='session_id')

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username',
                  'email', 'password', 'password2', 'department', 'session']

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError("Passwords do not match")
        return data

    def create(self, validated_data):
        validated_data.pop('password2')

        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            role='MEMBER',
            is_active=False
        )

        last_profile = MemberProfile.objects.order_by('-id').first()
        serial_id = f"MBR-{(last_profile.id + 1) if last_profile else 1:04d}"

        MemberProfile.objects.create(
            user=user,
            member_id=serial_id,
            shift='DAY',
            security_fee=0.00
        )

        return user

    def to_representation(self, instance):
        return {
            "first_name": instance.first_name,
            "last_name": instance.last_name,
            "username": instance.username,
            "email": instance.email,
            "role": instance.role,
            "member_id": instance.profile.member_id if hasattr(instance, 'profile') else None
        }


class ManagerRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)
    member_id = serializers.CharField(write_only=True)
    contact_number = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'password',
                  'password2', 'role', 'member_id', 'contact_number']
        read_only_fields = ['role']

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError("Passwords do not match")


        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        validated_data.pop('role', None)  # 🔒 ignore client input
        validated_data['role'] = 'MANAGER'

        member_id = validated_data.pop('member_id')
        contact_number = validated_data.pop('contact_number', None)

        try:
            with transaction.atomic():
                user = User.objects.create_user(**validated_data)
                user.is_active = True
                user.is_verified = True
                user.save()

                ManagerProfile.objects.create(
                    user=user,
                    member_id=member_id,
                    contact_number=contact_number
                )
            return user

        except IntegrityError as e:
            if "unique constraint" in str(e).lower() and "member_id" in str(e).lower():
                raise serializers.ValidationError({
                    "detail": "This member ID is already in use."
                })
            raise serializers.ValidationError("An error occurred while creating the manager profile.")
  

class SingleMemberRegisterSerializer(serializers.ModelSerializer):
    profile_photo = serializers.ImageField(required=False)
    payment_proof = serializers.ImageField(required=False)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username',
                  'email', 'password', 'payment_proof', 'profile_photo',
                  ]

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop('password')
        profile_photo = validated_data.pop('profile_photo', None)
        payment_proof = validated_data.pop('payment_proof', None)

        # Now only user-related fields remain
        user = User.objects.create_user(
            **validated_data,
            password=password,
            role='MEMBER',
            is_active=True,
            is_verified=True
        )

        # Generate member ID
        last_profile = MemberProfile.objects.order_by('-id').first()
        member_id = f"MBR-{(last_profile.id + 1) if last_profile else 1:04d}"

        # Create the profile
        data = self.context['request'].data
        cnic = (data.get('cnic') or '').strip()
        mobile_number = (data.get('mobile_number') or '').strip()

        # Validate lengths with DRF errors
        if cnic and len(cnic) > 14:
            raise serializers.ValidationError({"detail": "CNIC too long (max 14 chars)."})
        if mobile_number and len(mobile_number) > 15:
            raise serializers.ValidationError({"detail": "Mobile number too long (max 15 chars)."})

        # Create user
        MemberProfile.objects.create(
            user=user,
            member_id=member_id,
            middle_name=self.context['request'].data.get('middle_name', ''),
            father_first_name=self.context['request'].data.get(
                'father_first_name', ''),
            father_last_name=self.context['request'].data.get(
                'father_last_name', ''),
            profile_photo=profile_photo,
            class_name=self.context['request'].data.get('class_name', ''),
            section=self.context['request'].data.get('section', ''),
            mobile_number=self.context['request'].data.get(
                'mobile_number', ''),
            cnic=self.context['request'].data.get('cnic', ''),
            department_id=self.context['request'].data.get('department'),
            session_id=self.context['request'].data.get('session'),
            registration_id=self.context['request'].data.get(
                'registration_id', ''),
            roll_no=self.context['request'].data.get('roll_no', ''),
            shift=self.context['request'].data.get('shift', 'DAY'),
            security_fee=self.context['request'].data.get(
                'security_fee', 0.00),
            payment_proof=payment_proof,
            home_address=self.context['request'].data.get('home_address', ''),
            emergency_contact=self.context['request'].data.get(
                'emergency_contact', ''),
            library_membership_id=self.context['request'].data.get(
                'library_membership_id', '')
        )

        # Send welcome email
        from django.core.mail import send_mail
        
        scheduler.add_job(
                func=send_welcome_email,
                args=[user.id, password],
                next_run_time=timezone.now(),
                id=f"welcomEmail_{user.username}",
                replace_existing=True,)

        return user

class ManagerProfileSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = ManagerProfile
        fields = ['user_id', 'username', 'email', 'member_id', 'contact_number', 'notes']