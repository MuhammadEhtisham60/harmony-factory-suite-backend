"""
Dynamic Permission Classes for Role-Based Access Control (RBAC).
"""

from rest_framework.permissions import BasePermission


class HasERPModulePermission(BasePermission):
    """
    Checks if the authenticated user has the required ERP permission code.
    View can define `required_permission = 'module.action'` or
    `permission_map = {'GET': 'users.view', 'POST': 'users.add', ...}`.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Superusers bypass dynamic permission checks
        if request.user.is_superuser:
            return True

        # Check if user account is active
        if request.user.status != 'Active':
            return False

        # Check action or view-specific permission code
        required_perm = getattr(view, 'required_permission', None)

        if not required_perm:
            perm_map = getattr(view, 'permission_map', {})
            required_perm = perm_map.get(request.method)

        if not required_perm:
            # If no specific permission specified, allow authenticated active user
            return True

        return request.user.has_perm_code(required_perm)


def require_permission(perm_code):
    """
    Factory function to generate a DRF permission class requiring a specific permission code.
    Usage:
        permission_classes = [IsAuthenticated, require_permission('users.view')]
    """
    class CustomPerm(BasePermission):
        def has_permission(self, request, view):
            if not request.user or not request.user.is_authenticated:
                return False
            if request.user.is_superuser:
                return True
            if request.user.status != 'Active':
                return False
            return request.user.has_perm_code(perm_code)

    CustomPerm.__name__ = f"RequirePermission_{perm_code.replace('.', '_')}"
    return CustomPerm
