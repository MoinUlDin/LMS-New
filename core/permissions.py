from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.permissions import DjangoModelPermissions
from rest_framework import serializers
from django.contrib.auth.models import Permission, Group
from core.models import RolePermission
from core.models import User

class IsAdminOrLibrarian(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.role in ['ADMIN', 'SUPER USER', 'MANAGER']
        )


class IsAdminOrSuperuser(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.role in [
                'ADMIN', 'SUPER USER'] or request.user.is_superuser
        )

class CanViewAllMembers(BasePermission):
    """
    Allow access if the user has the 'view_all_members' permission
    or is in ADMIN / SUPER_USER roles or is_superuser.
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        # 1) Check the real Django permission
        if user.has_perm("core.view_all_members"):
            return True

        # 2) Fallback: check role or superuser
        return (
            user.is_superuser or
            user.role in {User.Role.SUPER_USER}
        )
        
        
class IsMember(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'MEMBER'

class IsProfileOwner(BasePermission):
    """
    Only allow the user who owns this ManagerProfile to view/update it.
    """
    def has_object_permission(self, request, view, obj):
        # obj is a ManagerProfile instance
        return obj.user == request.user

class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS


ROLE_MAP = {
    'manage_books': ['ADMIN', 'SUPER USER', 'MANAGER'],
    'issue_books': ['ADMIN', 'SUPER USER', 'MANAGER'],
    'return_books': ['ADMIN', 'SUPER USER', 'MANAGER'],
    'handle_fines': ['ADMIN', 'SUPER USER', 'MANAGER'],
    'view_requests': ['ADMIN', 'SUPER USER', 'MANAGER'],
    'manage_users': ['ADMIN', 'SUPER USER', 'MANAGER'],
}


def has_role(user, allowed_roles):
    return user.is_authenticated and user.role in allowed_roles


class CanManageBooks(BasePermission):
    def has_permission(self, request, view):
        return has_role(request.user, ROLE_MAP['manage_books'])

class CanViewDashboard(BasePermission):
    """
    Allow access if the user has the 'view_dashboard' permission (via groups or user_perm),
    or if their `user.role` CharField is SUPER_USER or MANAGER.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        # 1) Check the real Django permission first
        if user.has_perm("core.view_dashboard_summary"):
            return True

        # 2) Fallback: check the role CharField
        return user.role in {
            User.Role.SUPER_USER,
            User.Role.MANAGER,
        }
        

class ManagerOrGroups(BasePermission):
    elevated_roles = { User.Role.SUPER_USER, User.Role.MANAGER }

    def __init__(self, required_permission=None):
        self.required_permission = required_permission

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser or user.role in self.elevated_roles:
            return True

        # now check *only* the one perm for this action
        return bool(self.required_permission and user.has_perm(self.required_permission))

class AdminOrGroups(BasePermission):
    elevated_roles = { User.Role.SUPER_USER }

    def __init__(self, required_permission=None):
        self.required_permission = required_permission

    def has_permission(self, request, view):
        user = request.user
        print("\nUser",user.is_superuser)
        if not user.is_authenticated:
            return False
        if user.is_superuser or user.role in self.elevated_roles:
            return True
        
        # now check *only* the one perm for this action
        return bool(self.required_permission and user.has_perm(self.required_permission))

class CanManageUsers(BasePermission):
    def has_permission(self, request, view):
        return has_role(request.user, ROLE_MAP['manage_users'])


class CanIssueReturn(BasePermission):
    def has_permission(self, request, view):
        return has_role(request.user, ROLE_MAP['issue_books'] + ROLE_MAP['return_books'])


class CanHandleFines(BasePermission):
    def has_permission(self, request, view):
        return has_role(request.user, ROLE_MAP['handle_fines'])


class CanViewRequests(BasePermission):
    def has_permission(self, request, view):
        return has_role(request.user, ROLE_MAP['view_requests'])


class DenyAllPermission(BasePermission):
    def has_permission(self, request, view):
        return False


def has_feature_permission(user, feature_name, permission_type):
    try:
        role = user.role
        permission = RolePermission.objects.get(
            role=role, feature__name=feature_name)
        return getattr(permission, f'can_{permission_type}', False)
    except RolePermission.DoesNotExist:
        return False


class RoleBasedPermission(DjangoModelPermissions):
    """
    - Uses standard `add`, `change`, `delete`, `view` permissions for CRUD.
    - You can hook in custom action → permission mappings by overriding `perms_map`.
    """
    # DRF’s default perms_map handles GET→view, POST→add, etc.
    # If you have custom viewset actions (e.g. @action(detail=True, methods=['post']) def issue_book),
    # add them here:
    perms_map = {
        **DjangoModelPermissions.perms_map,    # includes GET, POST, PUT, PATCH, DELETE
        # 'ISSUE_BOOK': ['core.issue_book'],   # example custom
    }