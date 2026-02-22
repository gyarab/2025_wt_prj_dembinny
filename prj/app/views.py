from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.db.models import Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import LogTransactionForm, PaymentRequestForm
from .models import BankAccount, Expense, PaymentRequest, Transaction, User


# ── Helpers ───────────────────────────────────────────────────────────────────

def _add_form_control_class(form):
    """Inject a CSS class onto every visible widget so templates can style them uniformly."""
    for field in form.fields.values():
        field.widget.attrs.setdefault('class', 'form-control-input')
    return form


def _get_student_payment_data(user):
    """
    Central helper that computes all finance-related querysets and stats
    for a given student.  Returned dict is passed directly into template context.
    """
    # All payment requests that apply to this student
    assigned_requests = PaymentRequest.objects.filter(
        Q(assign_to_all=True) | Q(assigned_to=user)
    ).distinct()

    confirmed_request_ids = list(Transaction.objects.filter(
        student=user, status=Transaction.Status.CONFIRMED,
    ).values_list('payment_request_id', flat=True))

    pending_request_ids = list(Transaction.objects.filter(
        student=user, status=Transaction.Status.PENDING,
    ).values_list('payment_request_id', flat=True))

    # Requests still awaiting payment (no confirmed or pending transaction yet)
    # Sorted: overdue first, then by due_date ascending, then no due_date last
    unpaid_requests = (
        assigned_requests
        .exclude(id__in=confirmed_request_ids + pending_request_ids)
        .order_by('due_date')          # NULLs sort last in SQLite ascending
    )

    # Requests the student submitted payment for but the treasurer hasn't confirmed yet
    awaiting_requests = assigned_requests.filter(id__in=pending_request_ids)

    # Full transaction history, newest first
    my_transactions = (
        Transaction.objects
        .filter(student=user)
        .select_related('payment_request')
        .order_by('-created_at')
    )

    total_owed = (
        assigned_requests
        .exclude(id__in=confirmed_request_ids)
        .aggregate(s=Sum('amount'))['s'] or 0
    )

    total_paid = (
        Transaction.objects
        .filter(student=user, status=Transaction.Status.CONFIRMED)
        .aggregate(s=Sum('amount'))['s'] or 0
    )

    today = timezone.now().date()

    # Attach an `is_overdue` flag per unpaid request for use in templates
    for req in unpaid_requests:
        req.is_overdue = bool(req.due_date and req.due_date < today)

    return {
        'assigned_requests':   assigned_requests,
        'unpaid_requests':     unpaid_requests,
        'awaiting_requests':   awaiting_requests,
        'my_transactions':     my_transactions,
        'total_owed':          total_owed,
        'total_paid':          total_paid,
        'today':               today,
    }


# ── Public pages ─────────────────────────────────────────────────────────────

def render_home(req):
    """Landing page. Authenticated users are sent straight to their dashboard."""
    if req.user.is_authenticated:
        return redirect('dashboard')
    return render(req, 'home.html')


def render_about(req):
    return render(req, 'about.html')


# ── Student Dashboard ─────────────────────────────────────────────────────────

@login_required
def dashboard_view(req):
    """
    Personal dashboard for any logged-in user.
    Shows summary cards + abbreviated tables.  Full detail is on dedicated pages.
    """
    context = _get_student_payment_data(req.user)

    # Dashboard shows only the most recent 5 transactions and 10 expenses
    context['my_transactions']  = context['my_transactions'][:5]
    context['recent_expenses']  = Expense.objects.filter(
        is_published=True
    ).order_by('-spent_at')[:5]

    return render(req, 'dashboard.html', context)


# ── Pending Payments (full dedicated view) ────────────────────────────────────

@login_required
def pending_payments_view(req):
    """
    Dedicated page listing every payment request the student still owes,
    sorted with overdue items first, then by due date.
    """
    data = _get_student_payment_data(req.user)

    context = {
        'unpaid_requests':   data['unpaid_requests'],
        'awaiting_requests': data['awaiting_requests'],
        'total_owed':        data['total_owed'],
        'today':             data['today'],
    }
    return render(req, 'pending_payments.html', context)


# ── Payment Info & QR Code ────────────────────────────────────────────────────

