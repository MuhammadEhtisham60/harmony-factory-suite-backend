"""
URL routing for Bank Accounts and Bank Transactions.
"""

from rest_framework.routers import DefaultRouter
from .views import BankAccountViewSet, BankTransactionViewSet

router = DefaultRouter()
router.register(r"bank-accounts", BankAccountViewSet, basename="bank-accounts")
router.register(r"bank-transactions", BankTransactionViewSet, basename="bank-transactions")

urlpatterns = router.urls
