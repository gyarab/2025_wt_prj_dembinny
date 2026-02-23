"""
finances/views/utils.py
────────────────────────
Shared helpers used by both student and treasurer view modules.
Nothing here imports from other view modules (no circular imports).
"""

from functools import wraps

from django.contrib import messages
from django.db.models import Q, Sum
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect
from django.utils import timezone

from ..models import BankAccount, PaymentRequest, Transaction


# ── Form styling ──────────────────────────────────────────────────────────────

def add_form_control_class(form):
    """Inject a uniform CSS class onto every visible widget."""
    for field in form.fields.values():
        field.widget.attrs.setdefault('class', 'form-control-input')
    return form


# ── Access control ────────────────────────────────────────────────────────────

def treasurer_required(view_fn):
    """
    Decorator: unauthenticated users → login, non-treasurers → dashboard
    with an error message.
    """
    @wraps(view_fn)
    def wrapper(req, *args, **kwargs):
        if not req.user.is_authenticated:
            return redirect('login')
        if not req.user.is_treasurer:
            messages.error(req, 'Access denied – treasurer only.')
            return redirect('dashboard')
        return view_fn(req, *args, **kwargs)
    return wrapper


def require_POST_or_405(view_fn):
    """Decorator: return 405 for any non-POST request."""
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
    for a given student.  Returns a dict passed directly into template context.
    """
    assigned_requests = PaymentRequest.objects.filter(
        Q(assign_to_all=True) | Q(assigned_to=user)
    ).distinct()

    confirmed_ids = list(Transaction.objects.filter(
        student=user, status=Transaction.Status.CONFIRMED,
    ).values_list('payment_request_id', flat=True))

    pending_ids = list(Transaction.objects.filter(
        student=user, status=Transaction.Status.PENDING,
    ).values_list('payment_request_id', flat=True))

    unpaid_requests = (
        assigned_requests
        .exclude(id__in=confirmed_ids + pending_ids)
        .order_by('due_date')
    )
    awaiting_requests = assigned_requests.filter(id__in=pending_ids)
    my_transactions = (
        Transaction.objects
        .filter(student=user)
        .select_related('payment_request')
        .order_by('-created_at')
    )
    total_owed = (
        assigned_requests
        .exclude(id__in=confirmed_ids)
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
        'assigned_requests': assigned_requests,
        'unpaid_requests':   unpaid_requests,
        'awaiting_requests': awaiting_requests,
        'my_transactions':   my_transactions,
        'total_owed':        total_owed,
        'total_paid':        total_paid,
        'today':             today,
    }


# ── QR code helpers ───────────────────────────────────────────────────────────

def generate_spd_qr(
    account_id: str,
    amount=None,
    message: str = '',
    variable_symbol: str = '',
    specific_symbol: str = '',
    box_size: int = 7,
):
    """
    Build a Czech SPAYD QR code and return it as a base64-encoded PNG string.
    Returns None if the optional ``qrcode`` library is not installed.
    """
    import base64
    import io

    try:
        import qrcode
    except Exception:
        return None

    parts = ['SPD*1.0', f'ACC:{account_id}', 'CC:CZK']
    if amount is not None:
        parts.append(f'AM:{amount}')
    if message:
        parts.append(f'MSG:{message[:60]}')
    if variable_symbol:
        parts.append(f'X-VS:{variable_symbol}')
    if specific_symbol:
        parts.append(f'X-SS:{specific_symbol}')

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=4,
    )
    qr.add_data('*'.join(parts))
    qr.make(fit=True)

    img = qr.make_image(fill_color='#1a1a2e', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode('utf-8')


def attach_qr_to_requests(requests, account):
    """
    Attach a ``.qr_base64`` attribute to each PaymentRequest object.
    Safe when *account* is None.
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
