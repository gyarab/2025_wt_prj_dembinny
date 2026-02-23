"""
app/forms.py
────────────
Compatibility shim — forms have moved to finances/forms.py.
"""

from finances.forms import ExpenseForm, LogTransactionForm, PaymentRequestForm  # noqa: F401

__all__ = ['ExpenseForm', 'LogTransactionForm', 'PaymentRequestForm']
