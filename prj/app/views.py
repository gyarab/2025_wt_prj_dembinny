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

    Pulls:
      • Payment requests assigned to this student (all-class or explicitly assigned)
      • Their own transactions, grouped by status
      • Published expenses so they can see how the fund is being spent
    """
    user = req.user

    # All payment requests that apply to this student
    assigned_requests = PaymentRequest.objects.filter(
        Q(assign_to_all=True) | Q(assigned_to=user)
    ).distinct()

    # IDs of requests the student has already paid (confirmed)
    confirmed_request_ids = Transaction.objects.filter(
        student=user,
        status=Transaction.Status.CONFIRMED,
    ).values_list('payment_request_id', flat=True)

    # IDs of requests the student has a pending payment for
    pending_request_ids = Transaction.objects.filter(
        student=user,
        status=Transaction.Status.PENDING,
    ).values_list('payment_request_id', flat=True)

    # Requests still awaiting payment (no confirmed or pending transaction yet)
    unpaid_requests = assigned_requests.exclude(
        id__in=list(confirmed_request_ids) + list(pending_request_ids)
    )

    # Requests with a pending (unconfirmed) transaction
    awaiting_requests = assigned_requests.filter(id__in=pending_request_ids)

    # Full transaction history for this student, newest first
    my_transactions = Transaction.objects.filter(student=user).select_related(
        'payment_request'
    ).order_by('-created_at')

    # Summary stats
    total_owed = assigned_requests.exclude(
        id__in=confirmed_request_ids
    ).aggregate(s=Sum('amount'))['s'] or 0

    total_paid = Transaction.objects.filter(
        student=user,
        status=Transaction.Status.CONFIRMED,
    ).aggregate(s=Sum('amount'))['s'] or 0

    # Recent published expenses (last 10)
    recent_expenses = Expense.objects.filter(is_published=True).order_by('-spent_at')[:10]

    context = {
        'unpaid_requests':   unpaid_requests,
        'awaiting_requests': awaiting_requests,
        'my_transactions':   my_transactions,
        'recent_expenses':   recent_expenses,
        'total_owed':        total_owed,
        'total_paid':        total_paid,
        'today':             timezone.now().date(),
    }
    return render(req, 'dashboard.html', context)


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
