"""
accounts/models.py
──────────────────
Identity, authentication, and multi-tenancy models.

CustomUser  – extends AbstractUser with a role flag (Teacher vs. Parent)
              and a preference flag (hide_fund_balance).
SchoolClass – a single class cohort, e.g. "4.B – 2026".
StudentProfile – the child's record: name, parent FK, unique Variable Symbol.

NOTE: AUTH_USER_MODEL must be set to 'accounts.CustomUser' in settings.py
      once the migration from 'app.User' is complete.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """
    Custom user model for Class Fund Manager.

    Roles
    -----
    TEACHER  – the class treasurer / teacher who manages the fund.
    PARENT   – a parent/guardian who pays on behalf of their child.

    The `is_treasurer` alias is kept for backward compatibility with
    templates and decorators that still reference it.
    """

    class Role(models.TextChoices):
        TEACHER = 'teacher', 'Teacher / Treasurer'
        PARENT  = 'parent',  'Parent / Guardian'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.PARENT,
        verbose_name='Role',
        help_text='Teachers manage the fund; Parents receive payment requests.',
    )
    hide_fund_balance = models.BooleanField(
        default=False,
        verbose_name='Hide fund balance',
        help_text='When checked, the class fund balance card is hidden on this user\'s dashboard.',
    )

    # Avoid reverse-accessor clashes with app.User (both active during migration)
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

    # ── Convenience property so existing code keeps working ──────────────────
    @property
    def is_treasurer(self):
        return self.role == self.Role.TEACHER

    def __str__(self):
        role_label = self.get_role_display()
        return f"{self.get_full_name() or self.username} ({role_label})"

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
        limit_choices_to={'role': CustomUser.Role.TEACHER},
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
        limit_choices_to={'role': CustomUser.Role.PARENT},
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
