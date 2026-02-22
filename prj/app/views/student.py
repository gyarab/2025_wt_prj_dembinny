"""
app/views/student.py
────────────────────
Student-facing views: landing page, personal dashboard,
pending-payments page, payment-info / QR-code page, and budget timeline.
"""

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
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


# ── Budget / Transparency page ────────────────────────────────────────────────

@login_required
def budget_view(req):
    """
    Public (login-required) transparency page showing the full timeline of
    published expenses, grouped by month, with running totals and category
    breakdown — so every student can see how the class money is being spent.
    """
    from itertools import groupby
    from ..models import Transaction

    expenses = list(
        Expense.objects.filter(is_published=True)
        .select_related('recorded_by')
        .order_by('-spent_at', '-created_at')
    )

    # Group expenses by (year, month) for the timeline
    def month_key(e):
        return (e.spent_at.year, e.spent_at.month)

    grouped = []
    for key, group in groupby(expenses, key=month_key):
        items = list(group)
        grouped.append({
            'year':    key[0],
            'month':   key[1],
            'items':   items,
            'subtotal': sum(e.amount for e in items),
        })

    # Category totals for the summary bar
    category_totals = (
        Expense.objects.filter(is_published=True)
        .values('category')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )

    total_spent = Expense.objects.filter(
        is_published=True
    ).aggregate(s=Sum('amount'))['s'] or 0

    # Attach human-readable category labels
    category_labels = dict(Expense.Category.choices)
    for row in category_totals:
        row['label'] = category_labels.get(row['category'], row['category'])
        row['pct']   = round(row['total'] / total_spent * 100) if total_spent else 0

    return render(req, 'budget.html', {
        'grouped':          grouped,
        'category_totals':  category_totals,
        'total_spent':      total_spent,
        'expense_count':    len(expenses),
    })
