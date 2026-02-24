"""
accounts/admin.py
─────────────────
Admin registrations for CustomUser, SchoolClass, and StudentProfile.

When a CustomUser is saved via the admin the user is automatically placed in
the Django Group that corresponds to their role (e.g. role=TREASURER → group
"Class Treasurer / Teacher").  This lets you assign model-level permissions to
groups and have them reflected automatically.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group

from .models import CustomUser, SchoolClass, StudentProfile

# Mapping from role value → group name (must match apps.py _create_default_groups)
ROLE_GROUP_MAP = {
    CustomUser.Role.SYSTEM_ADMIN: 'System Admin',
    CustomUser.Role.TREASURER:    'Class Treasurer / Teacher',
    CustomUser.Role.STUDENT:      'Student',
    CustomUser.Role.PARENT:       'Parent',
}


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    """
    Extends the default UserAdmin to surface the role field.
    On every save the user's group membership is synced to match their role.
    """

    list_display  = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff')
    list_filter   = BaseUserAdmin.list_filter + ('role',)
    search_fields = ('username', 'first_name', 'last_name', 'email')

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Class Fund Role', {'fields': ('role', 'hide_fund_balance')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Class Fund Role', {'fields': ('role', 'hide_fund_balance')}),
    )

    def save_model(self, request, obj, form, change):
        """Persist the user then sync their Django group membership."""
        super().save_model(request, obj, form, change)
        _sync_user_group(obj)


def _sync_user_group(user: CustomUser) -> None:
    """Remove user from all role groups then add them to the one matching their role."""
    role_groups = Group.objects.filter(name__in=ROLE_GROUP_MAP.values())
    user.groups.remove(*role_groups)
    target_name = ROLE_GROUP_MAP.get(user.role)
    if target_name:
        group, _ = Group.objects.get_or_create(name=target_name)
        user.groups.add(group)


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
