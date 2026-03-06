"""
accounts/services.py
────────────────────
CSV parsing and bulk student-import logic.

This module is intentionally HTTP-free so it can be called from views,
management commands, or tests without a request object.

Public API
──────────
    parse_student_csv(rows, school_class)  →  ParseResult
    import_students(rows, school_class)    →  ImportResult

CSV format
──────────
Required columns (case-insensitive, trimmed):
    first_name, last_name

Optional columns:
    username         – derived from first_name + last_name if absent
    variable_symbol  – auto-generated from SchoolClass.vs_prefix if absent
    parent_email     – creates / links a Parent user
    parent_first_name
    parent_last_name
    password         – plain-text initial password (a random one is set if absent)

Header row is required.  BOM-safe UTF-8 (utf-8-sig) is assumed by the form;
raw bytes are not accepted here — pass already-decoded rows (list of dicts).
"""

from __future__ import annotations

import secrets
import string
from dataclasses import dataclass, field
from typing import List, Optional

from django.db import transaction

from .models import CustomUser, SchoolClass, StudentProfile


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class RowPreview:
    """Represents one CSV row after validation — used for the preview table."""
    row_number:        int
    first_name:        str
    last_name:         str
    username:          str
    parent_email:      str
    parent_first_name: str
    parent_last_name:  str
    variable_symbol:   str          # '' means auto-generate
    password:          str          # '' means auto-generate
    errors:            List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    @property
    def has_parent(self) -> bool:
        return bool(self.parent_email)


@dataclass
class ParseResult:
    """Outcome of parse_student_csv()."""
    rows:          List[RowPreview]
    school_class:  SchoolClass

    @property
    def valid_rows(self):
        return [r for r in self.rows if r.is_valid]

    @property
    def error_rows(self):
        return [r for r in self.rows if not r.is_valid]

    @property
    def has_errors(self) -> bool:
        return bool(self.error_rows)


@dataclass
class ImportedStudent:
    """Details of one successfully imported student."""
    row_number:      int
    student_user:    CustomUser
    parent_user:     Optional[CustomUser]
    profile:         StudentProfile
    student_created: bool          # True = new user, False = pre-existing
    parent_created:  bool
    password:        str           # plain-text, shown once then discarded


@dataclass
class ImportResult:
    """Outcome of import_students()."""
    imported:     List[ImportedStudent] = field(default_factory=list)
    skipped:      List[RowPreview]      = field(default_factory=list)   # already had a profile
    errors:       List[tuple]           = field(default_factory=list)   # (row, message)
    school_class: Optional[SchoolClass] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

_ALPHABET = string.ascii_letters + string.digits

def _random_password(length: int = 12) -> str:
    """Return a cryptographically random password."""
    return ''.join(secrets.choice(_ALPHABET) for _ in range(length))


def _derive_username(first_name: str, last_name: str) -> str:
    """
    Build a lowercase ASCII username from names.
    E.g. "Jan Novák" → "jnovak", with a numeric suffix if taken.
    """
    base = (first_name[:1] + last_name).lower()
    # Strip non-ASCII by encoding/decoding
    safe = base.encode('ascii', errors='ignore').decode()
    safe = ''.join(c for c in safe if c.isalnum())[:30] or 'student'

    candidate = safe
    suffix = 1
    while CustomUser.objects.filter(username=candidate).exists():
        candidate = f"{safe}{suffix}"
        suffix += 1
    return candidate


def _normalise_row(raw: dict) -> dict:
    """Return a new dict with all keys lower-cased and values stripped."""
    return {k.strip().lower(): (v or '').strip() for k, v in raw.items()}


# ── Public functions ──────────────────────────────────────────────────────────

