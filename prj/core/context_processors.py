"""
core/context_processors.py
──────────────────────────
Global template context injected into every request.

Registered in settings.py → TEMPLATES[0]['OPTIONS']['context_processors'].
"""

from django.db.models import Sum


def fund_balance(request):
    """
    Injects fund-level totals into every template context:

        fund_collected  – total CZK from all CONFIRMED transactions
        fund_spent      – total CZK across all published Expense records
        fund_balance    – fund_collected minus fund_spent
        show_fund_balance – False when the user has opted to hide it
    """
    # Import here to avoid circular imports during app startup
    from finances.models import Expense, Transaction

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
