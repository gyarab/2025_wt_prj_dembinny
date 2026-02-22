"""
app/views/auth.py
─────────────────
Login, logout, and password-change views.
"""

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render

from .utils import add_form_control_class


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


@login_required
def password_change_view(req):
    """Allow a logged-in user to change their own password."""
    if req.method == 'POST':
        form = PasswordChangeForm(req.user, req.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(req, user)
            messages.success(req, 'Your password was updated successfully.')
            return redirect('password_change_done')
        else:
            messages.error(req, 'Please fix the errors below.')
    else:
        form = PasswordChangeForm(req.user)

    add_form_control_class(form)
    return render(req, 'password_change.html', {'form': form})


@login_required
def password_change_done_view(req):
    """Confirmation page shown after a successful password change."""
    return render(req, 'password_change_done.html')
