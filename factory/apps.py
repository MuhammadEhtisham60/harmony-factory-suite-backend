"""
AppConfig for the factory application.
"""

from django.apps import AppConfig


class FactoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "factory"
    verbose_name = "Factory"
