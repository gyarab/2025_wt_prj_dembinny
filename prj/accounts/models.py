"""
accounts/models.py
──────────────────
Identity, authentication, and multi-tenancy models.

CustomUser    – extends AbstractUser with an is_treasurer flag and hide_fund_balance preference.
SchoolClass   – a single class cohort, e.g. "4.B – 2026".
StudentProfile – thin enrollment record: links a student user to a class, VS, and optional parent.
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
    Thin enrollment record that associates a student (CustomUser) with a class.

    Every student has their own CustomUser account (with first_name, last_name, email, etc.).
    This model adds the school-specific data:
    - the SchoolClass they belong to (optional, can be assigned later)
    - a unique Variable Symbol used to match bank transfers automatically
    - an optional parent/guardian link (another CustomUser)
    """

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='student_profile',
        help_text='The student\'s own user account.',
    )
    school_class = models.ForeignKey(
        SchoolClass,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students',
        help_text='The class this student belongs to.',
    )
    variable_symbol = models.CharField(
        max_length=10,
        unique=True,
        verbose_name='Variable Symbol (VS)',
        help_text='Unique up-to-10-digit code used to identify this student\'s bank transfers.',
    )
    parent = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        help_text='Optional parent/guardian linked to this student.',
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Uncheck to exclude this student from new payment requests.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Student Profile'
        verbose_name_plural = 'Student Profiles'
        ordering = ['school_class', 'user__last_name', 'user__first_name']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.school_class})"
