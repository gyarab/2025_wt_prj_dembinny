"""
communications/views.py
────────────────────────
Views for the communications app (future: send reminders, view notification log).
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import NotificationLog


@login_required
def notification_log_view(req):
    """
    Treasurer-only view: list of all sent notifications.
    Protected by treasurer_required in urls.py.
    """
    logs = NotificationLog.objects.select_related('recipient', 'payment_request').all()
    return render(req, 'communications/notification_log.html', {'logs': logs})
