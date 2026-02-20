from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Expense, PaymentRequest, Transaction, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Extends the default UserAdmin to surface the `is_treasurer`
    field both in the list view and in the edit form.
    """

    # Show is_treasurer in the user list table
    list_display = BaseUserAdmin.list_display + ("is_treasurer",)
    list_filter = BaseUserAdmin.list_filter + ("is_treasurer",)

    # Add is_treasurer to the "Permissions" section of the change form
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Class Fund Role", {"fields": ("is_treasurer",)}),
    )

    # Also expose it on the "add user" form
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Class Fund Role", {"fields": ("is_treasurer",)}),
    )


@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display  = ("title", "amount", "assign_to_all", "due_date", "created_by", "created_at", "total_collected")
    list_filter   = ("assign_to_all", "due_date")
    search_fields = ("title", "description")
    readonly_fields = ("created_at", "total_collected")
    filter_horizontal = ("assigned_to",)

    fieldsets = (
        (None, {
            "fields": ("title", "description", "amount", "due_date", "created_by"),
        }),
        ("Assignment", {
            "fields": ("assign_to_all", "assigned_to"),
            "description": "Choose whether this request applies to everyone or specific students.",
        }),
        ("Metadata", {
            "fields": ("created_at", "total_collected"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="Collected (CZK)")
    def total_collected(self, obj):
        return obj.total_collected


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display  = ("student", "payment_request", "amount", "status", "paid_at", "confirmed_at")
    list_filter   = ("status",)
    search_fields = ("student__username", "student__first_name", "student__last_name",
                     "payment_request__title", "note")
    readonly_fields = ("created_at",)

    fieldsets = (
        (None, {
            "fields": ("payment_request", "student", "amount", "status", "note"),
        }),
        ("Timestamps", {
            "fields": ("paid_at", "confirmed_at", "created_at"),
        }),
    )


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display  = ("title", "amount", "category", "spent_at", "recorded_by", "is_published")
    list_filter   = ("category", "is_published", "spent_at")
    search_fields = ("title", "description")
    readonly_fields = ("created_at",)

    fieldsets = (
        (None, {
            "fields": ("title", "description", "amount", "category", "spent_at"),
        }),
        ("Publishing", {
            "fields": ("is_published", "recorded_by"),
        }),
        ("Metadata", {
            "fields": ("created_at",),
            "classes": ("collapse",),
        }),
    )
