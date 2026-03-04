"""
accounts/urls.py
────────────────
URL patterns for authentication, account management, and the in-app admin panel.
Include in the root urls.py with:
    path('', include('accounts.urls')),
"""

from django.urls import path

from . import views, views_admin

urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────────────────
    path('login/',  views.login_view,  name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('password-change/',       views.password_change_view,      name='password_change'),
    path('password-change/done/',  views.password_change_done_view, name='password_change_done'),

    # ── In-app Admin Panel (System Admin only) ────────────────────────────────
    path('admin-panel/',
         views_admin.admin_panel_view,
         name='admin_panel'),

    # Fund Groups
    path('admin-panel/groups/create/',
         views_admin.fund_group_create_view,
         name='fund_group_create'),
    path('admin-panel/groups/<int:group_id>/edit/',
         views_admin.fund_group_edit_view,
         name='fund_group_edit'),
    path('admin-panel/groups/<int:group_id>/delete/',
         views_admin.fund_group_delete_view,
         name='fund_group_delete'),

    # Memberships
    path('admin-panel/memberships/add/',
         views_admin.membership_create_view,
         name='membership_create'),
    path('admin-panel/memberships/<int:membership_id>/edit/',
         views_admin.membership_edit_view,
         name='membership_edit'),
    path('admin-panel/memberships/<int:membership_id>/delete/',
         views_admin.membership_delete_view,
         name='membership_delete'),

    # Credentials export
    path('admin-panel/classes/<int:class_id>/export-credentials/',
         views_admin.export_credentials_view,
         name='export_credentials'),
]
