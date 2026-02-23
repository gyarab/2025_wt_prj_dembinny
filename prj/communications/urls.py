"""
communications/urls.py
───────────────────────
URL patterns for the communications app.
Include in root urls.py with:
    path('communications/', include('communications.urls')),
"""

from django.urls import path

from . import views

urlpatterns = [
    path('notifications/', views.notification_log_view, name='notification_log'),
]
