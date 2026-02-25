"""
importer/parser.py
──────────────────
Pure CSV parsing — no database access, no HTTP.

This module is responsible only for reading and validating the raw CSV text.
It produces a list of ``ParsedRow`` dataclasses that the service layer can
act on.

Supported CSV columns (case-insensitive, leading/trailing whitespace trimmed)
─────────────────────────────────────────────────────────────────────────────
Required:
    first_name
    last_name

Optional:
    username           – auto-derived from first/last name if absent
    variable_symbol    – auto-generated from SchoolClass.vs_prefix if absent
    parent_email       – creates / links a Parent user when supplied
    parent_first_name
    parent_last_name
    password           – random 12-char password set if absent

The module deliberately avoids importing Django models so it can be tested
with plain Python without a running database.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import List


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class ParsedRow:
    """One cleaned, validated row from the CSV."""
    row_number:        int
    first_name:        str
    last_name:         str
    username:          str          # derived or supplied
    parent_email:      str
    parent_first_name: str
    parent_last_name:  str
    variable_symbol:   str          # '' → auto-generate later
    password:          str          # '' → auto-generate later
    errors:            List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    @property
    def has_parent(self) -> bool:
        return bool(self.parent_email)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


@dataclass
class ParseResult:
    """The full result of parsing one CSV file."""
    rows: List[ParsedRow]
    field_errors: List[str] = field(default_factory=list)   # structural problems

    @property
    def valid_rows(self) -> List[ParsedRow]:
        return [r for r in self.rows if r.is_valid]

    @property
    def error_rows(self) -> List[ParsedRow]:
        return [r for r in self.rows if not r.is_valid]

    @property
    def has_errors(self) -> bool:
        return bool(self.error_rows) or bool(self.field_errors)

    @property
    def total(self) -> int:
        return len(self.rows)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _derive_username(first_name: str, last_name: str) -> str:
    """
    Build a lowercase ASCII candidate username from first + last name.
    Uniqueness is NOT checked here — that is the service layer's job.

    "Jan Novák" → "jnovak"
    """
    base = (first_name[:1] + last_name).lower()
    safe = base.encode('ascii', errors='ignore').decode()
    safe = ''.join(c for c in safe if c.isalnum())
    return safe[:30] or 'student'


def _clean(raw: dict, key: str) -> str:
    """Return stripped value for *key*, or '' if missing/None."""
    return (raw.get(key) or '').strip()


# ── Public API ────────────────────────────────────────────────────────────────

REQUIRED_COLUMNS = {'first_name', 'last_name'}


def parse_csv_bytes(data: bytes) -> ParseResult:
    """
    Decode *data* (UTF-8 or UTF-8-BOM) and delegate to ``parse_csv_text``.
    Raises ``ValueError`` if the bytes cannot be decoded.
    """
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ValueError('CSV file must be UTF-8 encoded.') from exc
    return parse_csv_text(text)


def parse_csv_text(text: str) -> ParseResult:
    """
    Parse *text* as CSV and return a ``ParseResult``.

    Structural errors (missing header, missing required columns, empty file)
    are stored in ``ParseResult.field_errors``.
    Per-row validation errors are stored on each ``ParsedRow.errors``.

    Nothing is written to the database.
    """
    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        return ParseResult(rows=[], field_errors=['CSV file has no header row.'])

    # Normalise fieldnames to lower-case stripped strings
    normalised_fields = {f.strip().lower() for f in reader.fieldnames}
    missing = REQUIRED_COLUMNS - normalised_fields
    if missing:
        return ParseResult(
            rows=[],
            field_errors=[f'CSV is missing required columns: {", ".join(sorted(missing))}.'],
        )

    rows: list[ParsedRow] = []
    seen_vs: set[str] = set()          # dedup within the file

    for i, raw in enumerate(reader, start=2):   # row 1 = header
        # Normalise keys
        r = {k.strip().lower(): (v or '').strip() for k, v in raw.items()}
        errors: list[str] = []

        first_name = _clean(r, 'first_name')
        last_name  = _clean(r, 'last_name')

        if not first_name:
            errors.append('first_name is required.')
        if not last_name:
            errors.append('last_name is required.')

        username = _clean(r, 'username') or (
            _derive_username(first_name, last_name) if first_name and last_name else ''
        )

        vs = _clean(r, 'variable_symbol')
        if vs:
            if not vs.isdigit():
                errors.append(f'variable_symbol "{vs}" must contain digits only.')
            elif len(vs) > 10:
                errors.append(f'variable_symbol "{vs}" must be at most 10 digits.')
            elif vs in seen_vs:
                errors.append(f'variable_symbol "{vs}" appears more than once in this file.')
            else:
                seen_vs.add(vs)

        parent_email = _clean(r, 'parent_email')
        if parent_email and '@' not in parent_email:
            errors.append(f'parent_email "{parent_email}" is not a valid email address.')

        rows.append(ParsedRow(
            row_number=i,
            first_name=first_name,
            last_name=last_name,
            username=username,
            parent_email=parent_email,
            parent_first_name=_clean(r, 'parent_first_name'),
            parent_last_name=_clean(r, 'parent_last_name'),
            variable_symbol=vs,
            password=_clean(r, 'password'),
            errors=errors,
        ))

    if not rows:
        return ParseResult(rows=[], field_errors=['The CSV file contains no data rows.'])

    return ParseResult(rows=rows)
