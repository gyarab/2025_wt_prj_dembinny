"""
finances/forms.py
─────────────────
Forms for the treasurer to manage payment requests, log transactions,
and record expenses.
"""

from django import forms
from django.db.models import Q
from django.utils import timezone

from .models import Expense, PaymentRequest, Transaction


class PaymentRequestForm(forms.ModelForm):
    """
    Form for the treasurer to create a new PaymentRequest.
    """

    class Meta:
        model  = PaymentRequest
        fields = [
            'title', 'description', 'amount', 'due_date',
            'variable_symbol', 'specific_symbol',
            'assign_to_all', 'assigned_to',
        ]
        widgets = {
            'title':           forms.TextInput(attrs={'placeholder': 'e.g. School trip deposit', 'class': 'form-control'}),
            'description':     forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional details…', 'class': 'form-control'}),
            'amount':          forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': '0.00', 'class': 'form-control'}),
            'due_date':        forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'variable_symbol': forms.TextInput(attrs={'placeholder': 'Up to 10 digits', 'class': 'form-control'}),
            'specific_symbol': forms.TextInput(attrs={'placeholder': 'Up to 10 digits', 'class': 'form-control'}),
            'assigned_to':     forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['due_date'].input_formats = ['%Y-%m-%d']
        self.fields['assigned_to'].required = False

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('assign_to_all') and not cleaned.get('assigned_to'):
            raise forms.ValidationError(
                "Please either tick 'Assign to whole class' or select at least one student."
            )
        return cleaned


class LogTransactionForm(forms.Form):
    """
    Treasurer form to manually log an incoming bank transfer.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    student = forms.ModelChoiceField(
        queryset=None,   # set in __init__
        label='Student',
        empty_label='— select student —',
    )
    payment_request = forms.ModelChoiceField(
        queryset=PaymentRequest.objects.all(),
        label='Payment Request',
        empty_label='— select payment request —',
    )
    amount = forms.DecimalField(
        max_digits=8, decimal_places=2, min_value=0,
        label='Amount received (CZK)',
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
    )
    paid_at = forms.DateTimeField(
        label='Transfer date & time',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        input_formats=['%Y-%m-%dT%H:%M'],
    )
    note = forms.CharField(
        required=False, label='Note (optional)',
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Bank reference, VS/SS, any remark…'}),
    )
    status = forms.ChoiceField(
        choices=Transaction.Status.choices,
        initial=Transaction.Status.CONFIRMED,
        label='Transaction status',
    )

    def __init__(self, *args, **kwargs):
        pr_queryset = kwargs.pop('pr_queryset', None)
        super().__init__(*args, **kwargs)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.fields['student'].queryset = (
            User.objects.filter(is_active=True)
            .order_by('last_name', 'first_name', 'username')
        )
        if pr_queryset is not None:
            self.fields['payment_request'].queryset = pr_queryset
        if not self.data.get('paid_at'):
            self.fields['paid_at'].initial = timezone.localtime().strftime('%Y-%m-%dT%H:%M')

    def clean(self):
        cleaned = super().clean()
        student = cleaned.get('student')
        pr      = cleaned.get('payment_request')
        status  = cleaned.get('status')

        if student and pr:
            assigned = PaymentRequest.objects.filter(
                Q(assign_to_all=True) | Q(assigned_to=student),
                id=pr.id,
            ).exists()
            if not assigned:
                raise forms.ValidationError(
                    f'{student} is not assigned to "{pr.title}".'
                )
            if status == Transaction.Status.CONFIRMED:
                if Transaction.objects.filter(
                    student=student, payment_request=pr,
                    status=Transaction.Status.CONFIRMED,
                ).exists():
                    raise forms.ValidationError(
                        f'A confirmed transaction already exists for {student} → "{pr.title}".'
                    )
        return cleaned


class ExpenseForm(forms.ModelForm):
    """Treasurer form to log a class fund expense."""

    class Meta:
        model  = Expense
        fields = ['title', 'description', 'amount', 'category', 'spent_at', 'is_published']
        widgets = {
            'title':        forms.TextInput(attrs={'class': 'form-control'}),
            'description':  forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'amount':       forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': 'form-control'}),
            'category':     forms.Select(attrs={'class': 'form-select'}),
            'spent_at':     forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['spent_at'].input_formats = ['%Y-%m-%d']
        if not self.data.get('spent_at') and not self.instance.pk:
            self.fields['spent_at'].initial = timezone.localdate().strftime('%Y-%m-%d')
