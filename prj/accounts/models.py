"""
accounts/models.py
──────────────────
Identity, authentication, and multi-tenancy models.

CustomUser    – extends AbstractUser with a role field and hide_fund_balance preference.
SchoolClass   – a single class cohort, e.g. "4.B – 2026".
StudentProfile – thin enrollment record: links a student user to a class, VS, and optional parent.

Roles
─────
SYSTEM_ADMIN  – full platform administrator (maps to Django's is_staff superuser).
TREASURER     – class teacher / treasurer; manages the fund for one or more classes.
STUDENT       – a regular student account; has a StudentProfile.
PARENT        – parent / guardian account; linked via StudentProfile.parent.

Variable Symbol (VS) generation
────────────────────────────────
Every student must have a unique numeric VS used to match incoming bank transfers.

Format: <class_prefix><zero-padded sequence>
  class_prefix  – 2-digit number stored on SchoolClass (e.g. 01 for "1.A 2026")
  sequence      – 3-digit auto-increment per class (001, 002, …, 999)

Example: class prefix 04, third student → VS "04003"

If SchoolClass.vs_prefix is blank (legacy / un-assigned), a fallback of 6 random
digits is used so uniqueness is always guaranteed.
"""

import random
import string

from django.core.validators import RegexValidator
from django.contrib.auth.models import AbstractUser
from django.db import models


# ── VS helpers ────────────────────────────────────────────────────────────────

VS_VALIDATOR = RegexValidator(
    regex=r'^\d{1,10}$',
    message='Variable Symbol must be 1–10 digits.',
)


def _next_vs_for_class(school_class: 'SchoolClass') -> str:
    """
    Return the next available VS for *school_class*.

    Format: <2-digit prefix><3-digit sequence>  → e.g. "04003"
    Falls back to 6 random digits when no prefix is set.
    """
    prefix = (school_class.vs_prefix or '').strip()

    if prefix:
        # Find the highest existing sequence number in this class
        existing = (
            StudentProfile.objects
            .filter(school_class=school_class)
            .exclude(variable_symbol='')
            .values_list('variable_symbol', flat=True)
        )
        max_seq = 0
        for vs in existing:
            # Strip the prefix and parse the remainder as an integer
            if vs.startswith(prefix):
                try:
                    max_seq = max(max_seq, int(vs[len(prefix):]))
                except ValueError:
                    pass
        seq = max_seq + 1
        candidate = f"{prefix}{seq:03d}"
    else:
        # No prefix configured – generate a random 6-digit VS
        candidate = ''.join(random.choices(string.digits, k=6))

    # Safety: keep incrementing / re-rolling until we get a globally unique value
    while StudentProfile.objects.filter(variable_symbol=candidate).exists():
        if prefix:
            seq += 1
            candidate = f"{prefix}{seq:03d}"
        else:
            candidate = ''.join(random.choices(string.digits, k=6))

    return candidate


class CustomUser(AbstractUser):
    """
    Custom user model for Class Fund Manager.

    Four roles distinguish what a user can see and do:
        SYSTEM_ADMIN  – platform admin, full access.
        TREASURER     – class treasurer / teacher, manages a class fund.
        STUDENT       – enrolled student, read-only view of own data.
        PARENT        – parent / guardian, read-only view of their child's data.
    """

    class Role(models.TextChoices):
        SYSTEM_ADMIN = 'system_admin', 'System Admin'
        TREASURER    = 'treasurer',    'Class Treasurer / Teacher'
        STUDENT      = 'student',      'Student'
        PARENT       = 'parent',       'Parent'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
        verbose_name='Role',
        help_text='Determines what this user can see and do in the application.',
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

    # ── Convenience properties ────────────────────────────────────────────────

    @property
    def is_system_admin(self) -> bool:
        """True for System Admin role users."""
        return self.role == self.Role.SYSTEM_ADMIN

    @property
    def is_treasurer(self) -> bool:
        """True for Class Treasurer / Teacher role users."""
        return self.role == self.Role.TREASURER

    @property
    def is_student(self) -> bool:
        """True for Student role users."""
        return self.role == self.Role.STUDENT

    @property
    def is_parent(self) -> bool:
        """True for Parent role users."""
        return self.role == self.Role.PARENT

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'


class SchoolClass(models.Model):
    """
    Represents one class cohort, e.g. "4.B – 2026".

    A teacher can manage multiple classes; each class has exactly one
    linked BankAccount (defined in the finances app).

    vs_prefix – 2-digit string used as the leading part of auto-generated
                Variable Symbols for students in this class (e.g. "04").
                Leave blank to use random 6-digit fallback VS values.
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
        limit_choices_to={'role': CustomUser.Role.TREASURER},
        related_name='managed_classes',
        help_text='The teacher/treasurer responsible for this class.',
    )
    school_year = models.CharField(
        max_length=20,
        blank=True,
        help_text='Optional school year label, e.g. "2025/2026".',
    )
    vs_prefix = models.CharField(
        max_length=2,
        blank=True,
        verbose_name='VS Prefix',
        help_text=(
            '2-digit numeric prefix for auto-generated Variable Symbols in this class '
            '(e.g. "04" → students get VS 04001, 04002 …). '
            'Leave blank to use random 6-digit fallback values.'
        ),
        validators=[
            RegexValidator(r'^\d{0,2}$', 'VS Prefix must be 0–2 digits.')
        ],
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
    - a unique Variable Symbol (VS) used to match bank transfers automatically
    - an optional parent/guardian link (another CustomUser)

    VS auto-generation
    ──────────────────
    When a StudentProfile is created (or saved with an empty variable_symbol),
    ``save()`` calls ``_next_vs_for_class()`` to generate a unique numeric VS.
    A VS can also be set manually; it will be validated as 1–10 digits.
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
        blank=True,          # blank allowed so save() can auto-fill it
        verbose_name='Variable Symbol (VS)',
        help_text=(
            'Unique 1–10-digit code used to match this student\'s bank transfers. '
            'Leave blank to auto-generate from the class VS prefix.'
        ),
        validators=[VS_VALIDATOR],
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

    # ── Auto VS generation ────────────────────────────────────────────────────

    def save(self, *args, **kwargs):
        """Auto-generate a Variable Symbol if one is not already set."""
        if not self.variable_symbol:
            if self.school_class_id:
                # school_class may not be loaded yet — fetch it
                sc = self.school_class if self.school_class else SchoolClass.objects.get(pk=self.school_class_id)
                self.variable_symbol = _next_vs_for_class(sc)
            else:
                # No class yet: generate a random 6-digit placeholder
                candidate = ''.join(random.choices(string.digits, k=6))
                while StudentProfile.objects.filter(variable_symbol=candidate).exists():
                    candidate = ''.join(random.choices(string.digits, k=6))
                self.variable_symbol = candidate
        super().save(*args, **kwargs)

    def regenerate_vs(self) -> str:
        """
        Force-regenerate the Variable Symbol (even if one already exists).
        Saves the instance and returns the new VS.
        Call this after assigning a student to a class.
        """
        self.variable_symbol = ''
        self.save()
        return self.variable_symbol

    class Meta:
        verbose_name = 'Student Profile'
        verbose_name_plural = 'Student Profiles'
        ordering = ['school_class', 'user__last_name', 'user__first_name']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.school_class}) VS:{self.variable_symbol}"
