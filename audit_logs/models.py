from django.db import models
from django.conf import settings


class ActivityLog(models.Model):
    class ActionChoices(models.TextChoices):
        LOGIN = 'Login', 'Login'
        LOGOUT = 'Logout', 'Logout'
        PROFILE_UPDATED = 'Profile Updated', 'Profile Updated'
        PASSWORD_CHANGED = 'Password Changed', 'Password Changed'
        ROLE_CHANGED = 'Role Changed', 'Role Changed'
        PERMISSION_UPDATED = 'Permission Updated', 'Permission Updated'
        USER_CREATED = 'User Created', 'User Created'
        USER_ACTIVATED = 'User Activated', 'User Activated'
        USER_DEACTIVATED = 'User Deactivated', 'User Deactivated'
        USER_DELETED = 'User Deleted', 'User Deleted'
        ROLE_CREATED = 'Role Created', 'Role Created'
        ROLE_DELETED = 'Role Deleted', 'Role Deleted'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activities'
    )
    username = models.CharField(max_length=150)
    user_full_name = models.CharField(max_length=255)
    action = models.CharField(max_length=50, choices=ActionChoices.choices)
    description = models.TextField()
    module = models.CharField(max_length=100, default='User Management')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(max_length=20, default='Success')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.username} - {self.action} at {self.created_at}"