def parse_student_csv(
    rows: list[dict],
    school_class: SchoolClass,
) -> ParseResult:
    """
    Validate a list of raw CSV row-dicts and return a ParseResult.

    Does NOT write anything to the database — safe to call for a dry-run
    preview before the treasurer confirms the import.
    """
    previews: list[RowPreview] = []

    for i, raw in enumerate(rows, start=2):   # row 1 is the header
        r = _normalise_row(raw)
        errors: list[str] = []

        first_name = r.get('first_name', '')
        last_name  = r.get('last_name', '')

        if not first_name:
            errors.append('first_name is required.')
        if not last_name:
            errors.append('last_name is required.')

        # Username: use supplied value or derive from names
        username = r.get('username', '').strip()
        if not username:
            if first_name and last_name:
                username = _derive_username(first_name, last_name)
            else:
                username = ''

        # Variable symbol: blank is fine (auto-generated on save)
        vs = r.get('variable_symbol', '').strip()
        if vs and (not vs.isdigit() or len(vs) > 10):
            errors.append(f'variable_symbol "{vs}" must be 1–10 digits.')

        # Check for VS uniqueness within this batch
        if vs and any(p.variable_symbol == vs for p in previews if p.variable_symbol):
            errors.append(f'variable_symbol "{vs}" is duplicated in this CSV.')

        # Check for VS uniqueness against the DB
        if vs and StudentProfile.objects.filter(variable_symbol=vs).exists():
            errors.append(f'variable_symbol "{vs}" is already used by another student.')

        parent_email = r.get('parent_email', '').strip()
        if parent_email and '@' not in parent_email:
            errors.append(f'parent_email "{parent_email}" does not look like an email address.')

        previews.append(RowPreview(
            row_number=i,
            first_name=first_name,
            last_name=last_name,
            username=username,
            parent_email=parent_email,
            parent_first_name=r.get('parent_first_name', ''),
            parent_last_name=r.get('parent_last_name', ''),
            variable_symbol=vs,
            password=r.get('password', ''),
            errors=errors,
        ))

    return ParseResult(rows=previews, school_class=school_class)


@transaction.atomic
def import_students(
    parse_result: ParseResult,
) -> ImportResult:
    """
    Persist all *valid* rows from *parse_result* to the database.

    - Creates CustomUser (role=STUDENT) for each student.
    - Creates CustomUser (role=PARENT) for each unique parent_email.
    - Creates StudentProfile, auto-generating VS when not supplied.
    - Skips rows where the student already has a StudentProfile.
    - Wraps everything in a single atomic transaction — any unexpected error
      rolls back all changes for that call.

    Returns an ImportResult with per-row details (including plain-text passwords
    that the treasurer can communicate to students/parents — shown once only).
    """
    result = ImportResult(school_class=parse_result.school_class)
    parent_cache: dict[str, CustomUser] = {}    # email → user

    for row in parse_result.valid_rows:
        try:
            # ── Student user ──────────────────────────────────────────────────
            student_user, student_created = CustomUser.objects.get_or_create(
                username=row.username,
                defaults={
                    'first_name': row.first_name,
                    'last_name':  row.last_name,
                    'role':       CustomUser.Role.STUDENT,
                },
            )
            # Update names if we fetched an existing user
            if not student_created:
                student_user.first_name = row.first_name
                student_user.last_name  = row.last_name
                student_user.save(update_fields=['first_name', 'last_name'])

            # Skip students already enrolled (no duplicate profiles)
            if hasattr(student_user, 'student_profile'):
                result.skipped.append(row)
                continue

            # Password
            plain_password = row.password or _random_password()
            student_user.set_password(plain_password)
            student_user.save(update_fields=['password'])

            # ── Parent user ───────────────────────────────────────────────────
            parent_user: Optional[CustomUser] = None
            parent_created = False

            if row.parent_email:
                if row.parent_email in parent_cache:
                    parent_user = parent_cache[row.parent_email]
                else:
                    parent_user, parent_created = CustomUser.objects.get_or_create(
                        email=row.parent_email,
                        defaults={
                            'username':   _derive_username(
                                row.parent_first_name or 'parent',
                                row.parent_last_name  or row.last_name,
                            ),
                            'first_name': row.parent_first_name,
                            'last_name':  row.parent_last_name or row.last_name,
                            'role':       CustomUser.Role.PARENT,
                        },
                    )
                    if parent_created:
                        parent_password = _random_password()
                        parent_user.set_password(parent_password)
                        parent_user.save(update_fields=['password'])
                    parent_cache[row.parent_email] = parent_user

            # ── StudentProfile ────────────────────────────────────────────────
            profile = StudentProfile(
                user=student_user,
                school_class=parse_result.school_class,
                variable_symbol=row.variable_symbol,   # '' → auto-generated by save()
                parent=parent_user,
                is_active=True,
            )
            profile.save()   # triggers VS auto-generation if variable_symbol is ''

            result.imported.append(ImportedStudent(
                row_number=row.row_number,
                student_user=student_user,
                parent_user=parent_user,
                profile=profile,
                student_created=student_created,
                parent_created=parent_created,
                password=plain_password,
            ))

        except Exception as exc:                        # noqa: BLE001
            result.errors.append((row, str(exc)))

    return result
