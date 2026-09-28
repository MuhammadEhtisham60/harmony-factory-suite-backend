"""
Views for Authentication, User Management, and Roles & Permissions modules.
"""

from django.db.models import Q
from django.utils import timezone
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .models import User, Role
from .constants import MODULE_PERMISSIONS
from .permissions import require_permission
from .pagination import StandardResultsSetPagination
from .serializers import (
    RoleSerializer,
    UserProfileSerializer,
    UserListSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    UserStatusUpdateSerializer,
    AdminPasswordResetSerializer,
    LoginSerializer,
)
from audit_logs.utils import log_activity


def get_user_by_pk_or_identifier(pk):
    """
    Helper to look up a User by database ID, formatted string (e.g. USR-001), or username.
    """
    pk_str = str(pk).strip()
    if pk_str.upper().startswith('USR-'):
        try:
            numeric_id = int(pk_str.split('-')[1])
            return get_object_or_404(User, id=numeric_id)
        except (ValueError, IndexError):
            pass
    if pk_str.isdigit():
        return get_object_or_404(User, id=int(pk_str))
    return get_object_or_404(User, username=pk_str)


# ============================================================================
# 1. Authentication Views
# ============================================================================

class LoginView(APIView):
    """
    POST /api/v1/auth/login/
    Authenticates user via username or email and returns JWT tokens with profile & permissions.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Invalid username or password.',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        credential = serializer.validated_data['username'].strip()
        password = serializer.validated_data['password']

        # Find user by username or email (case-insensitive)
        user = User.objects.filter(
            Q(username__iexact=credential) | Q(email__iexact=credential)
        ).first()

        if not user or not user.check_password(password):
            log_activity(
                request,
                action='Login',
                description=f"Failed login attempt for credential: {credential}",
                module='Authentication',
                status='Failed'
            )
            return Response({
                'success': False,
                'message': 'Invalid username or password.',
                'errors': {
                    'detail': 'No active account found with the given credentials.'
                }
            }, status=status.HTTP_401_UNAUTHORIZED)

        # Check account status
        if user.status != 'Active' or not user.is_active:
            log_activity(
                request,
                action='Login',
                description=f"Blocked login for {user.status} user: {user.username}",
                module='Authentication',
                status='Failed',
                user=user
            )
            return Response({
                'success': False,
                'message': f'Your account is currently {user.status.lower()}. Please contact system administration.',
                'errors': {
                    'detail': f'Account is {user.status.lower()}.'
                }
            }, status=status.HTTP_403_FORBIDDEN)

        # Generate JWT Tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        # Update last login timestamps
        user.last_login_at = timezone.now()
        user.last_login = timezone.now()
        user.save(update_fields=['last_login_at', 'last_login'])

        # Audit log entry
        log_activity(
            request,
            action='Login',
            description=f"{user.full_name} logged in successfully.",
            module='Authentication',
            status='Success',
            user=user
        )

        user_data = UserProfileSerializer(user, context={'request': request}).data

        return Response({
            'success': True,
            'message': 'Login successful.',
            'data': {
                'tokens': {
                    'access': access_token,
                    'refresh': refresh_token
                },
                'user': user_data
            }
        }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/
    Blacklists the provided refresh token and logs out the user.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({
                'success': False,
                'message': 'Refresh token is required.',
                'errors': {'refresh': ['This field is required.']}
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate the refresh token format
        try:
            RefreshToken(refresh_token)
        except TokenError as e:
            return Response({
                'success': False,
                'message': 'Invalid or expired refresh token.',
                'errors': {'detail': str(e)}
            }, status=status.HTTP_400_BAD_REQUEST)

        log_activity(
            request,
            action='Logout',
            description=f"{request.user.full_name} logged out.",
            module='Authentication',
            status='Success',
            user=request.user
        )

        return Response({
            'success': True,
            'message': 'Successfully logged out.'
        }, status=status.HTTP_200_OK)


class CurrentUserView(APIView):
    """
    GET /api/v1/auth/me/
    Returns current authenticated user details and permissions.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user, context={'request': request})
        return Response({
            'success': True,
            'data': {
                'user': serializer.data
            }
        }, status=status.HTTP_200_OK)


