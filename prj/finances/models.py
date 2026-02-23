"""
finances/models.py
──────────────────
The money engine.  All models here deal exclusively with money, banking,
and reconciliation.

BankAccount    – IBAN / account number linked to a SchoolClass.
PaymentRequest – What is owed, e.g. "Field Trip – 500 CZK".
Transaction    – Money actually received (confirmed bank transfer).
Expense        – Money the teacher spent from the fund.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class BankAccount(models.Model):
    """
    Holds the class bank account details shown to students on the payment-info
    page.  Linked to one SchoolClass; only one row per class should be active.
    """

    # Optional FK to accounts.SchoolClass — use string reference to avoid
    # a hard import cycle at startup.
    school_class = models.OneToOneField(
        'accounts.SchoolClass',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bank_account',
        help_text='The class this bank account belongs to.',
    )
    owner_name = models.CharField(
        max_length=200,
        help_text="Account holder name (e.g. 'Class 4.B Fund').",
    )
    account_number = models.CharField(
        max_length=50,
        help_text="Local account number (e.g. '123456789/0800').",
    )
    iban = models.CharField(
        max_length=34,
        blank=True,
        help_text='IBAN (optional, used in the QR code).',
    )
    bank_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Bank name (e.g. 'Česká spořitelna').",
    )
    note = models.TextField(
        blank=True,
        help_text="Any extra instructions for students.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Only the active account is shown to students.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Bank Account'
        verbose_name_plural = 'Bank Accounts'

    def __str__(self):
        return f"{self.owner_name} — {self.account_number}"


class PaymentRequest(models.Model):
    """
    A request created by the treasurer asking students to pay a specific amount.

    Can target every student in the class (assign_to_all=True) or only a
    hand-picked subset via the ManyToMany `assigned_to` field.
    """

    title = models.CharField(
        max_length=200,
        help_text='Short description of what the payment is for.',
    )
    description = models.TextField(
        blank=True,
        help_text='Optional longer explanation.',
    )
    amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text='Amount each assigned student is expected to pay (CZK).',
    )
    due_date = models.DateField(
        null=True,
        blank=True,
        help_text='Optional deadline for payment.',
    )
    school_class = models.ForeignKey(
        'accounts.SchoolClass',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_requests',
        help_text='The class this payment request belongs to.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='finances_created_payment_requests',
        help_text='Treasurer who created this request.',
    )
    created_at = models.DateTimeField(default=timezone.now)

    # Czech bank payment identifiers
    variable_symbol = models.CharField(
        max_length=10,
        blank=True,
        verbose_name='Variable Symbol (VS)',
        help_text='Up to 10 digits — identifies the payment purpose.',
    )
    specific_symbol = models.CharField(
        max_length=10,
        blank=True,
        verbose_name='Specific Symbol (SS)',
        help_text='Up to 10 digits — optionally identifies the payer.',
    )

    # Who needs to pay?
    assign_to_all = models.BooleanField(
        default=True,
        help_text='If True, every active student is expected to pay.',
    )
    assigned_to = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='finances_payment_requests',
        help_text='Specific students assigned to this request (used when assign_to_all=False).',
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Payment Request'
        verbose_name_plural = 'Payment Requests'

    def __str__(self):
        return f"{self.title} – {self.amount} CZK"

    @property
    def total_collected(self):
        """Sum of all confirmed transactions linked to this request."""
        return (
            self.transactions.filter(status=Transaction.Status.CONFIRMED)
            .aggregate(models.Sum('amount'))['amount__sum'] or 0
        )


class Transaction(models.Model):
    """
    Records a single payment made by a student towards a PaymentRequest.
    """

    class Status(models.TextChoices):
        PENDING   = 'pending',   'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        REJECTED  = 'rejected',  'Rejected'

    payment_request = models.ForeignKey(
        PaymentRequest,
        on_delete=models.CASCADE,
        related_name='transactions',
    )
    school_class = models.ForeignKey(
        'accounts.SchoolClass',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        help_text='The class this transaction belongs to.',
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='finances_transactions',
    )
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    note = models.TextField(blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'

    def __str__(self):
        return (
            f"{self.student} → {self.payment_request.title} "
            f"({self.amount} CZK, {self.get_status_display()})"
        )


class Expense(models.Model):
    """
    Money spent FROM the class fund by the treasurer.
    Published so every student can see how the collected money is being used.
    """

    class Category(models.TextChoices):
        TRIP       = 'trip',       'Trip / Excursion'
        SUPPLIES   = 'supplies',   'Supplies'
        FOOD       = 'food',       'Food & Drinks'
        DECORATION = 'decoration', 'Decoration'
        DONATION   = 'donation',   'Donation'
        OTHER      = 'other',      'Other'

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER,
    )
    school_class = models.ForeignKey(
        'accounts.SchoolClass',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses',
        help_text='The class this expense belongs to.',
    )
    spent_at = models.DateField(default=timezone.now)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='finances_recorded_expenses',
    )
    is_published = models.BooleanField(
        default=True,
        help_text='If True, all logged-in students can see this expense.',
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-spent_at']
        verbose_name = 'Expense'
        verbose_name_plural = 'Expenses'

    def __str__(self):
        return f"{self.title} – {self.amount} CZK ({self.spent_at})"