def _generate_spd_qr(
    account_id: str,
    amount=None,
    message: str = "",
    variable_symbol: str = "",
    specific_symbol: str = "",
    box_size: int = 7,
) -> str:
    """
    Build a Czech SPD Payment QR code and return it as a base64-encoded PNG string
    for use in <img src="data:image/png;base64,..."> tags.

    SPD fields used:
      ACC  – IBAN or local account number
      AM   – amount in CZK (omitted if None)
      CC   – currency (always CZK)
      MSG  – payment message / description
      X-VS – Variable Symbol (up to 10 digits)
      X-SS – Specific Symbol (up to 10 digits)
    """
    import base64
    import io
    try:
        import qrcode
    except Exception:
        # qrcode library is optional at runtime; return None so callers can
        # continue rendering pages without the pre-generated image.
        print("The library qrcode is not imported")
        return None

    parts = ["SPD*1.0", f"ACC:{account_id}", "CC:CZK"]
    if amount is not None:
        parts.append(f"AM:{amount}")
    if message:
        parts.append(f"MSG:{message[:60]}")   # SPD MSG cap
    if variable_symbol:
        parts.append(f"X-VS:{variable_symbol}")
    if specific_symbol:
        parts.append(f"X-SS:{specific_symbol}")

    spd_string = "*".join(parts)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=4,
    )
    qr.add_data(spd_string)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#1a1a2e", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _attach_qr_to_requests(requests, account):
    """
    Iterate a queryset/list of PaymentRequest objects and attach a `.qr_base64`
    attribute to each one so templates can render it inline.
    Silently skips QR generation if no account is configured.
    """
    if not account:
        for req in requests:
            req.qr_base64 = None
        return requests

    account_id = account.iban.strip() if account.iban.strip() else account.account_number.strip()

    for req in requests:
        try:
            req.qr_base64 = _generate_spd_qr(
                account_id=account_id,
                amount=req.amount,
                message=req.title,
                variable_symbol=req.variable_symbol,
                specific_symbol=req.specific_symbol,
            )
        except Exception:
            req.qr_base64 = None

    return requests


@login_required
def pending_payments_view(req):
    """
    Dedicated page listing every payment request the student still owes,
    sorted with overdue items first, then by due date.
    Each request carries a pre-generated QR code with its exact amount, VS and SS.
    """
    data    = _get_student_payment_data(req.user)
    account = BankAccount.objects.filter(is_active=True).order_by('-updated_at').first()

    # Force evaluation so we can attach attributes to the objects
    unpaid_list   = list(data['unpaid_requests'])
    awaiting_list = list(data['awaiting_requests'])

    _attach_qr_to_requests(unpaid_list,   account)
    _attach_qr_to_requests(awaiting_list, account)

    context = {
        'unpaid_requests':   unpaid_list,
        'awaiting_requests': awaiting_list,
        'total_owed':        data['total_owed'],
        'today':             data['today'],
        'account':           account,
    }
    return render(req, 'pending_payments.html', context)


@login_required
def payment_info_view(req):
    """
    Shows the class bank account details and a generic scannable QR code
    (no amount pre-filled — students use this to find the account details).
    """
    account = BankAccount.objects.filter(is_active=True).order_by('-updated_at').first()
    qr_base64 = None
    if account and account.account_number:
        account_id = account.iban.strip() if account.iban.strip() else account.account_number.strip()
        qr_base64 = _generate_spd_qr(
            account_id=account_id,
            message=f"Class Fund - {account.owner_name}",
        )

    return render(req, 'payment_info.html', {
        'account':   account,
        'qr_base64': qr_base64,
    })


def login_view(req):
    """Show the login form (GET) or authenticate and redirect (POST)."""
    if req.user.is_authenticated:
        return redirect('homepage')

    if req.method == 'POST':
        username = req.POST.get('username', '').strip()
        password = req.POST.get('password', '')
        user = authenticate(req, username=username, password=password)
        if user is not None:
            login(req, user)
            messages.success(req, f'Welcome back, {user.get_full_name() or user.username}!')
            # Honour the ?next= parameter so protected pages redirect properly
            next_url = req.POST.get('next') or req.GET.get('next') or 'dashboard'
            return redirect(next_url)
        else:
            messages.error(req, 'Invalid username or password. Please try again.')

    return render(req, 'login.html', {'next': req.GET.get('next', '')})