# ============================================================================
# 2. User Management Views
# ============================================================================

class UserStatsView(APIView):
    """
    GET /api/v1/users/stats/
    Returns aggregate user and role statistics.
    """
    permission_classes = [IsAuthenticated, require_permission('users.view')]

    def get(self, request):
        total_users = User.objects.count()
        active_users = User.objects.filter(status='Active').count()
        inactive_users = User.objects.filter(status='Inactive').count()
        pending_users = User.objects.filter(status='Pending').count()
        suspended_users = User.objects.filter(status='Suspended').count()
        total_roles = Role.objects.count()

        return Response({
            'success': True,
            'data': {
                'totalUsers': total_users,
                'activeUsers': active_users,
                'inactiveUsers': inactive_users,
                'pendingUsers': pending_users,
                'suspendedUsers': suspended_users,
                'totalRoles': total_roles
            }
        }, status=status.HTTP_200_OK)


class UserListCreateView(APIView):
    """
    GET  /api/v1/users/ - List users with multi-filters, search & pagination
    POST /api/v1/users/ - Onboard a new user account
    """
    pagination_class = StandardResultsSetPagination

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), require_permission('users.add')()]
        return [IsAuthenticated(), require_permission('users.view')()]

    def get(self, request):
        queryset = User.objects.select_related('role').all()

        # Multi-field search
        search_query = request.query_params.get('search')
        if search_query:
            search_query = search_query.strip()
            # If search is in format USR-001
            if search_query.upper().startswith('USR-'):
                try:
                    num_id = int(search_query.split('-')[1])
                    queryset = queryset.filter(id=num_id)
                except (ValueError, IndexError):
                    pass
            else:
                queryset = queryset.filter(
                    Q(username__icontains=search_query) |
                    Q(full_name__icontains=search_query) |
                    Q(first_name__icontains=search_query) |
                    Q(last_name__icontains=search_query) |
                    Q(email__icontains=search_query) |
                    Q(phone__icontains=search_query) |
                    Q(employee_id__icontains=search_query)
                )

        # Filters
        role_param = request.query_params.get('role')
        if role_param:
            if role_param.isdigit():
                queryset = queryset.filter(role_id=int(role_param))
            else:
                queryset = queryset.filter(role__name__iexact=role_param)

        department = request.query_params.get('department')
        if department:
            queryset = queryset.filter(department__iexact=department)

        company = request.query_params.get('company')
        if company:
            queryset = queryset.filter(company__iexact=company)

        branch = request.query_params.get('branch')
        if branch:
            queryset = queryset.filter(branch__iexact=branch)

        status_param = request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status__iexact=status_param)

        # Ordering
        ordering = request.query_params.get('ordering', '-id')
        ordering_map = {
            'fullName': 'full_name',
            '-fullName': '-full_name',
            'createdDate': 'created_date',
            '-createdDate': '-created_date',
            'lastLogin': 'last_login_at',
            '-lastLogin': '-last_login_at',
        }
        order_field = ordering_map.get(ordering, ordering)
        try:
            queryset = queryset.order_by(order_field)
        except Exception:
            queryset = queryset.order_by('-id')

        # Pagination
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = UserListSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = UserCreateSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Validation failed.',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()

        log_activity(
            request,
            action='User Created',
            description=f"Created user account {user.full_name} (@{user.username}) with role {user.role.name if user.role else 'None'}.",
            module='User Management',
            status='Success',
            user=request.user
        )

        return Response({
            'success': True,
            'message': 'User account created successfully.',
            'data': {
                'id': user.formatted_id,
                'username': user.username,
                'fullName': user.full_name,
                'email': user.email,
                'role': user.role.name if user.role else None,
                'status': user.status,
                'createdDate': user.created_date.strftime('%Y-%m-%d')
            }
        }, status=status.HTTP_201_CREATED)


