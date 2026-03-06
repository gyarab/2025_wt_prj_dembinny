# AI Navigation Manual — Class Fund Manager

> **HOW TO USE THIS FILE**
> Paste the full contents of this file at the top of every new AI coding session before
> describing your task.  It gives the AI the exact architectural boundaries, naming
> conventions, and security rules it needs to produce correct, safe code without
> reading every source file.

---

## 1. Project Overview

**Class Fund Manager** is a multi-tenant Django web application.  Its purpose is to let
school class treasurers (teachers or elected student officers) collect money from parents,
track expenses, and give students and parents a transparent view of where the class fund
stands.

| Item | Value |
|---|---|
| Python | 3.13.5 |
| Django | 6.x (latest stable) |
| Database | SQLite (local) / PostgreSQL via Supabase (production) |
| Hosting | Render.com (web service + cron job) |
| Auth user model | `accounts.CustomUser` |
| Static files | WhiteNoise (CompressedManifest) |
| Timezone | `Europe/Prague` |
| Repo root | `2025_wt_prj_dembinny/` |
| Django project root | `2025_wt_prj_dembinny/prj/` |

---

## 2. The 6-App Architecture

```
prj/                        ← Django project package (settings, root urls, wsgi/asgi)
accounts/                   ← Identity, authentication, multi-tenancy
core/                       ← Public pages, base templates, context processors
finances/                   ← Money engine: payments, transactions, expenses
communications/             ← Outbound email log (NotificationLog)
importer/                   ← CSV bulk student import
```

### 2.1 `accounts` — Identity & Multi-tenancy

**Models** (`accounts/models.py`):

| Model | Purpose |
|---|---|
| `CustomUser` | Extends `AbstractUser`.  Adds `role` (6 choices) and `hide_fund_balance` flag. |
| `SchoolClass` | One class cohort, e.g. "4.B – 2026".  Has `vs_prefix` (2-digit) for VS generation. |
| `FundGroup` | Named permission group per class created by the System Admin.  4 boolean flags. |
| `ClassMembership` | Links a treasurer-role user to a `SchoolClass` via a `FundGroup`. |
| `StudentProfile` | Links a student `CustomUser` to a class.  Holds the unique `variable_symbol` and optional parent FK. |

**Decorator shortcuts** (`accounts/decorators.py`):

| Decorator | Allowed roles |
|---|---|
| `@admin_required` | `SYSTEM_ADMIN` only |
| `@treasurer_required` | all treasurer tiers + SYSTEM_ADMIN |
| `@expenses_required` | same as `treasurer_required` |
| `@payment_requests_required` | FULL + ACCOUNTANT + SYSTEM_ADMIN (NOT bookkeeper) |
| `@import_required` | `SYSTEM_ADMIN` only |
| `@student_required` | `STUDENT` only |
| `@parent_required` | `PARENT` only |

**Views** (`accounts/views.py`): login, logout, password change.
**Admin Panel views** (`accounts/views_admin.py`): `admin_panel_view`, CRUD for `FundGroup`, CRUD for `ClassMembership`.

### 2.2 `core` — Public Pages & Utilities

- `core/views.py`: `home_view` (landing page), `about_view`, `handler404`, `handler500`.
- `core/context_processors.py`: `fund_balance` — injects `fund_collected`, `fund_spent`,
  `fund_balance`, `show_fund_balance` into **every** template.  Scoped to the current user's
  `SchoolClass`; returns zeros for unauthenticated users.
- `core/static/`: All project-wide CSS, JS, images.
- `core/templates/core/base.html`: The master layout template.

### 2.3 `finances` — Money Engine

**Models** (`finances/models.py`):

| Model | Purpose |
|---|---|
| `BankAccount` | IBAN / account number linked via `OneToOneField` to `SchoolClass`. |
| `PaymentRequest` | A treasurer-created payment obligation.  Has `amount`, `due_date`, `assign_to_all` flag, and a `ManyToManyField` to specific students. |
| `Transaction` | One payment event (Pending / Confirmed / Rejected).  FK to `PaymentRequest` and to `student` (CustomUser). |
| `Expense` | Money spent from the fund.  Has `category` (6 choices), `is_published` flag. |

**Views** split into three modules inside `finances/views/`:

