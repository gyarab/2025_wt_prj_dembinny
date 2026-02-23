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


# ── Class-scoping helpers ─────────────────────────────────────────────────────

def get_treasurer_class(user):
    """
    Return the SchoolClass this treasurer manages, or None if they have no
    class assigned yet.  Always use this to scope treasurer querysets.
    """
    from accounts.models import SchoolClass
    return SchoolClass.objects.filter(teacher=user).first()


def get_class_students(school_class):
    """
    Return a queryset of active CustomUsers who are enrolled in *school_class*
    (i.e. have a StudentProfile pointing to that class), ordered for display.
    Returns an empty queryset when school_class is None.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    if school_class is None:
        return User.objects.none()
    return (
        User.objects
        .filter(student_profile__school_class=school_class, is_active=True)
        .order_by('last_name', 'first_name', 'username')
    )


def get_class_payment_requests(school_class):
    """
    Return a queryset of PaymentRequests that belong to *school_class*.
    Returns an empty queryset when school_class is None.
    """
    if school_class is None:
        return PaymentRequest.objects.none()
    return PaymentRequest.objects.filter(school_class=school_class)


def get_class_bank_account(school_class):
    """
    Return the active BankAccount for *school_class*, or None.
    Falls back to any active account when school_class is None (student views).
    """
    if school_class is None:
        return BankAccount.objects.filter(is_active=True).order_by('-updated_at').first()
    return BankAccount.objects.filter(
        school_class=school_class, is_active=True,
    ).order_by('-updated_at').first()


# ── Student payment data ──────────────────────────────────────────────────────

def get_student_payment_data(user):
    """
    Central helper that computes all finance-related querysets and stats
    for a given student.  Scopes payment requests to the student's own class
    (via StudentProfile) so they never see another class's requests.
    Returns a dict passed directly into template context.
    """
    # Determine the student's own class for scoping.
    school_class = getattr(
        getattr(user, 'student_profile', None), 'school_class', None
    )

    # Base queryset: requests from the student's class only.
    class_requests = (
        PaymentRequest.objects.filter(school_class=school_class)
        if school_class is not None
        else PaymentRequest.objects.none()
    )

    assigned_requests = class_requests.filter(
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
        'school_class':      school_class,
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

def unconfirmed_requests_for_student(student, school_class=None):
    """
    Return a queryset of PaymentRequests that *student* is assigned to but has
    NOT yet had a CONFIRMED transaction for.

    When *school_class* is given the result is further scoped to that class,
    ensuring treasurers never see or act on another class's requests.
    """
    confirmed_ids = Transaction.objects.filter(
        student=student,
        status=Transaction.Status.CONFIRMED,
    ).values_list('payment_request_id', flat=True)

    qs = PaymentRequest.objects.filter(
        Q(assign_to_all=True) | Q(assigned_to=student)
    ).exclude(id__in=confirmed_ids)

    if school_class is not None:
        qs = qs.filter(school_class=school_class)

    return qs.order_by('title')
