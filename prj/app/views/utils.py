"""
app/views/utils.py
──────────────────
Small helpers shared by multiple view modules.
Nothing here depends on any other view module (no circular imports).
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, Sum
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect
from django.utils import timezone

from ..models import BankAccount, PaymentRequest, Transaction


# ── Form styling ──────────────────────────────────────────────────────────────

def add_form_control_class(form):
    """Inject a CSS class onto every visible widget so templates can style them uniformly."""
    for field in form.fields.values():
        field.widget.attrs.setdefault('class', 'form-control-input')
    return form


# ── Access control ────────────────────────────────────────────────────────────

def _is_treasurer(user):
    """Test function for user_passes_test: True only for active treasurers."""
    return user.is_active and user.is_treasurer


def treasurer_required(view_fn):
    """
    Decorator that enforces treasurer-only access with two layers:

    1. @login_required  — unauthenticated users are redirected to /login/?next=<url>
                          so they land back on the protected page after signing in.
    2. @user_passes_test(_is_treasurer, raise_exception=False)
                        — authenticated non-treasurers are bounced to /dashboard/
                          with an error message instead of seeing a 403 page.

    Stack order (outermost first): login_required → user_passes_test → view
    """
    @wraps(view_fn)
    def _access_denied(req, *args, **kwargs):
        messages.error(req, 'Access denied – treasurer only.')
        return redirect('dashboard')

    # user_passes_test redirects to login by default; override with our bounce
    protected = login_required(
        user_passes_test(
            _is_treasurer,
            login_url='dashboard',   # sends authenticated non-treasurers here …
        )(view_fn)
    )

    @wraps(view_fn)
    def wrapper(req, *args, **kwargs):
        if req.user.is_authenticated and not req.user.is_treasurer:
            # Add a visible flash message before the redirect
            messages.error(req, 'Access denied – treasurer only.')
            return redirect('dashboard')
        return protected(req, *args, **kwargs)

    return wrapper


def require_POST_or_405(view_fn):
    """
    Decorator: return HTTP 405 Method Not Allowed for any non-POST request
    instead of silently redirecting.  Use on write-only endpoints.
    """
    @wraps(view_fn)
    def wrapper(req, *args, **kwargs):
        if req.method != 'POST':
            return HttpResponseNotAllowed(['POST'])
        return view_fn(req, *args, **kwargs)
    return wrapper


# ── Student payment data ──────────────────────────────────────────────────────

def get_student_payment_data(user):
    """
    Central helper that computes all finance-related querysets and stats
    for a given student.  Returned dict is passed directly into template context.
    """
    assigned_requests = PaymentRequest.objects.filter(
        Q(assign_to_all=True) | Q(assigned_to=user)
    ).distinct()

    confirmed_request_ids = list(Transaction.objects.filter(
        student=user, status=Transaction.Status.CONFIRMED,
    ).values_list('payment_request_id', flat=True))

    pending_request_ids = list(Transaction.objects.filter(
        student=user, status=Transaction.Status.PENDING,
    ).values_list('payment_request_id', flat=True))

    unpaid_requests = (
        assigned_requests
        .exclude(id__in=confirmed_request_ids + pending_request_ids)
        .order_by('due_date')
    )

    awaiting_requests = assigned_requests.filter(id__in=pending_request_ids)

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


# ── QR code helpers ───────────────────────────────────────────────────────────

def generate_spd_qr(
    account_id: str,
    amount=None,
    message: str = "",
    variable_symbol: str = "",
    specific_symbol: str = "",
    box_size: int = 7,
):
    """
    Build a Czech SPD Payment QR code and return it as a base64-encoded PNG string
    for use in <img src="data:image/png;base64,..."> tags.
    Returns None if the optional `qrcode` library is not installed.
    """
    import base64
    import io
    try:
        import qrcode
    except Exception:
        return None

    parts = ["SPD*1.0", f"ACC:{account_id}", "CC:CZK"]
    if amount is not None:
        parts.append(f"AM:{amount}")
    if message:
        parts.append(f"MSG:{message[:60]}")
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


def attach_qr_to_requests(requests, account):
    """
    Attach a `.qr_base64` attribute to each PaymentRequest object in *requests*
    so templates can render the QR inline.  Safe when account is None.
    """
    if not account:
        for req in requests:
            req.qr_base64 = None
        return requests

    account_id = account.iban.strip() if account.iban.strip() else account.account_number.strip()

    for req in requests:
        try:
            req.qr_base64 = generate_spd_qr(
                account_id=account_id,
                amount=req.amount,
                message=req.title,
                variable_symbol=req.variable_symbol,
                specific_symbol=req.specific_symbol,
            )
        except Exception:
            req.qr_base64 = None

    return requests


# ── Treasurer helpers ─────────────────────────────────────────────────────────

def unconfirmed_requests_for_student(student):
    """
    Return a queryset of PaymentRequests that *student* is assigned to but has
    NOT yet had a CONFIRMED transaction for.
    """
    confirmed_ids = Transaction.objects.filter(
        student=student,
        status=Transaction.Status.CONFIRMED,
    ).values_list('payment_request_id', flat=True)

    return PaymentRequest.objects.filter(
        Q(assign_to_all=True) | Q(assigned_to=student)
    ).exclude(id__in=confirmed_ids).order_by('title')



# ── Form styling ──────────────────────────────────────────────────────────────

def add_form_control_class(form):
    """Inject a CSS class onto every visible widget so templates can style them uniformly."""
    for field in form.fields.values():
        field.widget.attrs.setdefault('class', 'form-control-input')
    return form


# ── Student payment data ──────────────────────────────────────────────────────

def get_student_payment_data(user):
    """
    Central helper that computes all finance-related querysets and stats
    for a given student.  Returned dict is passed directly into template context.
    """
    assigned_requests = PaymentRequest.objects.filter(
        Q(assign_to_all=True) | Q(assigned_to=user)
    ).distinct()

    confirmed_request_ids = list(Transaction.objects.filter(
        student=user, status=Transaction.Status.CONFIRMED,
    ).values_list('payment_request_id', flat=True))

    pending_request_ids = list(Transaction.objects.filter(
        student=user, status=Transaction.Status.PENDING,
    ).values_list('payment_request_id', flat=True))

    unpaid_requests = (
        assigned_requests
        .exclude(id__in=confirmed_request_ids + pending_request_ids)
        .order_by('due_date')
    )

    awaiting_requests = assigned_requests.filter(id__in=pending_request_ids)

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


# ── QR code helpers ───────────────────────────────────────────────────────────

def generate_spd_qr(
    account_id: str,
    amount=None,
    message: str = "",
    variable_symbol: str = "",
    specific_symbol: str = "",
    box_size: int = 7,
):
    """
    Build a Czech SPD Payment QR code and return it as a base64-encoded PNG string
    for use in <img src="data:image/png;base64,..."> tags.
    Returns None if the optional `qrcode` library is not installed.
    """
    import base64
    import io
    try:
        import qrcode
    except Exception:
        return None

    parts = ["SPD*1.0", f"ACC:{account_id}", "CC:CZK"]
    if amount is not None:
        parts.append(f"AM:{amount}")
    if message:
        parts.append(f"MSG:{message[:60]}")
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


def attach_qr_to_requests(requests, account):
    """
    Attach a `.qr_base64` attribute to each PaymentRequest object in *requests*
    so templates can render the QR inline.  Safe when account is None.
    """
    if not account:
        for req in requests:
            req.qr_base64 = None
        return requests

    account_id = account.iban.strip() if account.iban.strip() else account.account_number.strip()

    for req in requests:
        try:
            req.qr_base64 = generate_spd_qr(
                account_id=account_id,
                amount=req.amount,
                message=req.title,
                variable_symbol=req.variable_symbol,
                specific_symbol=req.specific_symbol,
            )
        except Exception:
            req.qr_base64 = None

    return requests


# ── Treasurer access decorator ────────────────────────────────────────────────

def treasurer_required(view_fn):
    """Decorator: redirect non-treasurers to their own dashboard."""
    from functools import wraps
    from django.contrib import messages
    from django.shortcuts import redirect

    @wraps(view_fn)
    def wrapper(req, *args, **kwargs):
        if not req.user.is_authenticated:
            return redirect('login')
        if not req.user.is_treasurer:
            messages.error(req, 'Access denied – treasurer only.')
            return redirect('dashboard')
        return view_fn(req, *args, **kwargs)
    return wrapper


# ── Treasurer helpers ─────────────────────────────────────────────────────────

def unconfirmed_requests_for_student(student):
    """
    Return a queryset of PaymentRequests that *student* is assigned to but has
    NOT yet had a CONFIRMED transaction for.
    """
    confirmed_ids = Transaction.objects.filter(
        student=student,
        status=Transaction.Status.CONFIRMED,
    ).values_list('payment_request_id', flat=True)

    return PaymentRequest.objects.filter(
        Q(assign_to_all=True) | Q(assigned_to=student)
    ).exclude(id__in=confirmed_ids).order_by('title')