def logout_view(req):
    """Log the current user out (POST only for CSRF safety)."""
    if req.method == 'POST':
        logout(req)
        messages.info(req, 'You have been logged out.')
    return redirect('login')


# ── Password change ───────────────────────────────────────────────────────────

@login_required
def password_change_view(req):
    """Allow a logged-in user to change their own password."""
    if req.method == 'POST':
        form = PasswordChangeForm(req.user, req.POST)
        if form.is_valid():
            user = form.save()
            # Keep the session alive after the password change
            update_session_auth_hash(req, user)
            messages.success(req, 'Your password was updated successfully.')
            return redirect('password_change_done')
        else:
            messages.error(req, 'Please fix the errors below.')
    else:
        form = PasswordChangeForm(req.user)

    _add_form_control_class(form)
    return render(req, 'password_change.html', {'form': form})


@login_required
def password_change_done_view(req):
    """Simple confirmation page shown after a successful password change."""
    return render(req, 'password_change_done.html')


# ── Treasurer Dashboard ───────────────────────────────────────────────────────

def _treasurer_required(view_fn):
    """Decorator: redirect non-treasurers to their own dashboard."""
    from functools import wraps
    @wraps(view_fn)
    def wrapper(req, *args, **kwargs):
        if not req.user.is_authenticated:
            return redirect('login')
        if not req.user.is_treasurer:
            messages.error(req, 'Access denied – treasurer only.')
            return redirect('dashboard')
        return view_fn(req, *args, **kwargs)
    return wrapper


@_treasurer_required
def treasurer_dashboard_view(req):
    """
    Treasurer-only overview:
    - Fund totals (collected, spent, balance)
    - All active payment requests with per-request progress
    - All students with per-student paid/missing/pending summary
    - Recent unconfirmed transactions waiting for review
    """
    today = timezone.now().date()

    # ── Payment requests ──────────────────────────────────────────────────────
    all_requests = PaymentRequest.objects.prefetch_related(
        'transactions', 'assigned_to'
    ).order_by('-created_at')

    # Annotate each request with progress stats
    students = User.objects.filter(is_active=True, is_treasurer=False).order_by('last_name', 'first_name', 'username')
    student_count = students.count()

    for pr in all_requests:
        pr.confirmed_count = pr.transactions.filter(status=Transaction.Status.CONFIRMED).count()
        pr.pending_count   = pr.transactions.filter(status=Transaction.Status.PENDING).count()
        pr.expected_count  = student_count if pr.assign_to_all else pr.assigned_to.count()
        pr.missing_count   = max(0, pr.expected_count - pr.confirmed_count - pr.pending_count)
        pr.collected       = pr.transactions.filter(
            status=Transaction.Status.CONFIRMED
        ).aggregate(s=Sum('amount'))['s'] or 0
        pr.expected_total  = pr.amount * pr.expected_count
        pr.is_overdue      = bool(pr.due_date and pr.due_date < today)

    # ── Per-student summary ───────────────────────────────────────────────────
    confirmed_txs = Transaction.objects.filter(
        status=Transaction.Status.CONFIRMED
    ).select_related('student', 'payment_request')

    pending_txs = Transaction.objects.filter(
        status=Transaction.Status.PENDING
    ).select_related('student', 'payment_request')

    # Build lookup: student_id → set of confirmed/pending request ids
    confirmed_map: dict[int, set] = {}
    pending_map:   dict[int, set] = {}
    paid_amount_map: dict[int, int] = {}

    for tx in confirmed_txs:
        confirmed_map.setdefault(tx.student_id, set()).add(tx.payment_request_id)
        paid_amount_map[tx.student_id] = paid_amount_map.get(tx.student_id, 0) + int(tx.amount)

    for tx in pending_txs:
        pending_map.setdefault(tx.student_id, set()).add(tx.payment_request_id)

    # All request ids
    all_request_ids = set(pr.id for pr in all_requests)

    student_rows = []
    for student in students:
        s_confirmed = confirmed_map.get(student.id, set())
        s_pending   = pending_map.get(student.id, set())

        # Requests assigned to this student
        assigned_ids = set(
            PaymentRequest.objects.filter(
                Q(assign_to_all=True) | Q(assigned_to=student)
            ).values_list('id', flat=True)
        )

        missing_ids  = assigned_ids - s_confirmed - s_pending
        paid_total   = paid_amount_map.get(student.id, 0)

        owed_total = (
            PaymentRequest.objects.filter(id__in=missing_ids | s_pending)
            .aggregate(s=Sum('amount'))['s'] or 0
        )

        student_rows.append({
            'student':       student,
            'paid_count':    len(s_confirmed),
            'pending_count': len(s_pending),
            'missing_count': len(missing_ids),
            'paid_total':    paid_total,
            'owed_total':    owed_total,
        })

    # ── Fund totals ───────────────────────────────────────────────────────────
    total_collected = Transaction.objects.filter(
        status=Transaction.Status.CONFIRMED
    ).aggregate(s=Sum('amount'))['s'] or 0

    total_spent = Expense.objects.aggregate(s=Sum('amount'))['s'] or 0
    balance     = total_collected - total_spent

    # ── Pending transactions (awaiting treasurer action) ──────────────────────
    pending_transactions = (
        Transaction.objects
        .filter(status=Transaction.Status.PENDING)
        .select_related('student', 'payment_request')
        .order_by('created_at')
    )

    # ── Recent expenses ───────────────────────────────────────────────────────
    recent_expenses = Expense.objects.order_by('-spent_at')[:8]

    return render(req, 'treasurer_dashboard.html', {
        'all_requests':         all_requests,
        'student_rows':         student_rows,
        'pending_transactions': pending_transactions,
        'recent_expenses':      recent_expenses,
        'total_collected':      total_collected,
        'total_spent':          total_spent,
        'balance':              balance,
        'today':                today,
    })


