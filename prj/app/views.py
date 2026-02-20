from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.db.models import Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import BankAccount, Expense, PaymentRequest, Transaction


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
    import qrcode

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
