from django import forms
from django.utils import timezone

from .models import PaymentRequest, User


class PaymentRequestForm(forms.ModelForm):
    """
    Form for the treasurer to create a new PaymentRequest.

    Key behaviour:
    - `assign_to_all` checkbox:  when checked the `assigned_to` multi-select
      is ignored and the request is sent to every active student.
    - When `assign_to_all` is unchecked at least one student must be chosen.
    """

    # Only show active, non-treasurer accounts in the student picker
    assigned_to = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True, is_treasurer=False)
                             .order_by('last_name', 'first_name', 'username'),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Assign to specific students",
        help_text="Checked when 'Assign to whole class' is unchecked.",
    )

    class Meta:
        model  = PaymentRequest
        fields = [
            'title',
            'description',
            'amount',
            'due_date',
            'variable_symbol',
            'specific_symbol',
            'assign_to_all',
            'assigned_to',
        ]
        widgets = {
            'title':           forms.TextInput(attrs={'placeholder': 'e.g. School trip deposit'}),
            'description':     forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional details…'}),
            'amount':          forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'due_date':        forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'variable_symbol': forms.TextInput(attrs={'placeholder': 'Up to 10 digits'}),
            'specific_symbol': forms.TextInput(attrs={'placeholder': 'Up to 10 digits'}),
        }
        labels = {
            'title':           'Title',
            'description':     'Description (optional)',
            'amount':          'Amount per student (CZK)',
            'due_date':        'Due date (optional)',
            'variable_symbol': 'Variable Symbol (VS)',
            'specific_symbol': 'Specific Symbol (SS)',
            'assign_to_all':   'Assign to whole class',
        }
        help_texts = {
            'amount':          'Each assigned student will owe this amount.',
            'variable_symbol': 'Up to 10 digits — identifies the payment purpose.',
            'specific_symbol': 'Up to 10 digits — optionally identifies the payer.',
            'assign_to_all':   'When checked every active student is included; the list below is ignored.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-select today as a sensible default for due_date display
        self.fields['due_date'].input_formats = ['%Y-%m-%d']

    def clean(self):
        cleaned = super().clean()
        assign_to_all = cleaned.get('assign_to_all')
        assigned_to   = cleaned.get('assigned_to')

        if not assign_to_all and not assigned_to:
            raise forms.ValidationError(
                "Please either tick 'Assign to whole class' or select at least one student."
            )

        return cleaned
