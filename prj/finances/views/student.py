"""
finances/views/student.py
──────────────────────────
Student-facing views: dashboard, pending payments, payment info / QR,
and the budget transparency page.
"""

from itertools import groupby

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from ..models import BankAccount, Expense, Transaction
from .utils import attach_qr_to_requests, generate_spd_qr, get_student_payment_data


@login_required
def dashboard_view(req):
    """
    Personal dashboard for any logged-in user.
    Shows summary cards and the most recent 5 transactions / 5 expenses.
    """
    context = get_student_payment_data(req.user)
    context['my_transactions'] = context['my_transactions'][:5]
    context['recent_expenses'] = (
        Expense.objects.filter(is_published=True).order_by('-spent_at')[:5]
    )
    return render(req, 'finances/dashboard.html', context)


@login_required
def pending_payments_view(req):
    """
    Dedicated page listing every payment request the student still owes,
    with per-request SPAYD QR codes.
    """
    data    = get_student_payment_data(req.user)
    account = BankAccount.objects.filter(is_active=True).order_by('-updated_at').first()

    unpaid_list   = list(data['unpaid_requests'])
    awaiting_list = list(data['awaiting_requests'])

    attach_qr_to_requests(unpaid_list,   account)
    attach_qr_to_requests(awaiting_list, account)

    return render(req, 'finances/pending_payments.html', {
        'unpaid_requests':   unpaid_list,
        'awaiting_requests': awaiting_list,
        'total_owed':        data['total_owed'],
        'today':             data['today'],
        'account':           account,
    })


@login_required
def payment_info_view(req):
    """
    Shows the class bank account details and a generic scannable QR code
    (no amount pre-filled — students use this to find the account details).
    """
    account = BankAccount.objects.filter(is_active=True).order_by('-updated_at').first()
    qr_base64 = None
    if account and account.account_number:
        account_id = account.iban.strip() or account.account_number.strip()
        qr_base64 = generate_spd_qr(
            account_id=account_id,
            message=f'Class Fund - {account.owner_name}',
        )
    return render(req, 'finances/payment_info.html', {
        'account':   account,
        'qr_base64': qr_base64,
    })


@login_required
def budget_view(req):
    """
    Transparency page: full timeline of published expenses grouped by month,
    with running totals and a category breakdown.
    """
    expenses = list(
        Expense.objects.filter(is_published=True)
        .select_related('recorded_by')
        .order_by('-spent_at', '-created_at')
    )

    def month_key(e):
        return (e.spent_at.year, e.spent_at.month)

    grouped = []
    for k, g in groupby(expenses, key=month_key):
        items = list(g)
        grouped.append({
            'year':     k[0],
            'month':    k[1],
            'items':    items,
            'subtotal': sum(e.amount for e in items),
        })

    category_totals = (
        Expense.objects.filter(is_published=True)
        .values('category')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    total_spent = (
        Expense.objects.filter(is_published=True)
        .aggregate(s=Sum('amount'))['s'] or 0
    )
    category_labels = dict(Expense.Category.choices)
    for row in category_totals:
        row['label'] = category_labels.get(row['category'], row['category'])
        row['pct']   = round(row['total'] / total_spent * 100) if total_spent else 0

    return render(req, 'finances/budget.html', {
        'grouped':         grouped,
        'category_totals': category_totals,
        'total_spent':     total_spent,
        'expense_count':   len(expenses),
    })
