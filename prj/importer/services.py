"""
importer/services.py
────────────────────
Database write layer for the CSV student import.

Depends on:
    importer.parser   – pure parsing (no DB)
    accounts.models   – CustomUser, SchoolClass, StudentProfile
    importer.models   – ImportBatch, ImportRow  (audit log)

Public API
──────────
    execute_import(parse_result, school_class, uploaded_by, filename)
        → ImportBatch

The function is wrapped in ``@transaction.atomic`` so the entire import
either succeeds or rolls back completely.  The audit log is written inside
the same transaction so it always reflects the actual DB state.
"""

from __future__ import annotations

import secrets
import string
from datetime import datetime, timezone
from typing import Optional

from django.db import transaction

from accounts.models import ClassMembership, CustomUser, FundGroup, SchoolClass, StudentProfile
from .models import ImportBatch, ImportRow
from .parser import ParseResult, ParsedRow


# ── Helpers ───────────────────────────────────────────────────────────────────

_ALPHABET = string.ascii_letters + string.digits


def _random_password(length: int = 12) -> str:
    """Return a cryptographically random alphanumeric password."""
    return ''.join(secrets.choice(_ALPHABET) for _ in range(length))


def _unique_username(candidate: str) -> str:
    """
    Return *candidate* if it is free, otherwise append a numeric suffix
    until a free username is found.
    """
    base = candidate or 'student'
    username = base
    suffix = 1
    while CustomUser.objects.filter(username=username).exists():
        username = f'{base}{suffix}'
        suffix += 1
    return username


# ── Result helpers attached to ImportedStudent ────────────────────────────────

class ImportedStudent:
    """Lightweight result object for one successfully imported student."""
    __slots__ = (
        'row_number', 'student_user', 'parent_user',
        'profile', 'student_created', 'parent_created', 'plain_password',
    )

    def __init__(self, *, row_number, student_user, parent_user,
                 profile, student_created, parent_created, plain_password):
        self.row_number      = row_number
        self.student_user    = student_user
        self.parent_user     = parent_user
        self.profile         = profile
        self.student_created = student_created
        self.parent_created  = parent_created
        self.plain_password  = plain_password   # shown once; empty for existing users


# ── Main entry point ──────────────────────────────────────────────────────────