# ── Create Payment Request ────────────────────────────────────────────────────

@_treasurer_required
def create_payment_request_view(req):
    """
    Treasurer-only form for creating a new PaymentRequest.

    - If 'Assign to whole class' is checked, `assign_to_all` is set to True
      and the M2M `assigned_to` list is left empty.
    - Otherwise, exactly the selected students are stored in `assigned_to`
      and `assign_to_all` is False.
    """
    if req.method == 'POST':
        form = PaymentRequestForm(req.POST)
        if form.is_valid():
            payment_request = form.save(commit=False)
            payment_request.created_by = req.user
            payment_request.save()

            # Save M2M only when targeting specific students
            if payment_request.assign_to_all:
                payment_request.assigned_to.clear()
            else:
                form.save_m2m()

            messages.success(
                req,
                f'Payment request "{payment_request.title}" created successfully.'
            )
            return redirect('treasurer_dashboard')
        else:
            messages.error(req, 'Please fix the errors below.')
    else:
        form = PaymentRequestForm()

    students = User.objects.filter(
        is_active=True, is_treasurer=False
    ).order_by('last_name', 'first_name', 'username')

    return render(req, 'create_payment_request.html', {
        'form':     form,
        'students': students,
    })


# ── Log Bank Transfer (create confirmed Transaction) ─────────────────────────

def _unconfirmed_requests_for_student(student):
    """
    Return a queryset of PaymentRequests that `student` is assigned to but has
    NOT yet had a CONFIRMED transaction for.  Used to populate the payment
    request dropdown on the log-transaction form.
    """
    confirmed_ids = Transaction.objects.filter(
        student=student,
        status=Transaction.Status.CONFIRMED,
    ).values_list('payment_request_id', flat=True)

    return PaymentRequest.objects.filter(
        Q(assign_to_all=True) | Q(assigned_to=student)
    ).exclude(id__in=confirmed_ids).order_by('title')


