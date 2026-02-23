"""
accounts/admin.py
─────────────────
Admin registrations for CustomUser, SchoolClass, and StudentProfile.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import CustomUser, SchoolClass, StudentProfile


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    """
    Extends the default UserAdmin to surface the `role` and
    `hide_fund_balance` fields in both the list and edit views.
    """

    list_display  = BaseUserAdmin.list_display + ('role',)
    list_filter   = BaseUserAdmin.list_filter  + ('role',)

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Class Fund Role', {'fields': ('role', 'hide_fund_balance')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Class Fund Role', {'fields': ('role', 'hide_fund_balance')}),
    )


@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    list_display  = ('name', 'teacher', 'school_year', 'created_at')
    list_filter   = ('school_year',)
    search_fields = ('name', 'teacher__username', 'teacher__last_name')
    raw_id_fields = ('teacher',)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display  = ('child_name', 'school_class', 'parent', 'variable_symbol', 'is_active')
    list_filter   = ('school_class', 'is_active')
    search_fields = ('child_name', 'variable_symbol', 'parent__username', 'parent__last_name')
    raw_id_fields = ('parent',)