@transaction.atomic
def execute_import(
    parse_result: ParseResult,
    school_class: SchoolClass,
    uploaded_by: Optional[CustomUser] = None,
    filename: str = '',
    fund_groups_by_name: dict[str, FundGroup] | None = None,
) -> tuple[ImportBatch, list[ImportedStudent]]:
    """
    Persist all *valid* rows from *parse_result* into the database.

    Creates:
    - A ``CustomUser`` for each student that doesn't exist yet.
    - A ``CustomUser`` (role=PARENT) for each unique parent_email.
    - A ``StudentProfile`` for each student (VS auto-generated when not supplied).
    - When the row's *role* matches a key in *fund_groups_by_name*, a
      ``ClassMembership`` is also created linking the user to that FundGroup.
    - An ``ImportBatch`` + ``ImportRow`` audit log for every row.

    Students who already have a ``StudentProfile`` are **skipped** (not duplicated).

    *fund_groups_by_name* — mapping of FundGroup.name → FundGroup for the
    target class, used to resolve custom group role names from the CSV.

    Returns a 2-tuple of (ImportBatch, list[ImportedStudent]).
    """
    batch = ImportBatch.objects.create(
        uploaded_by=uploaded_by,
        school_class=school_class,
        original_filename=filename,
        total_rows=parse_result.total,
        status=ImportBatch.Status.PENDING,
    )

    imported_students: list[ImportedStudent] = []
    parent_cache: dict[str, CustomUser] = {}   # email → user

    n_imported = 0
    n_skipped  = 0
    n_errors   = 0

    for row in parse_result.rows:

        # ── Row-level validation errors → log and skip ────────────────────────
        if not row.is_valid:
            ImportRow.objects.create(
                batch=batch,
                row_number=row.row_number,
                first_name=row.first_name,
                last_name=row.last_name,
                username=row.username,
                variable_symbol=row.variable_symbol,
                parent_email=row.parent_email,
                outcome=ImportRow.Outcome.ERROR,
                message='; '.join(row.errors),
            )
            n_errors += 1
            continue

        try:
            # ── Resolve role ──────────────────────────────────────────────────
            # A row role can be:
            #   a) A FundGroup name (original case)  → user gets TREASURER_BOOKKEEPER + ClassMembership
            #   b) A system role name (lowercased)   → maps to CustomUser.Role enum value
            groups = fund_groups_by_name or {}
            fund_group: FundGroup | None = groups.get(row.role)

            if fund_group is not None:
                # Custom group role — treat user as a treasurer-level member
                user_role = CustomUser.Role.TREASURER_BOOKKEEPER
            else:
                user_role = getattr(CustomUser.Role, row.role.upper(), CustomUser.Role.STUDENT)

            # ── Student user ──────────────────────────────────────────────────
            # Look up by exact username first so we reuse an existing account
            # rather than creating a suffixed duplicate.  Only call
            # _unique_username when creating a genuinely new account.
            if row.username:
                try:
                    student_user = CustomUser.objects.get(username=row.username)
                    student_created = False
                except CustomUser.DoesNotExist:
                    username = _unique_username(row.username)
                    student_user, student_created = CustomUser.objects.get_or_create(
                        username=username,
                        defaults={
                            'first_name': row.first_name,
                            'last_name':  row.last_name,
                            'email':      row.email,
                            'role':       user_role,
                        },
                    )
            else:
                username = _unique_username(row.username)
                student_user, student_created = CustomUser.objects.get_or_create(
                    username=username,
                    defaults={
                        'first_name': row.first_name,
                        'last_name':  row.last_name,
                        'email':      row.email,
                        'role':       user_role,
                    },
                )
            if not student_created:
                # Keep names and email fresh even for existing accounts
                update_fields = ['first_name', 'last_name']
                student_user.first_name = row.first_name
                student_user.last_name  = row.last_name
                if row.email:
                    student_user.email = row.email
                    update_fields.append('email')
                student_user.save(update_fields=update_fields)

            # Skip students that are already enrolled
            if hasattr(student_user, 'student_profile'):
                ImportRow.objects.create(
                    batch=batch,
                    row_number=row.row_number,
                    first_name=row.first_name,
                    last_name=row.last_name,
                    username=student_user.username,
                    variable_symbol=row.variable_symbol,
                    parent_email=row.parent_email,
                    outcome=ImportRow.Outcome.SKIPPED,
                    message='Student already has a profile — skipped.',
                )
                n_skipped += 1
                continue

            # Set / generate password
            plain_password = row.password or _random_password()
            if student_created:
                student_user.set_password(plain_password)
                student_user.save(update_fields=['password'])
            else:
                plain_password = ''   # don't overwrite existing user's password

            # ── Parent user ───────────────────────────────────────────────────
            parent_user: Optional[CustomUser] = None
            parent_created = False

            if row.parent_email:
                if row.parent_email in parent_cache:
                    parent_user = parent_cache[row.parent_email]
                else:
                    parent_username = _unique_username(
                        (row.parent_first_name[:1] + row.parent_last_name).lower()
                        .encode('ascii', errors='ignore').decode()
                        or 'parent'
                    )
                    parent_user, parent_created = CustomUser.objects.get_or_create(
                        email=row.parent_email,
                        defaults={
                            'username':   parent_username,
                            'first_name': row.parent_first_name,
                            'last_name':  row.parent_last_name or row.last_name,
                            'role':       CustomUser.Role.PARENT,
                        },
                    )
                    if parent_created:
                        parent_user.set_password(_random_password())
                        parent_user.save(update_fields=['password'])
                    parent_cache[row.parent_email] = parent_user

            # ── StudentProfile ────────────────────────────────────────────────
            profile = StudentProfile(
                user=student_user,
                school_class=school_class,
                variable_symbol=row.variable_symbol,   # '' → auto-generated by save()
                parent=parent_user,
                is_active=True,
            )
            profile.save()   # triggers VS auto-generation

            # ── ClassMembership for FundGroup roles ───────────────────────────
            if fund_group is not None:
                ClassMembership.objects.get_or_create(
                    user=student_user,
                    school_class=school_class,
                    defaults={'fund_group': fund_group},
                )

            # ── Audit row ─────────────────────────────────────────────────────
            notes = 'new user' if student_created else 'existing user'
            if parent_created:
                notes += '; new parent account'
            ImportRow.objects.create(
                batch=batch,
                row_number=row.row_number,
                first_name=row.first_name,
                last_name=row.last_name,
                username=student_user.username,
                variable_symbol=profile.variable_symbol,
                parent_email=row.parent_email,
                plain_password=plain_password,   # empty for pre-existing accounts
                outcome=ImportRow.Outcome.IMPORTED,
                message=notes,
            )
            n_imported += 1

            imported_students.append(ImportedStudent(
                row_number=row.row_number,
                student_user=student_user,
                parent_user=parent_user,
                profile=profile,
                student_created=student_created,
                parent_created=parent_created,
                plain_password=plain_password,
            ))

        except Exception as exc:    # noqa: BLE001
            ImportRow.objects.create(
                batch=batch,
                row_number=row.row_number,
                first_name=row.first_name,
                last_name=row.last_name,
                username=row.username,
                variable_symbol=row.variable_symbol,
                parent_email=row.parent_email,
                outcome=ImportRow.Outcome.ERROR,
                message=str(exc),
            )
            n_errors += 1

    # Finalise batch
    batch.imported     = n_imported
    batch.skipped      = n_skipped
    batch.errors       = n_errors
    batch.status       = ImportBatch.Status.COMPLETED
    batch.completed_at = datetime.now(tz=timezone.utc)
    batch.save()

    return batch, imported_students