@_treasurer_required
def log_transaction_view(req, pr_id=None, student_id=None):
    """
    Treasurer-only form for manually logging an incoming bank transfer.

    Supports two entry points:
      • /treasurer/transactions/log/                          — blank form
      • /treasurer/transactions/log/<pr_id>/<student_id>/    — pre-filled shortcut
        (e.g. clicking "✓ Confirm" on a pending transaction row)

    On POST the Transaction is created with status=CONFIRMED immediately and
    any existing PENDING transaction for the same (student, request) pair is
    deleted (it has been superseded by this confirmed record).
    """
    import json

    students = User.objects.filter(
        is_active=True, is_treasurer=False
    ).order_by('last_name', 'first_name', 'username')

    # Build a JSON map  { student_pk: [ {id, title, amount}, … ] }
    # so the JS can update the payment-request dropdown without a round-trip.
    requests_by_student = {}
    for student in students:
        qs = _unconfirmed_requests_for_student(student)
        requests_by_student[str(student.pk)] = [
            {'id': pr.id, 'title': str(pr), 'amount': str(pr.amount)}
            for pr in qs
        ]

    # Determine initial values when coming from a pre-fill shortcut
    initial = {}
    pre_student = None
    if student_id:
        pre_student = User.objects.filter(pk=student_id, is_active=True, is_treasurer=False).first()
        if pre_student:
            initial['student'] = pre_student
    # Also support ?student=<pk> query param (from the students table icon)
    elif req.method == 'GET' and req.GET.get('student'):
        try:
            pre_student = User.objects.get(pk=int(req.GET['student']), is_active=True, is_treasurer=False)
            initial['student'] = pre_student
        except (User.DoesNotExist, ValueError):
            pass
    if pr_id and pre_student:
        pr_qs = _unconfirmed_requests_for_student(pre_student)
        pre_pr = pr_qs.filter(pk=pr_id).first()
        if pre_pr:
            initial['payment_request'] = pre_pr
            initial['amount']          = pre_pr.amount

    # Also handle confirming an existing pending transaction
    pending_tx = None
    if pr_id and student_id:
        pending_tx = Transaction.objects.filter(
            payment_request_id=pr_id,
            student_id=student_id,
            status=Transaction.Status.PENDING,
        ).first()
        if pending_tx:
            initial.setdefault('amount', pending_tx.amount)
            initial.setdefault('note',   pending_tx.note)

    if req.method == 'POST':
        # Restrict payment_request choices to the posted student's unconfirmed set
        posted_student_id = req.POST.get('student')
        pr_qs = PaymentRequest.objects.none()
        if posted_student_id:
            try:
                posted_student = User.objects.get(pk=posted_student_id)
                pr_qs = _unconfirmed_requests_for_student(posted_student)
                # Also include already-confirmed requests so validation message is clear
                pr_qs = PaymentRequest.objects.filter(
                    Q(assign_to_all=True) | Q(assigned_to=posted_student)
                )
            except User.DoesNotExist:
                pr_qs = PaymentRequest.objects.all()

        form = LogTransactionForm(req.POST, pr_queryset=pr_qs)
        if form.is_valid():
            cd      = form.cleaned_data
            student = cd['student']
            pr      = cd['payment_request']
            now     = timezone.now()

            # Remove any pending transaction for this (student, request) pair —
            # the treasurer is now logging the confirmed bank transfer directly.
            Transaction.objects.filter(
                student=student,
                payment_request=pr,
                status=Transaction.Status.PENDING,
            ).delete()

            Transaction.objects.create(
                student         = student,
                payment_request = pr,
                amount          = cd['amount'],
                status          = Transaction.Status.CONFIRMED,
                note            = cd.get('note', ''),
                paid_at         = cd['paid_at'],
                confirmed_at    = now,
            )

            messages.success(
                req,
                f'✅ Transfer logged: {student.get_full_name() or student.username} '
                f'→ "{pr.title}" ({cd["amount"]} CZK) marked as Confirmed.'
            )
            return redirect('treasurer_dashboard')
        else:
            messages.error(req, 'Please fix the errors below.')
    else:
        pr_qs = PaymentRequest.objects.all()
        if pre_student:
            pr_qs = PaymentRequest.objects.filter(
                Q(assign_to_all=True) | Q(assigned_to=pre_student)
            )
        form = LogTransactionForm(initial=initial, pr_queryset=pr_qs)

    return render(req, 'log_transaction.html', {
        'form':                  form,
        'students':              students,
        'requests_by_student':   json.dumps(requests_by_student),
        'pending_tx':            pending_tx,
    })


@_treasurer_required
def student_requests_json(req, student_id):
    """
    AJAX helper: returns JSON list of unconfirmed PaymentRequests for one student.
    Used by the JS on the log-transaction form to refresh the dropdown.
    """
    import json
    from django.http import JsonResponse

    student = User.objects.filter(pk=student_id, is_active=True, is_treasurer=False).first()
    if not student:
        return JsonResponse([], safe=False)

    data = [
        {'id': pr.id, 'title': str(pr), 'amount': str(pr.amount)}
        for pr in _unconfirmed_requests_for_student(student)
    ]
    return JsonResponse(data, safe=False)
