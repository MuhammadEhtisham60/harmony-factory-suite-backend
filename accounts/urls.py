"""
URLs for accounts module (Authentication, Users, Roles, Permissions).
"""

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    LoginView,
    LogoutView,
    CurrentUserView,
    UserStatsView,
    UserListCreateView,
    UserDetailView,
    UserStatusChangeView,
    UserPasswordResetView,
    RoleListCreateView,
    RoleDetailView,
    PermissionListView,
)

urlpatterns = [
    # Auth Endpoints
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='auth-token-refresh'),
    path('auth/logout/', LogoutView.as_view(), name='auth-logout'),
    path('auth/me/', CurrentUserView.as_view(), name='auth-me'),

    # User Management Endpoints
    path('users/stats/', UserStatsView.as_view(), name='users-stats'),
    path('users/', UserListCreateView.as_view(), name='users-list-create'),
    path('users/<str:pk>/', UserDetailView.as_view(), name='users-detail'),
    path('users/<str:pk>/status/', UserStatusChangeView.as_view(), name='users-status-change'),
    path('users/<str:pk>/reset-password/', UserPasswordResetView.as_view(), name='users-reset-password'),

    # Roles & Permissions Endpoints
    path('roles/', RoleListCreateView.as_view(), name='roles-list-create'),
    path('roles/<int:pk>/', RoleDetailView.as_view(), name='roles-detail'),
    path('permissions/', PermissionListView.as_view(), name='permissions-list'),
]
