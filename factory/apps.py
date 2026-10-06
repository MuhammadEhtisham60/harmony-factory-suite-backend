"""
AppConfig for the factory application.
"""

from django.apps import AppConfig


class FactoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "factory"
    verbose_name = "Factory"

    def ready(self):
        import factory.purchase.supplier.models
        import factory.sales.customer.models
        import factory.loom.models
        import factory.beam.models
        import factory.yarn.yarn_buyer.models
        import factory.yarn.yarn_intake.models
        import factory.yarn.sizing.models
