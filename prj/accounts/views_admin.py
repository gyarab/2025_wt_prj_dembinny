"""
accounts/views_admin.py
───────────────────────
System-Admin-only management views for Classes and ClassMemberships.

URL namespace: these views are wired under /admin-panel/ in accounts/urls.py
and protected by @admin_required.

Views
─────
admin_panel_view          – overview: list of all classes + their members
membership_create_view    – create a new ClassMembership
membership_edit_view      – edit an existing ClassMembership's tier
membership_delete_view    – remove a ClassMembership (POST-only)
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from .decorators import admin_required
from .forms_admin import ClassMembershipForm
from .models import ClassMembership, SchoolClass


# ── Overview ──────────────────────────────────────────────────────────────────

@admin_required
def admin_panel_view(req):
    """
    Main admin panel page.
    Lists every SchoolClass with its current ClassMembership entries so the
    admin can see who has access to what at a glance.
    """
    classes = (
        SchoolClass.objects
        .prefetch_related('memberships__user')
        .select_related('teacher')
        .order_by('name')
    )
    return render(req, 'accounts/admin_panel.html', {
        'classes':    classes,
        'tier_choices': ClassMembership.Tier.choices,
    })


# ── Create membership ─────────────────────────────────────────────────────────

@admin_required
def membership_create_view(req):
    """
    GET  → show the blank form (optionally pre-fill school_class from ?class=<pk>).
    POST → validate and create the ClassMembership.
    """
    initial = {}
    if req.method == 'GET' and req.GET.get('class'):
        try:
            initial['school_class'] = SchoolClass.objects.get(pk=int(req.GET['class']))
        except (SchoolClass.DoesNotExist, ValueError):
            pass

    if req.method == 'POST':
        form = ClassMembershipForm(req.POST)
        if form.is_valid():
            membership = form.save()
            messages.success(
                req,
                f'✅ {membership.user.get_full_name() or membership.user.username} '
                f'added to {membership.school_class} as '
                f'{membership.get_tier_display()}.'
            )
            return redirect('admin_panel')
        messages.error(req, 'Please fix the errors below.')
    else:
        form = ClassMembershipForm(initial=initial)

    return render(req, 'accounts/membership_form.html', {
        'form':  form,
        'title': 'Add Class Member',
        'submit_label': 'Add Member',
    })


# ── Edit membership ───────────────────────────────────────────────────────────

@admin_required
def membership_edit_view(req, membership_id):
    """
    GET  → pre-filled form for an existing ClassMembership.
    POST → update the tier (school_class and user are read-only after creation).
    """
    membership = get_object_or_404(ClassMembership, pk=membership_id)

    if req.method == 'POST':
        form = ClassMembershipForm(req.POST, instance=membership)
        if form.is_valid():
            form.save()
            messages.success(
                req,
                f'✅ Updated: {membership.user.get_full_name() or membership.user.username} '
                f'in {membership.school_class} → {membership.get_tier_display()}.'
            )
            return redirect('admin_panel')
        messages.error(req, 'Please fix the errors below.')
    else:
        form = ClassMembershipForm(instance=membership)

    return render(req, 'accounts/membership_form.html', {
        'form':       form,
        'membership': membership,
        'title':      'Edit Class Membership',
        'submit_label': 'Save Changes',
    })


# ── Delete membership ─────────────────────────────────────────────────────────

@admin_required
def membership_delete_view(req, membership_id):
    """POST-only: remove a ClassMembership."""
    if req.method != 'POST':
        return redirect('admin_panel')

    membership = get_object_or_404(ClassMembership, pk=membership_id)
    name  = membership.user.get_full_name() or membership.user.username
    klass = str(membership.school_class)
    membership.delete()
    messages.success(req, f'🗑 Removed {name} from {klass}.')
    return redirect('admin_panel')
