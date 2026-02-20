from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """
    Custom user model for Class Fund Manager.

    Extends Django's built-in AbstractUser so we keep all the
    standard auth functionality (username, password, email, etc.)
    and simply add the `is_treasurer` flag to distinguish the class
    treasurer (admin) from regular student accounts.
    """

    is_treasurer = models.BooleanField(
        default=False,
        verbose_name="Treasurer",
        help_text="Designates whether this user is the class treasurer "
                  "with administrative privileges over the fund.",
    )

    def __str__(self):
        role = "Treasurer" if self.is_treasurer else "Student"
        return f"{self.get_full_name() or self.username} ({role})"


# ── Finance models ─────────────────────────────────────────────────────────────

class PaymentRequest(models.Model):
    """
    A request created by the treasurer asking students to pay a specific amount.

    Can be directed at every student in the class (assign_to_all=True) or only
    to a hand-picked subset via the ManyToMany `assigned_to` field.
    """

    title = models.CharField(
        max_length=200,
        help_text="Short description of what the payment is for.",
    )
    description = models.TextField(
        blank=True,
        help_text="Optional longer explanation (event details, itemised costs, etc.).",
    )
    amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Amount each assigned student is expected to pay (CZK).",
    )
    due_date = models.DateField(
        null=True,
        blank=True,
        help_text="Optional deadline for payment.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_payment_requests",
        help_text="Treasurer who created this request.",
    )
    created_at = models.DateTimeField(default=timezone.now)

    # Who needs to pay?
    assign_to_all = models.BooleanField(
        default=True,
        help_text="If True, every active student is expected to pay. "
                  "If False, only the students listed in 'assigned_to'.",
    )
    assigned_to = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="payment_requests",
        help_text="Specific students assigned to this request (used when assign_to_all=False).",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Payment Request"
        verbose_name_plural = "Payment Requests"

    def __str__(self):
        return f"{self.title} – {self.amount} CZK"

    @property
    def total_collected(self):
        """Sum of all confirmed transactions linked to this request."""
        return self.transactions.filter(
            status=Transaction.Status.CONFIRMED
        ).aggregate(models.Sum("amount"))["amount__sum"] or 0


class Transaction(models.Model):
    """
    Records a single payment made by a student towards a PaymentRequest.

    The treasurer reviews incoming bank transfers and marks them CONFIRMED once
    the money is verified in the class account.
    """

    class Status(models.TextChoices):
        PENDING   = "pending",   "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED  = "rejected",  "Rejected"

    payment_request = models.ForeignKey(
        PaymentRequest,
        on_delete=models.CASCADE,
        related_name="transactions",
        help_text="The payment request this transaction is paying towards.",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="transactions",
        help_text="Student who made this payment.",
    )
    amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Amount actually transferred (CZK).",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    note = models.TextField(
        blank=True,
        help_text="Optional note from the student or treasurer (e.g. bank reference).",
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the student claims to have sent the money.",
    )
    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the treasurer confirmed receipt.",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"

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
        TRIP        = "trip",        "Trip / Excursion"
        SUPPLIES    = "supplies",    "Supplies"
        FOOD        = "food",        "Food & Drinks"
        DECORATION  = "decoration",  "Decoration"
        DONATION    = "donation",    "Donation"
        OTHER       = "other",       "Other"

    title = models.CharField(
        max_length=200,
        help_text="What the money was spent on.",
    )
    description = models.TextField(
        blank=True,
        help_text="Optional details, receipts info, etc.",
    )
    amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Amount spent (CZK).",
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER,
    )
    spent_at = models.DateField(
        default=timezone.now,
        help_text="Date the expense occurred.",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="recorded_expenses",
        help_text="Treasurer who logged this expense.",
    )
    is_published = models.BooleanField(
        default=True,
        help_text="If True, all logged-in students can see this expense.",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-spent_at"]
        verbose_name = "Expense"
        verbose_name_plural = "Expenses"

    def __str__(self):
        return f"{self.title} – {self.amount} CZK ({self.spent_at})"
