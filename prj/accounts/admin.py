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
    Extends the default UserAdmin to surface is_treasurer and hide_fund_balance.
    """

    list_display  = BaseUserAdmin.list_display + ('is_treasurer',)
    list_filter   = BaseUserAdmin.list_filter  + ('is_treasurer',)

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Class Fund Role', {'fields': ('is_treasurer', 'hide_fund_balance')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Class Fund Role', {'fields': ('is_treasurer', 'hide_fund_balance')}),
    )


@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    list_display  = ('name', 'teacher', 'school_year', 'created_at')
    list_filter   = ('school_year',)
    search_fields = ('name', 'teacher__username', 'teacher__last_name')
    raw_id_fields = ('teacher',)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display  = ('user', 'school_class', 'parent', 'variable_symbol', 'is_active')
    list_filter   = ('school_class', 'is_active')
    search_fields = (
        'user__username', 'user__first_name', 'user__last_name',
        'variable_symbol',
        'parent__username', 'parent__last_name',
    )
    raw_id_fields = ('user', 'parent')