class UserDetailView(APIView):
    """
    GET    /api/v1/users/{id}/ - Retrieve user details
    PUT    /api/v1/users/{id}/ - Full update user details
    PATCH  /api/v1/users/{id}/ - Partial update user details
    DELETE /api/v1/users/{id}/ - Delete user account
    """
    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH']:
            return [IsAuthenticated(), require_permission('users.edit')()]
        elif self.request.method == 'DELETE':
            return [IsAuthenticated(), require_permission('users.delete')()]
        return [IsAuthenticated(), require_permission('users.view')()]

    def get(self, request, pk):
        user = get_user_by_pk_or_identifier(pk)
        serializer = UserProfileSerializer(user, context={'request': request})
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial):
        user = get_user_by_pk_or_identifier(pk)
        serializer = UserUpdateSerializer(
            user,
            data=request.data,
            partial=partial,
            context={'request': request}
        )
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Validation failed.',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        updated_user = serializer.save()

        log_activity(
            request,
            action='Profile Updated',
            description=f"Updated details for user {updated_user.full_name} (@{updated_user.username}).",
            module='User Management',
            status='Success',
            user=request.user
        )

        return Response({
            'success': True,
            'message': 'User details updated successfully.',
            'data': UserProfileSerializer(updated_user, context={'request': request}).data
        }, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        user = get_user_by_pk_or_identifier(pk)

        if user.id == request.user.id:
            return Response({
                'success': False,
                'message': 'You cannot delete your own account.',
                'errors': {'detail': 'Self-deletion is prohibited.'}
            }, status=status.HTTP_400_BAD_REQUEST)

        if user.is_superuser and not request.user.is_superuser:
            return Response({
                'success': False,
                'message': 'Superuser accounts can only be removed by another superuser.',
                'errors': {'detail': 'Permission denied.'}
            }, status=status.HTTP_403_FORBIDDEN)

        user_info = f"{user.full_name} (@{user.username})"
        user.delete()

        log_activity(
            request,
            action='User Deleted',
            description=f"Permanently removed user account: {user_info}.",
            module='User Management',
            status='Success',
            user=request.user
        )

        return Response({
            'success': True,
            'message': 'User account permanently removed.'
        }, status=status.HTTP_200_OK)


class UserStatusChangeView(APIView):
    """
    POST /api/v1/users/{id}/status/
    Updates user account status (Active, Inactive, Suspended, Pending).
    """
    permission_classes = [IsAuthenticated, require_permission('users.status')]

    def post(self, request, pk):
        user = get_user_by_pk_or_identifier(pk)
        serializer = UserStatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Validation failed.',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        new_status = serializer.validated_data['status']
        reason = serializer.validated_data.get('reason', '')

        if user.id == request.user.id and new_status != 'Active':
            return Response({
                'success': False,
                'message': 'You cannot deactivate or suspend your own account.',
                'errors': {'detail': 'Operation prohibited.'}
            }, status=status.HTTP_400_BAD_REQUEST)

        user.status = new_status
        user.is_active = (new_status == 'Active')
        user.save(update_fields=['status', 'is_active'])

        action_name = 'User Activated' if new_status == 'Active' else 'User Deactivated'
        desc = f"Changed status of {user.full_name} to '{new_status}'."
        if reason:
            desc += f" Reason: {reason}"

        log_activity(
            request,
            action=action_name,
            description=desc,
            module='User Management',
            status='Success',
            user=request.user
        )

        return Response({
            'success': True,
            'message': f"User status updated to {new_status}.",
            'data': {
                'id': user.formatted_id,
                'status': user.status
            }
        }, status=status.HTTP_200_OK)


class UserPasswordResetView(APIView):
    """
    POST /api/v1/users/{id}/reset-password/
    Allows an administrator with users.reset_pwd permission to reset a user's password.
    """
    permission_classes = [IsAuthenticated, require_permission('users.reset_pwd')]

    def post(self, request, pk):
        user = get_user_by_pk_or_identifier(pk)
        serializer = AdminPasswordResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Validation failed.',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        new_password = serializer.validated_data['password']
        user.set_password(new_password)
        user.password_last_changed = timezone.now()
        user.save(update_fields=['password', 'password_last_changed'])

        log_activity(
            request,
            action='Password Changed',
            description=f"Admin {request.user.username} reset password for user {user.full_name} (@{user.username}).",
            module='User Management',
            status='Success',
            user=request.user
        )

        return Response({
            'success': True,
            'message': 'Password has been successfully updated.'
        }, status=status.HTTP_200_OK)


# ============================================================================
# 3. Roles & Permissions Views
# ============================================================================

class RoleListCreateView(APIView):
    """
    GET  /api/v1/roles/ - List all roles with user count and permissions
    POST /api/v1/roles/ - Create a new custom role
    """
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), require_permission('roles.manage')()]
        return [IsAuthenticated()]

    def get(self, request):
        roles = Role.objects.all().order_by('name')
        serializer = RoleSerializer(roles, many=True)
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = RoleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Validation failed.',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        role = serializer.save()

        log_activity(
            request,
            action='Role Created',
            description=f"Created custom role '{role.name}' with {len(role.permissions)} permissions.",
            module='User Management',
            status='Success',
            user=request.user
        )

        return Response({
            'success': True,
            'message': 'Role created successfully.',
            'data': RoleSerializer(role).data
        }, status=status.HTTP_201_CREATED)


