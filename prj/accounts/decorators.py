"""
accounts/decorators.py
──────────────────────
Role-based access decorators for views.

Usage
─────
    from accounts.decorators import role_required

    @role_required('treasurer')
    def my_view(request): ...

    # Multiple roles allowed:
    @role_required('system_admin', 'treasurer')
    def admin_or_treasurer_view(request): ...

Pre-built shortcuts
───────────────────
    @treasurer_required
    @student_required
    @parent_required
    @admin_required
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import CustomUser


def role_required(*roles):
    """
    Decorator that restricts a view to users whose ``role`` is in *roles*.

    *roles* should be one or more ``CustomUser.Role`` values (strings), e.g.::

        @role_required('treasurer', 'system_admin')

    Unauthenticated requests are redirected to the login page.
    Authenticated users with the wrong role receive a 403-style redirect to
    their dashboard with an error message.
    """
    allowed = set(roles)

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if request.user.role in allowed or request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            messages.error(
                request,
                "You don't have permission to access that page.",
            )
            return redirect('dashboard')

        return _wrapped

    return decorator


# ── Shortcut decorators ───────────────────────────────────────────────────────

admin_required = role_required(CustomUser.Role.SYSTEM_ADMIN)
treasurer_required = role_required(CustomUser.Role.TREASURER, CustomUser.Role.SYSTEM_ADMIN)
student_required = role_required(CustomUser.Role.STUDENT)
parent_required = role_required(CustomUser.Role.PARENT)
