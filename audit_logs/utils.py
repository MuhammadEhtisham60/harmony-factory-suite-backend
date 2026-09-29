"""
Audit Logging Utilities for recording user and system actions.
"""

import logging
from .models import ActivityLog

logger = logging.getLogger(__name__)


def log_activity(request, action, description, module="User Management", status="Success", user=None):
    """
    Records an activity audit log entry safely.
    """
    try:
        target_user = user or getattr(request, 'user', None)

        ip = None
        user_agent = ''

        if request is not None and hasattr(request, 'META'):
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')

        is_authenticated = bool(target_user and getattr(target_user, 'is_authenticated', False))
        username = target_user.username if is_authenticated else (getattr(user, 'username', 'anonymous') if user else 'anonymous')
        full_name = getattr(target_user, 'full_name', None) or username

        return ActivityLog.objects.create(
            user=target_user if is_authenticated else None,
            username=username,
            user_full_name=full_name,
            action=action,
            description=description,
            module=module,
            ip_address=ip if ip else None,
            device=user_agent[:250] if user_agent else '',
            status=status,
        )
    except Exception as e:
        logger.error(f"Failed to record activity log: {e}")
        return None
