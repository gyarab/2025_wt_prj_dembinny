# Business Logic & Financial Documentation — Class Fund Manager

---

## 1. The Class Fund Lifecycle

Every financial event in the system follows this linear flow:

```
[Admin sets up SchoolClass + BankAccount]
         ↓
[Treasurer creates PaymentRequest]
         ↓
[Parent pays via bank transfer using student's VS]
         ↓
[Transaction recorded (manually or via API) → Status: PENDING]
         ↓
[Treasurer confirms the transaction → Status: CONFIRMED]
         ↓
[Treasurer logs Expense when money is spent from the fund]
         ↓
[Budget transparency page updated for all students]
```

---

## 2. Variable Symbol (VS) — Generation & Purpose

### What it is

A **Variable Symbol (VS)** is a numeric code (1–10 digits) that Czech banks use to identify
what a payment is for.  Every student in the system has a unique VS.  When a parent makes a
bank transfer, they include the student's VS so the system can automatically match the incoming
money to the correct student.

### Generation algorithm

Defined in `accounts/models.py` → `_next_vs_for_class(school_class)`:

```
Format: <vs_prefix><zero-padded sequence>

vs_prefix  ← SchoolClass.vs_prefix (2-digit string, e.g. "04")
sequence   ← next integer after the highest existing sequence in that class (001, 002 …)

Example:
  SchoolClass.vs_prefix = "04"
  Three existing students already have VS 04001, 04002, 04003
  → Next VS = "04004"
```

**Uniqueness guarantee**: After computing the candidate, `save()` checks
`StudentProfile.objects.filter(variable_symbol=candidate).exists()` in a loop and increments
the sequence until a free value is found.

**Fallback (no prefix set)**: A 6-digit random string is generated and retried until unique.

### When is VS generated?

`StudentProfile.save()` calls `_next_vs_for_class()` automatically whenever
`variable_symbol` is blank.  This means:

- CSV bulk import — the importer can leave `variable_symbol` blank; it is filled in on `profile.save()`.
- Manual profile creation via the admin panel — same auto-fill behaviour.
- VS can also be set explicitly (validated as `^\d{1,10}$`).

### `regenerate_vs()`

`StudentProfile.regenerate_vs()` clears the current VS and calls `save()`, forcing a new
generation.  Use this after assigning an un-classed student to a class so they receive a
class-prefixed VS instead of a random placeholder.

---

## 3. PaymentRequest — How it Works

### Creation

A treasurer (role: `TREASURER_FULL` or `TREASURER_ACCOUNTANT`, or System Admin) creates a
`PaymentRequest` with:

| Field | Description |
|---|---|
| `title` | Short description, e.g. "Field Trip – Prague Zoo" |
| `amount` | Fixed amount per student (CZK, 2 decimal places) |
| `due_date` | Optional deadline; past-due requests are flagged `is_overdue` in views |
| `assign_to_all` | If `True`, every active student in the class is expected to pay |
| `assigned_to` | M2M to specific `CustomUser` records (used when `assign_to_all=False`) |
| `variable_symbol` | Up to 10 digits — identifies the payment *purpose* (e.g. trip code) |
| `specific_symbol` | Up to 10 digits — optionally identifies the payer |
| `school_class` | FK to `SchoolClass` — **always required, never null in practice** |

### Who is assigned?

From `finances/views/utils.py` → `get_student_payment_data()`:

```python
assigned_requests = class_requests.filter(
    Q(assign_to_all=True) | Q(assigned_to=user)
).distinct()
```

A student is considered "assigned" to a request if either `assign_to_all=True` OR their user
is explicitly in the `assigned_to` M2M relation.

### Progress tracking

In `treasurer_dashboard_view`, per-request counters are computed inline:

| Attribute | Meaning |
|---|---|
| `pr.confirmed_count` | Transactions with status `CONFIRMED` |
| `pr.pending_count` | Transactions with status `PENDING` |
| `pr.expected_count` | `student_count` (if all) or `assigned_to.count()` |
| `pr.missing_count` | `max(0, expected − confirmed − pending)` |
| `pr.collected` | Sum of confirmed transaction amounts |
| `pr.expected_total` | `amount × expected_count` |

---

## 4. Transaction — Recording & Confirmation

### Status lifecycle

```
PENDING  →  CONFIRMED  (treasurer manually confirms, or Fio Bank API auto-matches)
PENDING  →  REJECTED   (treasurer rejects incorrect / duplicate payment)
```

