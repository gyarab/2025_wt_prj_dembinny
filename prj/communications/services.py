"""
communications/services.py
──────────────────────────
Service functions for sending emails and generating QR codes.

These are called by views in finances/ and by management commands,
keeping all "talk to the outside world" logic in one place.

Functions
─────────
send_welcome_email(user, school_class)
    Send the initial welcome email to a newly created parent account.

send_payment_reminder(user, payment_request)
    Send a reminder email about an overdue or upcoming payment.

send_receipt(user, transaction)
    Send a confirmation receipt after a payment is confirmed.

generate_spayd_qr_attachment(payment_request, account)
    Return a base64-encoded PNG of the SPAYD QR code for use in emails.
"""

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from .models import NotificationLog


def _log(recipient, notification_type, channel, subject, body, payment_request=None,
         success=True, error=''):
    """Internal helper to persist a NotificationLog entry."""
    NotificationLog.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        channel=channel,
        subject=subject,
        body_preview=body[:500],
        payment_request=payment_request,
        sent_at=timezone.now(),
        success=success,
        error_message=error,
    )


def send_welcome_email(user, school_class=None):
    """
    Send a welcome email to a newly registered parent.
    Returns True on success, False on failure.
    """
    subject = 'Welcome to Class Fund Manager'
    context = {
        'user':         user,
        'school_class': school_class,
        'login_url':    getattr(settings, 'SITE_URL', '') + '/login/',
    }
    body = render_to_string('communications/email/welcome.txt', context)

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        _log(user, NotificationLog.NotificationType.WELCOME,
             NotificationLog.Channel.EMAIL, subject, body)
        return True
    except Exception as exc:
        _log(user, NotificationLog.NotificationType.WELCOME,
             NotificationLog.Channel.EMAIL, subject, body,
             success=False, error=str(exc))
        return False


def send_payment_reminder(user, payment_request):
    """
    Send a payment reminder email for a specific PaymentRequest.
    Returns True on success, False on failure.
    """
    subject = f'Payment Reminder: {payment_request.title}'
    context = {
        'user':            user,
        'payment_request': payment_request,
        'login_url':       getattr(settings, 'SITE_URL', '') + '/login/',
    }
    body = render_to_string('communications/email/payment_reminder.txt', context)

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        _log(user, NotificationLog.NotificationType.PAYMENT_REMINDER,
             NotificationLog.Channel.EMAIL, subject, body,
             payment_request=payment_request)
        return True
    except Exception as exc:
        _log(user, NotificationLog.NotificationType.PAYMENT_REMINDER,
             NotificationLog.Channel.EMAIL, subject, body,
             payment_request=payment_request, success=False, error=str(exc))
        return False
