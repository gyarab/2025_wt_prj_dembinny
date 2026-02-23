"""
core/views.py
─────────────
Public pages: landing page, about page.
Custom error handlers (404 / 500) are registered in urls.py.
"""

from django.shortcuts import redirect, render


def home_view(req):
    """Landing page – authenticated users go straight to their dashboard."""
    if req.user.is_authenticated:
        return redirect('dashboard')
    return render(req, 'core/home.html')


def about_view(req):
    """Public about / info page."""
    return render(req, 'core/about.html')


# ── Custom error pages ────────────────────────────────────────────────────────

def handler404(req, exception):
    return render(req, 'core/404.html', status=404)


def handler500(req):
    return render(req, 'core/500.html', status=500)
