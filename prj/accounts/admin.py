"""
accounts/admin.py
─────────────────
Admin registrations for CustomUser, SchoolClass, ClassMembership, and StudentProfile.

When a CustomUser is saved via the admin the user is automatically placed in
the Django Group that corresponds to their role.  This lets you assign
model-level permissions to groups and have them reflected automatically.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group

from .models import ClassMembership, CustomUser, FundGroup, SchoolClass, StudentProfile

# Mapping from role value → group name (must match apps.py _create_default_groups)
ROLE_GROUP_MAP = {
    CustomUser.Role.SYSTEM_ADMIN:         'System Admin',
    CustomUser.Role.TREASURER_FULL:       'Treasurer – Full',
    CustomUser.Role.TREASURER_ACCOUNTANT: 'Treasurer – Accountant',
    CustomUser.Role.TREASURER_BOOKKEEPER: 'Treasurer – Bookkeeper',
    CustomUser.Role.STUDENT:              'Student',
    CustomUser.Role.PARENT:               'Parent',
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


class ClassMembershipInline(admin.TabularInline):
    model = ClassMembership
    extra = 1
    raw_id_fields = ('user',)
    fields = ('user', 'fund_group', 'joined_at')
    readonly_fields = ('joined_at',)


class FundGroupInline(admin.TabularInline):
    model = FundGroup
    extra = 1
    fields = ('name', 'can_log_expenses', 'can_manage_payment_requests',
              'can_view_bank_account', 'can_manage_students')


@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    list_display  = ('name', 'teacher', 'school_year', 'vs_prefix', 'member_count', 'created_at')
    list_filter   = ('school_year',)
    search_fields = ('name', 'teacher__username', 'teacher__last_name')
    raw_id_fields = ('teacher',)
    fields        = ('name', 'teacher', 'school_year', 'vs_prefix')
    inlines       = [FundGroupInline, ClassMembershipInline]

    @admin.display(description='Members')
    def member_count(self, obj):
        return obj.memberships.count()


@admin.register(FundGroup)
class FundGroupAdmin(admin.ModelAdmin):
    list_display  = ('name', 'school_class', 'can_log_expenses', 'can_manage_payment_requests',
                     'can_view_bank_account', 'can_manage_students', 'member_count')
    list_filter   = ('school_class',)
    search_fields = ('name', 'school_class__name')
    fields        = ('school_class', 'name', 'can_log_expenses', 'can_manage_payment_requests',
                     'can_view_bank_account', 'can_manage_students')

    @admin.display(description='Members')
    def member_count(self, obj):
        return obj.memberships.count()


@admin.register(ClassMembership)
class ClassMembershipAdmin(admin.ModelAdmin):
    list_display  = ('school_class', 'user', 'fund_group', 'joined_at')
    list_filter   = ('fund_group__school_class',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'school_class__name')
    raw_id_fields = ('user',)
    readonly_fields = ('joined_at',)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display  = ('user', 'school_class', 'variable_symbol', 'parent', 'is_active')
    list_filter   = ('school_class', 'is_active')
    search_fields = (
        'user__username', 'user__first_name', 'user__last_name',
        'variable_symbol',
        'parent__username', 'parent__last_name',
    )
    raw_id_fields = ('user', 'parent')
    readonly_fields = ('variable_symbol',)
    actions = ['regenerate_variable_symbols']

    @admin.action(description='🔄 Regenerate Variable Symbol for selected students')
    def regenerate_variable_symbols(self, request, queryset):
        count = 0
        for profile in queryset:
            profile.regenerate_vs()
            count += 1
        self.message_user(request, f'Regenerated VS for {count} student(s).')
