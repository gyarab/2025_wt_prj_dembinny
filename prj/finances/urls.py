"""
finances/urls.py
────────────────
URL patterns for the finances app (student + treasurer views).
Include in the root urls.py with:
    path('', include('finances.urls')),
"""

from django.urls import path

from . import views

urlpatterns = [
    # Student views
    path('dashboard/',        views.dashboard_view,        name='dashboard'),
    path('payments/pending/', views.pending_payments_view, name='pending_payments'),
    path('payments/info/',    views.payment_info_view,     name='payment_info'),
    path('budget/',           views.budget_view,           name='budget'),

    # Treasurer views
    path('treasurer/',                                          views.treasurer_dashboard_view,    name='treasurer_dashboard'),
    path('treasurer/payment-requests/new/',                     views.create_payment_request_view, name='create_payment_request'),
    path('treasurer/transactions/log/',                         views.log_transaction_view,        name='log_transaction'),
    path('treasurer/transactions/log/<int:pr_id>/<int:student_id>/', views.log_transaction_view,  name='log_transaction_prefill'),
    path('treasurer/transactions/confirm/',                     views.confirm_pending_view,        name='confirm_pending'),
    path('treasurer/api/student-requests/<int:student_id>/',    views.student_requests_json,       name='student_requests_json'),
    path('treasurer/expenses/log/',                             views.log_expense_view,            name='log_expense'),
    path('treasurer/expenses/log/<int:expense_id>/',            views.log_expense_view,            name='edit_expense'),
    path('treasurer/expenses/delete/<int:expense_id>/',         views.delete_expense_view,         name='delete_expense'),
    path('treasurer/bank-account/',                             views.manage_bank_account_view,    name='manage_bank_account'),
]
