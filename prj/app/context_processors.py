"""
app/context_processors.py
─────────────────────────
Global context processors injected into every template automatically.

Registered in settings.py → TEMPLATES[0]['OPTIONS']['context_processors'].
"""

from django.db.models import Sum

from .models import Expense, Transaction


def fund_balance(request):
    """
    Injects three fund-level numbers into every template context:

        fund_collected  – total CZK from all CONFIRMED transactions
        fund_spent      – total CZK across all Expense records
        fund_balance    – fund_collected minus fund_spent
                          (negative means the fund is in deficit)

    These are intentionally cheap aggregation queries (two SUM calls)
    and are available on both the student dashboard and the treasurer dashboard.
    The treasurer dashboard view already passes its own copies, but the
    context processor values serve as a reliable fallback and power the
    student-facing balance banner.
    """
    collected = (
        Transaction.objects
        .filter(status=Transaction.Status.CONFIRMED)
        .aggregate(s=Sum('amount'))['s'] or 0
    )
    spent = Expense.objects.aggregate(s=Sum('amount'))['s'] or 0

    show_balance = not (
        request.user.is_authenticated and request.user.hide_fund_balance
    )

    return {
        'fund_collected':    collected,
        'fund_spent':        spent,
        'fund_balance':      collected - spent,
        'show_fund_balance': show_balance,
    }
