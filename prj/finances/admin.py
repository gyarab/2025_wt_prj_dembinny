"""
finances/admin.py
─────────────────
Admin registrations for BankAccount, PaymentRequest, Transaction, Expense.
"""

from django.contrib import admin

from .models import BankAccount, Expense, PaymentRequest, Transaction


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display  = ('owner_name', 'account_number', 'school_class', 'is_active', 'updated_at')
    list_filter   = ('is_active',)
    search_fields = ('owner_name', 'account_number', 'iban')


@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display      = ('title', 'amount', 'assign_to_all', 'due_date', 'created_by', 'created_at', 'total_collected')
    list_filter       = ('assign_to_all', 'due_date')
    search_fields     = ('title', 'description')
    readonly_fields   = ('created_at', 'total_collected')
    filter_horizontal = ('assigned_to',)

    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'amount', 'due_date', 'created_by'),
        }),
        ('Czech Bank Symbols', {
            'fields': ('variable_symbol', 'specific_symbol'),
        }),
        ('Assignment', {
            'fields': ('assign_to_all', 'assigned_to'),
        }),
        ('Metadata', {
            'fields': ('created_at', 'total_collected'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Collected (CZK)')
    def total_collected(self, obj):
        return obj.total_collected


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display  = ('student', 'payment_request', 'amount', 'status', 'paid_at', 'confirmed_at')
    list_filter   = ('status',)
    search_fields = ('student__username', 'student__first_name', 'student__last_name',
                     'payment_request__title')
    readonly_fields = ('created_at',)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display  = ('title', 'amount', 'category', 'spent_at', 'recorded_by', 'is_published')
    list_filter   = ('category', 'is_published', 'spent_at')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at',)
