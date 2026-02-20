from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


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
