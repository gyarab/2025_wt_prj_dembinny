"""
accounts/forms_admin.py
───────────────────────
Forms used exclusively by System Admin management views.

ClassMembershipForm  – create / edit a ClassMembership (assign a treasurer to
                        a class with a specific tier).
"""

from django import forms

from .models import ClassMembership, CustomUser, SchoolClass


class ClassMembershipForm(forms.ModelForm):
    """
    Lets an admin assign a treasurer-role user to a class with a chosen tier.
    Only users whose role is one of the three treasurer tiers are shown.
    """

    class Meta:
        model  = ClassMembership
        fields = ('school_class', 'user', 'tier')
        widgets = {
            'school_class': forms.Select(attrs={'class': 'form-select'}),
            'user':         forms.Select(attrs={'class': 'form-select'}),
            'tier':         forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only treasurer-role users may be assigned to class memberships
        self.fields['user'].queryset = CustomUser.objects.filter(
            role__in=[
                CustomUser.Role.TREASURER_FULL,
                CustomUser.Role.TREASURER_ACCOUNTANT,
                CustomUser.Role.TREASURER_BOOKKEEPER,
            ]
        ).order_by('last_name', 'first_name', 'username')
        self.fields['user'].label = 'Treasurer'
        self.fields['school_class'].queryset = SchoolClass.objects.all().order_by('name')
        self.fields['tier'].help_text = (
            '<strong>Full</strong> – all actions &nbsp;|&nbsp; '
            '<strong>Accountant</strong> – expenses + payment requests &nbsp;|&nbsp; '
            '<strong>Bookkeeper</strong> – expenses only'
        )
