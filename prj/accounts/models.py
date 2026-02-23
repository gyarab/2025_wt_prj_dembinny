"""
accounts/models.py
──────────────────
Identity, authentication, and multi-tenancy models.

CustomUser    – extends AbstractUser with an is_treasurer flag and hide_fund_balance preference.
SchoolClass   – a single class cohort, e.g. "4.B – 2026".
StudentProfile – the child's record: name, parent FK, unique Variable Symbol.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """
    Custom user model for Class Fund Manager.

    is_treasurer=True  → the class teacher/treasurer who manages the fund.
    is_treasurer=False → a regular student / parent account.
    """

    is_treasurer = models.BooleanField(
        default=False,
        verbose_name='Treasurer',
        help_text='Designates whether this user is the class treasurer '
                  'with administrative privileges over the fund.',
    )
    hide_fund_balance = models.BooleanField(
        default=False,
        verbose_name='Hide fund balance',
        help_text="When checked, the class fund balance card is hidden on this user's dashboard.",
    )

    # Avoid reverse-accessor clashes with app.User while both are in INSTALLED_APPS
    groups = models.ManyToManyField(
        'auth.Group',
        blank=True,
        related_name='accounts_customuser_set',
        related_query_name='accounts_customuser',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        blank=True,
        related_name='accounts_customuser_set',
        related_query_name='accounts_customuser',
        verbose_name='user permissions',
    )

    def __str__(self):
        role = 'Treasurer' if self.is_treasurer else 'Student'
        return f"{self.get_full_name() or self.username} ({role})"

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'


class SchoolClass(models.Model):
    """
    Represents one class cohort, e.g. "4.B – 2026".

    A teacher can manage multiple classes; each class has exactly one
    linked BankAccount (defined in the finances app).
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text='Human-readable class name, e.g. "4.B – 2026".',
    )
    teacher = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'is_treasurer': True},
        related_name='managed_classes',
        help_text='The teacher/treasurer responsible for this class.',
    )
    school_year = models.CharField(
        max_length=20,
        blank=True,
        help_text='Optional school year label, e.g. "2025/2026".',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'School Class'
        verbose_name_plural = 'School Classes'
        ordering = ['name']

    def __str__(self):
        return self.name


class StudentProfile(models.Model):
    """
    Stores the child's record inside a class.

    Every student has:
    - a display name (the child's name, not the login username)
    - a parent/guardian who is the linked CustomUser account
    - a unique Variable Symbol used to match bank transfers automatically
    - the SchoolClass they belong to
    """

    school_class = models.ForeignKey(
        SchoolClass,
        on_delete=models.CASCADE,
        related_name='students',
        help_text='The class this student belongs to.',
    )
    parent = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        limit_choices_to={'is_treasurer': False},
        related_name='children',
        help_text='The parent/guardian who will receive payment requests and pay.',
    )
    child_name = models.CharField(
        max_length=200,
        help_text='Full name of the child (displayed on treasurer dashboards).',
    )
    variable_symbol = models.CharField(
        max_length=10,
        unique=True,
        verbose_name='Variable Symbol (VS)',
        help_text='Unique up-to-10-digit code used to identify this student\'s bank transfers.',
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Uncheck to exclude this student from new payment requests.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Student Profile'
        verbose_name_plural = 'Student Profiles'
        ordering = ['school_class', 'child_name']

    def __str__(self):
        return f"{self.child_name} ({self.school_class})"
