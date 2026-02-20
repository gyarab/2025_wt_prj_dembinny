from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.db.models import Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import Expense, PaymentRequest, Transaction


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


# ── Authentication ────────────────────────────────────────────────────────────

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