### Manual recording (cash / physical payment)

The treasurer selects a student and a `PaymentRequest`, then submits the
`LogTransactionForm` in `finances/views/treasurer.py`.  This creates a `Transaction`
with `status=PENDING`.  The treasurer then explicitly confirms it to mark it `CONFIRMED`.

### Automatic bank reconciliation (Fio Bank API — planned)

> **Status: not yet implemented.**  The architecture is ready; the fetcher is the next
> major feature.  See `AI_CONTEXT.md` § 8 for status.

Planned flow:
1. A management command (or Render Cron Job) calls the Fio Bank read-only API to fetch
   new transactions for the class `BankAccount.account_number`.
2. For each incoming transfer, the fetcher reads the `variable_symbol` field.
3. It looks up `StudentProfile.objects.get(variable_symbol=vs, school_class=class)`.
4. It matches the amount against open `PaymentRequest` records for that student.
5. On a clean match, it creates a `Transaction` with `status=CONFIRMED` automatically.
6. Unmatched transfers (wrong VS, wrong amount) are flagged for manual review.

---

## 5. Expense — Fund Spending

An `Expense` record represents money **leaving** the class fund.

| Field | Description |
|---|---|
| `amount` | CZK spent |
| `category` | One of: Trip, Supplies, Food, Decoration, Donation, Other |
| `spent_at` | Date of the expenditure (defaults to today) |
| `is_published` | If `True`, every logged-in student can see it on the Budget page |
| `school_class` | Always scoped to the treasurer's class |

---

## 6. Fund Balance Calculation

The live fund balance is computed in `core/context_processors.py` → `fund_balance()` and
injected into every template:

```
fund_collected  =  SUM of Transaction.amount
                   WHERE status = 'confirmed'
                   AND   school_class = <current class>

fund_spent      =  SUM of Expense.amount
                   WHERE school_class = <current class>

fund_balance    =  fund_collected − fund_spent
```

This is a **real-time calculation** — there is no cached running total.  For large classes with
many transactions, consider adding a database index on `(status, school_class)`.

---

## 7. Discrepancy Handling

### Overpayment

There is currently **no automated overpayment credit** system.  If a parent pays more than the
`PaymentRequest.amount`, the `Transaction` is still recorded with the actual paid amount and
confirmed normally.  The excess is reflected in `fund_balance` as extra collected money.
A future feature should add a per-student balance ledger.

### Underpayment

A partial payment creates a `Transaction` with the partial amount.  The `PaymentRequest` is
still shown as outstanding to the student.  The treasurer should either:
- Accept the partial payment and manually log a follow-up transaction for the remainder.
- Reject the partial transaction and ask the student to re-pay the full amount.

### Unmatched VS (bank import)

When the VS on an incoming bank transfer does not match any `StudentProfile.variable_symbol`
in the expected class:
- The transaction is flagged for **manual review** by the treasurer.
- It is never silently dropped.
- The treasurer can manually assign it to the correct student.

---

## 8. SPAYD QR Code Generation

SPAYD (Short Payment Descriptor) is the Czech/Slovak standard for payment QR codes, supported
by every Czech mobile banking app.

Generated in `finances/views/utils.py` → `generate_spd_qr()`:

```
QR payload format:
  SPD*1.0*ACC:<IBAN or account_number>*CC:CZK[*AM:<amount>][*MSG:<message>][*X-VS:<vs>][*X-SS:<ss>]

Example (field trip payment):
  SPD*1.0*ACC:CZ6508000000192000145399*CC:CZK*AM:500.00*MSG:Field Trip Prague*X-VS:04003
```

The function returns a **base64-encoded PNG string** embedded directly in HTML as
`<img src="data:image/png;base64,...">`, requiring no file storage.

QR codes are attached to `PaymentRequest` objects (not stored in the DB) in
`attach_qr_to_requests()`.  They are regenerated on every page request.

---

## 9. Multi-Tenancy Safety Checklist

Before writing any finance query, verify all of these:

- [ ] `school_class` is resolved via `get_treasurer_class(user)` or `user.student_profile.school_class`
- [ ] Every `PaymentRequest` queryset has `.filter(school_class=school_class)`
- [ ] Every `Transaction` queryset has `.filter(school_class=school_class)`
- [ ] Every `Expense` queryset has `.filter(school_class=school_class)`
- [ ] Per-class permission is checked via `get_treasurer_membership(user, school_class).can_*`
- [ ] The context processor balance is **not** used for business logic — only for display
