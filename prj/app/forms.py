from django import forms
from django.db.models import Q
from django.utils import timezone

from .models import Expense, PaymentRequest, Transaction, User


class PaymentRequestForm(forms.ModelForm):
    """
    Form for the treasurer to create a new PaymentRequest.

    Key behaviour:
    - `assign_to_all` checkbox:  when checked the `assigned_to` multi-select
      is ignored and the request is sent to every active student.
    - When `assign_to_all` is unchecked at least one student must be chosen.
    """

    # Show all active accounts in the student picker (including treasurer)
    assigned_to = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True)
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


class LogTransactionForm(forms.Form):
    """
    Treasurer form to manually log an incoming bank transfer.

    Flow:
      1. Select the student who sent the money.
      2. The JS on the page (and the view's AJAX endpoint) filters the
         payment_request dropdown to only the requests that student still owes.
      3. Amount pre-fills from the selected request but can be overridden.
      4. On save the Transaction is created with status=CONFIRMED immediately
         (the treasurer has already verified the bank transfer).
    """

    student = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True)
                             .order_by('last_name', 'first_name', 'username'),
        label='Student',
        empty_label='— select student —',
    )

    payment_request = forms.ModelChoiceField(
        queryset=PaymentRequest.objects.all(),
        label='Payment Request',
        empty_label='— select payment request —',
        help_text='Only requests the student still owes are listed.',
    )

    amount = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        min_value=0,
        label='Amount received (CZK)',
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
        help_text='Pre-filled from the payment request; adjust if the student paid a different amount.',
    )

    paid_at = forms.DateTimeField(
        label='Transfer date & time',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        input_formats=['%Y-%m-%dT%H:%M'],
        help_text='When did the money arrive in the bank account?',
    )

    note = forms.CharField(
        required=False,
        label='Note (optional)',
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Bank reference, VS/SS, any remark…'}),
    )

    status = forms.ChoiceField(
        choices=Transaction.Status.choices,
        initial=Transaction.Status.CONFIRMED,
        label='Transaction status',
        help_text=(
            'Confirmed — money verified in bank account. '
            'Pending — submitted by student, not yet verified. '
            'Rejected — payment was incorrect or refused.'
        ),
    )

    def __init__(self, *args, **kwargs):
        # Allow the view to pre-restrict the payment_request queryset
        pr_queryset = kwargs.pop('pr_queryset', None)
        super().__init__(*args, **kwargs)
        if pr_queryset is not None:
            self.fields['payment_request'].queryset = pr_queryset
        # Default paid_at to now (formatted for datetime-local input)
        if not self.data.get('paid_at'):
            self.fields['paid_at'].initial = timezone.localtime().strftime('%Y-%m-%dT%H:%M')

    def clean(self):
        cleaned = super().clean()
        student         = cleaned.get('student')
        payment_request = cleaned.get('payment_request')
        status          = cleaned.get('status')

        if student and payment_request:
            # Guard: student must actually be assigned to this request
            assigned = PaymentRequest.objects.filter(
                Q(assign_to_all=True) | Q(assigned_to=student),
                id=payment_request.id,
            ).exists()
            if not assigned:
                raise forms.ValidationError(
                    f'{student} is not assigned to "{payment_request.title}".'
                )

            # Prevent duplicate confirmed transactions for the same (student, request)
            if status == Transaction.Status.CONFIRMED:
                already_confirmed = Transaction.objects.filter(
                    student=student,
                    payment_request=payment_request,
                    status=Transaction.Status.CONFIRMED,
                ).exists()
                if already_confirmed:
                    raise forms.ValidationError(
                        f'A confirmed transaction already exists for {student} '
                        f'→ "{payment_request.title}". No duplicate created.'
                    )

        return cleaned


class ExpenseForm(forms.ModelForm):
    """
    Treasurer form to log a class fund expense (e.g. 'Bought pizza: 400 CZK').
    """

    class Meta:
        model  = Expense
        fields = [
            'title',
            'description',
            'amount',
            'category',
            'spent_at',
            'is_published',
        ]
        widgets = {
            'title':       forms.TextInput(attrs={
                'placeholder': 'e.g. Bought pizza for class party',
                'class': 'form-control-input',
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Optional details (receipt number, shop, occasion…)',
                'class': 'form-control-input',
            }),
            'amount':      forms.NumberInput(attrs={
                'step': '0.01', 'min': '0', 'placeholder': '0.00',
                'class': 'form-control-input',
            }),
            'category':    forms.Select(attrs={'class': 'form-control-input'}),
            'spent_at':    forms.DateInput(attrs={'type': 'date', 'class': 'form-control-input'}, format='%Y-%m-%d'),
            'is_published': forms.CheckboxInput(),
        }
        labels = {
            'title':        'What was bought / spent on?',
            'description':  'Details (optional)',
            'amount':       'Amount (CZK)',
            'category':     'Category',
            'spent_at':     'Date of expense',
            'is_published': 'Visible to all students',
        }
        help_texts = {
            'is_published': 'Uncheck to keep this expense hidden from students for now.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['spent_at'].input_formats = ['%Y-%m-%d']
        # Default to today
        if not self.data.get('spent_at') and not self.instance.pk:
            self.fields['spent_at'].initial = timezone.localdate().strftime('%Y-%m-%d')
