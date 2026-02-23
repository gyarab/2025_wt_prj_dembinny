"""
communications/models.py
─────────────────────────
Models for outbound communication tracking.

NotificationLog – records every automated email/notification sent,
                  so the treasurer can see when reminders were dispatched.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class NotificationLog(models.Model):
    """
    Tracks outbound notifications (welcome emails, payment reminders, etc.)
    sent by the system.

    This gives the treasurer a full audit trail:
    "Reminder email sent to Parent X on Tuesday."
    """

    class NotificationType(models.TextChoices):
        WELCOME          = 'welcome',          'Welcome Email'
        PAYMENT_REMINDER = 'payment_reminder', 'Payment Reminder'
        RECEIPT          = 'receipt',          'Payment Receipt'
        CUSTOM           = 'custom',           'Custom Message'

    class Channel(models.TextChoices):
        EMAIL = 'email', 'Email'
        SMS   = 'sms',   'SMS'

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='notifications_received',
        help_text='The user (parent) who received this notification.',
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        default=NotificationType.PAYMENT_REMINDER,
    )
    channel = models.CharField(
        max_length=10,
        choices=Channel.choices,
        default=Channel.EMAIL,
    )
    subject = models.CharField(
        max_length=255,
        blank=True,
        help_text='Email subject line or SMS header.',
    )
    body_preview = models.TextField(
        blank=True,
        help_text='First 500 characters of the message body (for the audit log).',
    )
    # Optional FK to a specific PaymentRequest this reminder is about
    payment_request = models.ForeignKey(
        'finances.PaymentRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications',
        help_text='The payment request this reminder is about (if applicable).',
    )
    sent_at = models.DateTimeField(default=timezone.now)
    success = models.BooleanField(
        default=True,
        help_text='False if the send attempt failed (e.g. bounce, SMTP error).',
    )
    error_message = models.TextField(
        blank=True,
        help_text='Error details if success=False.',
    )

    class Meta:
        ordering = ['-sent_at']
        verbose_name = 'Notification Log'
        verbose_name_plural = 'Notification Logs'

    def __str__(self):
        recipient_label = str(self.recipient) if self.recipient else 'unknown'
        return (
            f"[{self.get_notification_type_display()}] "
            f"→ {recipient_label} "
            f"({self.sent_at.strftime('%Y-%m-%d %H:%M')})"
        )
