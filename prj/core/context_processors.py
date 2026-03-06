"""
core/context_processors.py
──────────────────────────
Global template context injected into every request.

Registered in settings.py → TEMPLATES[0]['OPTIONS']['context_processors'].
"""

from django.db.models import Sum


def fund_balance(request):
    """
    Injects fund-level totals into every template context, scoped to the
    current user's SchoolClass:

    - Treasurer → figures for the class they manage.
    - Student   → figures for the class they are enrolled in.
    - Unauthenticated / no class → all zeros.

        fund_collected  – total CZK from confirmed transactions (this class)
        fund_spent      – total CZK across all expenses (this class)
        fund_balance    – fund_collected minus fund_spent
        show_fund_balance – False when the user has opted to hide it
    """
    # Import here to avoid circular imports during app startup
    from finances.models import Expense, Transaction

    school_class = None

    if request.user.is_authenticated:
        if request.user.is_treasurer:
            # Treasurer: scope to the class they manage
            from accounts.models import SchoolClass
            school_class = SchoolClass.objects.filter(teacher=request.user).first()
        else:
            # Student: scope to the class they are enrolled in
            school_class = getattr(
                getattr(request.user, 'student_profile', None), 'school_class', None
            )

    if school_class is not None:
        collected = (
            Transaction.objects
            .filter(
                status=Transaction.Status.CONFIRMED,
                school_class=school_class,
            )
            .aggregate(s=Sum('amount'))['s'] or 0
        )
        spent = (
            Expense.objects
            .filter(school_class=school_class)
            .aggregate(s=Sum('amount'))['s'] or 0
        )
    else:
        collected = 0
        spent     = 0

    show_balance = not (
        request.user.is_authenticated and request.user.hide_fund_balance
    )

    return {
        'fund_collected':    collected,
        'fund_spent':        spent,
        'fund_balance':      collected - spent,
        'show_fund_balance': show_balance,
    }
