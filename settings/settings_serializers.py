from rest_framework import serializers
from core.models import Feature, LibrarySettings, Module, RolePermission, NotificationSettings


class LibrarySettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = LibrarySettings
        fields = '__all__'


class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ['id', 'name']


class FeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feature
        fields = ['id', 'name', 'module']


class RolePermissionSerializer(serializers.ModelSerializer):
    feature_name = serializers.CharField(source='feature.name', read_only=True)
    module_name = serializers.CharField(
        source='feature.module.name', read_only=True)

    class Meta:
        model = RolePermission
        fields = ['id', 'role', 'feature', 'feature_name',
                  'module_name', 'can_view', 'can_add', 'can_edit', 'can_delete']
    
class NotificationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationSettings
        fields = [
            "on_book_issue",
            "on_due_date",
            "on_reservation_request",
            "on_fine_imposition",
            "on_fine_collection",
        ]