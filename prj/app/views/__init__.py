"""
app/views/__init__.py
─────────────────────
Re-exports every view function so that `from app import views` and
`views.<name>` still works in urls.py without any changes.
"""

# Auth views
from .auth import (
    login_view,
    logout_view,
    password_change_done_view,
    password_change_view,
)

# Student-facing views
from .student import (
    dashboard_view,
    payment_info_view,
    pending_payments_view,
    render_about,
    render_home,
)

# Treasurer views
from .treasurer import (
    confirm_pending_view,
    create_payment_request_view,
    log_transaction_view,
    student_requests_json,
    treasurer_dashboard_view,
)

__all__ = [
    # auth
    "login_view",
    "logout_view",
    "password_change_view",
    "password_change_done_view",
    # student
    "render_home",
    "render_about",
    "dashboard_view",
    "pending_payments_view",
    "payment_info_view",
    # treasurer
    "treasurer_dashboard_view",
    "create_payment_request_view",
    "log_transaction_view",
    "confirm_pending_view",
    "student_requests_json",
]