| File | Contents |
|---|---|
| `utils.py` | Shared helpers: `get_treasurer_class()`, `get_treasurer_membership()`, `get_class_students()`, `get_class_payment_requests()`, `get_class_bank_account()`, `get_student_payment_data()`, `generate_spd_qr()`, `attach_qr_to_requests()`, `unconfirmed_requests_for_student()`, `_AdminMembership` sentinel. |
| `treasurer.py` | All treasurer-only views: dashboard, create/edit/delete `PaymentRequest`, log/confirm `Transaction`, log/edit/delete `Expense`, AJAX status endpoint. |
| `student.py` | Student-facing views: personal dashboard, pending payments, payment info / QR, budget transparency page. |

### 2.4 `communications` — Outbound Notification Log

**Model**: `NotificationLog` — records every email sent (type, channel, subject, body preview,
success/fail, optional FK to `PaymentRequest`).

**Service** (`communications/services.py`): `send_welcome_email()`, `send_payment_reminder()`,
`send_receipt()`, `generate_spayd_qr_attachment()`.  All functions call `_log()` to persist a
`NotificationLog` entry whether the send succeeded or failed.

### 2.5 `importer` — CSV Bulk Student Import

**Models** (`importer/models.py`): `ImportBatch` (one CSV upload), `ImportRow` (one row outcome).

**Pure parser** (`importer/parser.py`):
- No DB access.  Input: raw `bytes` or `str`.
- Returns `ParseResult` containing a list of `ParsedRow` dataclasses.
- **Identity rules**: each row needs at least one of `username`, `email`, or `first_name + last_name`.
- **Dynamic roles**: `parse_csv_bytes(data, extra_roles=set())` and `parse_csv_text(text, extra_roles=set())` accept a set of additional valid role names (FundGroup names for the target class).  Role comparison is **case-insensitive** internally; original case is preserved in `ParsedRow.role` for service-layer lookup.

**Service** (`importer/services.py`): `execute_import(parse_result, school_class, uploaded_by, filename, fund_groups_by_name)`.
- Wrapped in `@transaction.atomic`.
- When `row.role` matches a key in `fund_groups_by_name`, creates both a `CustomUser` (with role `TREASURER_BOOKKEEPER`) and a `ClassMembership` linking them to the matched `FundGroup`.
- Otherwise maps `row.role` to `CustomUser.Role` enum.

**Views** (`importer/views.py`): 3-step flow — `upload_view` → `preview_view` (editable inline table) → `confirm_view` → result.  History: `batch_list_view`, `batch_detail_view`.

---

## 3. Strict Multi-Tenancy Rules

> **These rules are non-negotiable.  Violating them can expose one class's data to another.**

**Rule 1 — Never query a scoped model without a `school_class` filter.**

```python
# ✗ WRONG
PaymentRequest.objects.all()
Transaction.objects.filter(student=user)
Expense.objects.order_by('-spent_at')

# ✓ CORRECT
PaymentRequest.objects.filter(school_class=school_class)
Transaction.objects.filter(school_class=school_class)
Expense.objects.filter(school_class=school_class)
```

Scoped models (always require `school_class=`): `PaymentRequest`, `Transaction`, `Expense`,
`BankAccount`, `StudentProfile` (via `school_class`), `ClassMembership`, `FundGroup`,
`ImportBatch`.

**Rule 2 — Resolve the active class before every treasurer view.**

Always call `get_treasurer_class(request.user)` from `finances/views/utils.py`.  This function
checks `ClassMembership` first (preferred), then falls back to `SchoolClass.teacher` FK.
Store the result in a local `school_class` variable; never assume it from the session.

**Rule 3 — Resolve per-class permissions via `ClassMembership`, not the global role.**

```python
membership = get_treasurer_membership(request.user, school_class)
if not membership.can_manage_payment_requests:
    # deny
```

`_AdminMembership` sentinel in `utils.py` grants all flags for System Admins.

**Rule 4 — Student data is scoped via `StudentProfile.school_class`.**

```python
# ✓ Correct student scoping
school_class = request.user.student_profile.school_class
```

Always use `get_student_payment_data(user)` from `finances/views/utils.py` for student views.

**Rule 5 — The context processor is NOT a replacement for queryset scoping.**

`fund_balance` in `core/context_processors.py` provides *display* totals only.  Never rely on it
to scope business logic queries.

---

## 4. Logic Location Map

