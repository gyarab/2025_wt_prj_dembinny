"""
accounts/forms_admin.py
───────────────────────
Forms used exclusively by System Admin management views.

FundGroupForm        – create / edit a FundGroup (name + permission checkboxes).
ClassMembershipForm  – assign a treasurer to a class, choosing which FundGroup they belong to.
"""

from django import forms

from .models import ClassMembership, CustomUser, FundGroup, SchoolClass


class FundGroupForm(forms.ModelForm):
    """
    Create or edit a FundGroup for a specific class.
    The admin picks a name and ticks the permissions they want to grant.
    """

    class Meta:
        model  = FundGroup
        fields = (
            'school_class',
            'name',
            'can_log_expenses',
            'can_manage_payment_requests',
            'can_view_bank_account',
            'can_manage_students',
        )
        widgets = {
            'school_class': forms.Select(attrs={'class': 'form-select'}),
            'name':         forms.TextInput(attrs={'class': 'form-control',
                                                   'placeholder': 'e.g. Accountant, Auditor …'}),
        }
        labels = {
            'school_class':              'Class',
            'name':                      'Group name',
            'can_log_expenses':          'Log expenses',
            'can_manage_payment_requests': 'Manage payment requests',
            'can_view_bank_account':     'View / edit bank account',
            'can_manage_students':       'Manage students',
        }

    def __init__(self, *args, school_class=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['school_class'].queryset = SchoolClass.objects.all().order_by('name')
        if school_class:
            self.fields['school_class'].initial = school_class
            self.fields['school_class'].widget = forms.HiddenInput()


class ClassMembershipForm(forms.ModelForm):
    """
    Assign a treasurer-role user to a class and place them in a FundGroup.
    Only users whose global role is one of the three treasurer tiers are shown.
    When a school_class is pre-selected, the fund_group dropdown is filtered to
    groups that belong to that class.
    """

    class Meta:
        model  = ClassMembership
        fields = ('school_class', 'user', 'fund_group')
        widgets = {
            'school_class': forms.Select(attrs={'class': 'form-select'}),
            'user':         forms.Select(attrs={'class': 'form-select'}),
            'fund_group':   forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'school_class': 'Class',
            'user':         'Treasurer',
            'fund_group':   'Permission group',
        }

    def __init__(self, *args, school_class=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Only treasurer-role users may be assigned to class memberships
        self.fields['user'].queryset = CustomUser.objects.filter(
            role__in=[
                CustomUser.Role.TREASURER_FULL,
                CustomUser.Role.TREASURER_ACCOUNTANT,
                CustomUser.Role.TREASURER_BOOKKEEPER,
            ]
        ).order_by('last_name', 'first_name', 'username')

        self.fields['school_class'].queryset = SchoolClass.objects.all().order_by('name')
        self.fields['fund_group'].queryset   = FundGroup.objects.none()
        self.fields['fund_group'].required   = False
        self.fields['fund_group'].help_text  = (
            'Pick a permission group for this class. '
            'Leave blank to assign permissions later.'
        )

        # If a class is already known, filter groups to that class only
        if school_class:
            self.fields['school_class'].initial = school_class
            self.fields['fund_group'].queryset  = (
                FundGroup.objects.filter(school_class=school_class).order_by('name')
            )
        elif self.instance.pk and self.instance.school_class_id:
            self.fields['fund_group'].queryset = (
                FundGroup.objects.filter(school_class_id=self.instance.school_class_id)
                .order_by('name')
            )
        else:
            # Show all groups so the form is usable when class isn't pre-selected
            self.fields['fund_group'].queryset = FundGroup.objects.select_related('school_class').order_by(
                'school_class__name', 'name'
            )

    def clean(self):
        cleaned = super().clean()
        school_class = cleaned.get('school_class')
        fund_group   = cleaned.get('fund_group')
        if fund_group and school_class and fund_group.school_class != school_class:
            self.add_error(
                'fund_group',
                'The selected group does not belong to the chosen class.'
            )
        return cleaned
