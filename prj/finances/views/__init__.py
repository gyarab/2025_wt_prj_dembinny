"""
finances/views/
───────────────
Split into sub-modules for clarity:
  utils.py     – shared helpers (QR generation, decorators, payment data)
  student.py   – student-facing dashboard, payments, budget
  treasurer.py – treasurer-only dashboard, CRUD for requests/expenses
"""
from .student import (
    budget_view,
    dashboard_view,
    payment_info_view,
    pending_payments_view,
)
from .treasurer import (
    confirm_pending_view,
    create_payment_request_view,
    delete_expense_view,
    log_expense_view,
    log_transaction_view,
    manage_bank_account_view,
    student_requests_json,
    treasurer_dashboard_view,
)

__all__ = [
    # student
    'dashboard_view',
    'pending_payments_view',
    'payment_info_view',
    'budget_view',
    # treasurer
    'treasurer_dashboard_view',
    'create_payment_request_view',
    'log_transaction_view',
    'confirm_pending_view',
    'student_requests_json',
    'log_expense_view',
    'delete_expense_view',
    'manage_bank_account_view',
]
