"""
accounts/urls.py
────────────────
URL patterns for authentication and account management.
Include in the root urls.py with:
    path('', include('accounts.urls')),
"""

from django.urls import path

from . import views

urlpatterns = [
    path('login/',  views.login_view,  name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('password-change/',       views.password_change_view,      name='password_change'),
    path('password-change/done/',  views.password_change_done_view, name='password_change_done'),
]