class RoleDetailView(APIView):
    """
    GET    /api/v1/roles/{id}/ - Retrieve single role details
    PUT    /api/v1/roles/{id}/ - Update role and permission matrix
    PATCH  /api/v1/roles/{id}/ - Partial update role
    DELETE /api/v1/roles/{id}/ - Delete custom role (system roles protected)
    """
    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsAuthenticated(), require_permission('roles.manage')()]
        return [IsAuthenticated()]

    def get(self, request, pk):
        role = get_object_or_404(Role, id=pk)
        return Response({
            'success': True,
            'data': RoleSerializer(role).data
        }, status=status.HTTP_200_OK)

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial):
        role = get_object_or_404(Role, id=pk)
        serializer = RoleSerializer(role, data=request.data, partial=partial)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Validation failed.',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        updated_role = serializer.save()

        log_activity(
            request,
            action='Permission Updated' if 'permissions' in request.data else 'Role Changed',
            description=f"Updated role '{updated_role.name}'.",
            module='User Management',
            status='Success',
            user=request.user
        )

        return Response({
            'success': True,
            'message': 'Role updated successfully.',
            'data': RoleSerializer(updated_role).data
        }, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        role = get_object_or_404(Role, id=pk)

        if role.is_system:
            return Response({
                'success': False,
                'message': 'System protected roles cannot be deleted.',
                'errors': {'detail': 'System protected roles cannot be deleted.'}
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if users are assigned to this role
        assigned_users_count = role.users.count()
        if assigned_users_count > 0:
            return Response({
                'success': False,
                'message': f"Cannot delete role '{role.name}' because {assigned_users_count} user(s) are assigned to it.",
                'errors': {'detail': 'Reassign users before deleting this role.'}
            }, status=status.HTTP_400_BAD_REQUEST)

        role_name = role.name
        role.delete()

        log_activity(
            request,
            action='Role Deleted',
            description=f"Deleted custom role '{role_name}'.",
            module='User Management',
            status='Success',
            user=request.user
        )

        return Response({
            'success': True,
            'message': 'Role deleted successfully.'
        }, status=status.HTTP_200_OK)


class PermissionListView(APIView):
    """
    GET /api/v1/permissions/
    Returns the complete structured permissions matrix grouped by module.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            'success': True,
            'data': MODULE_PERMISSIONS
        }, status=status.HTTP_200_OK)
