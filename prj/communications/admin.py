"""
communications/admin.py
────────────────────────
Admin for NotificationLog.
"""

from django.contrib import admin

from .models import NotificationLog


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display  = ('notification_type', 'channel', 'recipient', 'payment_request', 'sent_at', 'success')
    list_filter   = ('notification_type', 'channel', 'success', 'sent_at')
    search_fields = ('recipient__username', 'recipient__last_name', 'subject')
    readonly_fields = ('sent_at',)

    fieldsets = (
        (None, {
            'fields': ('recipient', 'notification_type', 'channel', 'payment_request'),
        }),
        ('Content', {
            'fields': ('subject', 'body_preview'),
        }),
        ('Result', {
            'fields': ('success', 'error_message', 'sent_at'),
        }),
    )