| What you need | Where it lives |
|---|---|
| User creation / roles | `accounts/models.py` → `CustomUser` |
| VS auto-generation | `accounts/models.py` → `_next_vs_for_class()`, `StudentProfile.save()` |
| Role-access decorators | `accounts/decorators.py` |
| Admin panel (FundGroups / Memberships) | `accounts/views_admin.py` + `accounts/forms_admin.py` |
| Class-scoping helpers | `finances/views/utils.py` |
| QR code (SPAYD) generation | `finances/views/utils.py` → `generate_spd_qr()` |
| Student payment summary | `finances/views/utils.py` → `get_student_payment_data()` |
| Treasurer dashboard logic | `finances/views/treasurer.py` |
| Student-facing views | `finances/views/student.py` |
| Fund balance (global template) | `core/context_processors.py` → `fund_balance()` |
| Outbound email sending | `communications/services.py` |
| CSV parsing (no DB) | `importer/parser.py` |
| CSV import execution (DB writes) | `importer/services.py` → `execute_import()` |
| Import audit log | `importer/models.py` → `ImportBatch`, `ImportRow` |
| Settings & env vars | `prj/settings.py` |
| URL routing | `prj/urls.py` (root) + each app's `urls.py` |

---

## 5. URL Routing Summary

| Prefix | App | Key named URLs |
|---|---|---|
| `/` | `core` | `homepage`, `about` |
| `/login/`, `/logout/` | `accounts` | `login`, `logout`, `password_change` |
| `/admin-panel/` | `accounts` | `admin_panel`, `fund_group_create`, `fund_group_edit`, `fund_group_delete`, `membership_create`, `membership_edit`, `membership_delete` |
| `/dashboard/` | `finances` | `dashboard` |
| `/payments/` | `finances` | `pending_payments`, `payment_info`, `budget` |
| `/treasurer/` | `finances` | `treasurer_dashboard`, `create_payment_request`, `log_transaction`, `confirm_transaction`, `log_expense` … |
| `/communications/` | `communications` | `notification_log` |
| `/import/` | `importer` (namespace `importer`) | `importer:upload`, `importer:preview`, `importer:confirm`, `importer:history`, `importer:batch_detail` |

---

## 6. Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Django secret key |
| `DEBUG` | No (default `True`) | Set to `False` in production |
| `ALLOWED_HOSTS` | No (default `*`) | Comma-separated list |
| `DATABASE_URL` | Production | Full PostgreSQL URL (Supabase IPv4 Pooler) |
| `CUSTOM_DATABASE` | Alternative | Set to `postgresql` to use `DB_NAME`/`DB_USER`/`PASSWORD`/`DB_HOST`/`DB_PORT` individually |
| `DEFAULT_FROM_EMAIL` | Production | Sender address for emails |
| `SITE_URL` | Production | Full base URL, e.g. `https://two025-wt-prj-dembinny.onrender.com` |

---

## 7. Critical Code Patterns

### Adding a new treasurer view

```python
# finances/views/treasurer.py
from .utils import treasurer_required, get_treasurer_class, get_treasurer_membership

@treasurer_required
def my_new_view(req):
    school_class = get_treasurer_class(req.user)
    membership   = get_treasurer_membership(req.user, school_class)
    if not membership.can_log_expenses:          # or whichever flag applies
        messages.error(req, 'Access denied.')
        return redirect('treasurer_dashboard')
    # ALL querysets must use school_class:
    items = MyModel.objects.filter(school_class=school_class)
    ...
```

### Adding a new model linked to SchoolClass

```python
class MyModel(models.Model):
    school_class = models.ForeignKey(
        'accounts.SchoolClass',
        on_delete=models.CASCADE,        # or SET_NULL with null=True
        related_name='my_models',
    )
    # ... fields ...
```

Then add it to the **scoped models** list in Rule 1 above, and update this file.

### Adding a new column to the CSV importer

1. Add the field to `ParsedRow` dataclass in `importer/parser.py`.
2. Parse it inside `parse_csv_text()` in the same file.
3. Include it in the session serialisation dict in `importer/views.py` → `upload_view`.
4. Add it to `_hydrate()` in `importer/views.py`.
5. Add the `<input>` to `importer/templates/importer/preview.html`.
6. Handle it in `importer/services.py` → `execute_import()`.
7. Update `importer/tests.py`.

---

## 8. What Does NOT Exist Yet (Future Work)

- Fio Bank API automatic transaction fetcher (`finances/services.py` — not yet implemented)
- Multi-class support per treasurer (currently a treasurer is resolved to their *first* class)
- Parent portal with full payment history
- SMS notifications (channel exists in `NotificationLog` but no backend)
- Overpayment credit tracking (currently marked as "pending" manual review)

---

## 9. AI Update Rule

> **MANDATORY**: Whenever you suggest a new feature, a new model, a new URL, or a new
> environment variable, you MUST include, as part of your response, the exact Markdown text
> to add or replace in the relevant section of this `AI_CONTEXT.md` file.  Format it as a
> clearly labelled block so the developer can paste it in directly.
