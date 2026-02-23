"""
app/models.py
─────────────
Compatibility shim — all models have moved to dedicated apps.

Keeping these imports means any code that still does
    from app.models import User, BankAccount, ...
continues to work unchanged during the transition period.

TODO: Remove this file once all direct imports have been updated
      to reference the new app locations.
"""

# Identity & auth → accounts
from accounts.models import CustomUser as User, SchoolClass, StudentProfile  # noqa: F401

# Finance models → finances
from finances.models import (  # noqa: F401
    BankAccount,
    Expense,
    PaymentRequest,
    Transaction,
)

__all__ = [
    'User',
    'SchoolClass',
    'StudentProfile',
    'BankAccount',
    'Expense',
    'PaymentRequest',
    'Transaction',
]
