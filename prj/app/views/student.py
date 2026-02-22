"""
app/views/student.py
────────────────────
Student-facing views: landing page, personal dashboard,
pending-payments page, and payment-info / QR-code page.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from ..models import BankAccount, Expense
from .utils import attach_qr_to_requests, generate_spd_qr, get_student_payment_data


# ── Public pages ──────────────────────────────────────────────────────────────

def render_home(req):
    """Landing page – authenticated users go straight to their dashboard."""
    if req.user.is_authenticated:
        return redirect('dashboard')
    return render(req, 'home.html')


def render_about(req):
    return render(req, 'about.html')


# ── Student Dashboard ─────────────────────────────────────────────────────────

@login_required
def dashboard_view(req):
    """
    Personal dashboard for any logged-in user.
    Shows summary cards + abbreviated tables.
    """
    context = get_student_payment_data(req.user)
    context['my_transactions'] = context['my_transactions'][:5]
    context['recent_expenses'] = Expense.objects.filter(
        is_published=True
    ).order_by('-spent_at')[:5]
    return render(req, 'dashboard.html', context)


# ── Pending Payments ──────────────────────────────────────────────────────────

@login_required
def pending_payments_view(req):
    """
    Dedicated page listing every payment request the student still owes.
    Each request carries a pre-generated QR code with its exact amount, VS and SS.
    """
    data    = get_student_payment_data(req.user)
    account = BankAccount.objects.filter(is_active=True).order_by('-updated_at').first()

    unpaid_list   = list(data['unpaid_requests'])
    awaiting_list = list(data['awaiting_requests'])

    attach_qr_to_requests(unpaid_list,   account)
    attach_qr_to_requests(awaiting_list, account)

    return render(req, 'pending_payments.html', {
        'unpaid_requests':   unpaid_list,
        'awaiting_requests': awaiting_list,
        'total_owed':        data['total_owed'],
        'today':             data['today'],
        'account':           account,
    })


# ── Payment Info & QR Code ────────────────────────────────────────────────────

@login_required
def payment_info_view(req):
    """
    Shows the class bank account details and a generic scannable QR code
    (no amount pre-filled — students use this to find the account details).
    """
    account = BankAccount.objects.filter(is_active=True).order_by('-updated_at').first()
    qr_base64 = None
    if account and account.account_number:
        account_id = account.iban.strip() if account.iban.strip() else account.account_number.strip()
        qr_base64 = generate_spd_qr(
            account_id=account_id,
            message=f"Class Fund - {account.owner_name}",
        )

    return render(req, 'payment_info.html', {
        'account':   account,
        'qr_base64': qr_base64,
    })
