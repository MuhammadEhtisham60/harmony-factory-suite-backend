"""
Custom JWT Authentication class that safely handles invalid user IDs (e.g. legacy MongoDB ObjectIds)
without raising unhandled 500 ValueError exceptions.
"""

from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed


class SafeJWTAuthentication(JWTAuthentication):
    """
    Extends SimpleJWT's JWTAuthentication to catch ValueError/TypeError when looking up
    the user by primary key (e.g. when an old MongoDB ObjectId string token is submitted to PostgreSQL).
    Returns 401 AuthenticationFailed instead of causing a 500 Server Error.
    """
    def get_user(self, validated_token):
        try:
            return super().get_user(validated_token)
        except (ValueError, TypeError):
            raise AuthenticationFailed(
                _("User not found or token contains an invalid user identifier. Please log in again."),
                code="user_not_found"
            )
