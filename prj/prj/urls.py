"""
URL configuration for prj project.

── Current routing ────────────────────────────────────────────────────────────
All live URLs still come from the `app` monolith while the migration to the
four new apps is in progress.

── Future routing (switch when each app is ready) ─────────────────────────────
  path('', include('core.urls')),            # public landing + about
  path('', include('accounts.urls')),        # login / logout / password change
  path('', include('finances.urls')),        # dashboards, payments, expenses
  path('communications/', include('communications.urls')),  # notification log
"""

from django.contrib import admin
from django.urls import include, path

from app import views

urlpatterns = [
    path('admin/', admin.site.urls),

    # ── app monolith (active) ─────────────────────────────────────────────────
    path('', views.render_home, name='homepage'),
    path('about/', views.render_about, name='about'),
    # Student views
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('payments/pending/', views.pending_payments_view, name='pending_payments'),
    path('payments/info/', views.payment_info_view, name='payment_info'),
    path('budget/', views.budget_view, name='budget'),
    # Treasurer views
    path('treasurer/', views.treasurer_dashboard_view, name='treasurer_dashboard'),
    path('treasurer/payment-requests/new/', views.create_payment_request_view, name='create_payment_request'),
    path('treasurer/transactions/log/', views.log_transaction_view, name='log_transaction'),
    path('treasurer/transactions/log/<int:pr_id>/<int:student_id>/', views.log_transaction_view, name='log_transaction_prefill'),
    path('treasurer/api/student-requests/<int:student_id>/', views.student_requests_json, name='student_requests_json'),
    path('treasurer/transactions/confirm/', views.confirm_pending_view, name='confirm_pending'),
    path('treasurer/expenses/log/', views.log_expense_view, name='log_expense'),
    path('treasurer/expenses/log/<int:expense_id>/', views.log_expense_view, name='edit_expense'),
    path('treasurer/expenses/delete/<int:expense_id>/', views.delete_expense_view, name='delete_expense'),
    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('password-change/', views.password_change_view, name='password_change'),
    path('password-change/done/', views.password_change_done_view, name='password_change_done'),

    # ── communications app (new — notification log) ───────────────────────────
    path('communications/', include('communications.urls')),
]
