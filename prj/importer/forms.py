"""
importer/forms.py
─────────────────
Upload form for the CSV student import.
"""

from django import forms

from accounts.models import SchoolClass


class StudentCSVUploadForm(forms.Form):
    """
    Phase-1 form: choose a target class and upload a CSV file.

    The file is decoded and validated in the view; cleaned rows are stashed
    in the session for the confirmation step.
    """

    school_class = forms.ModelChoiceField(
        queryset=SchoolClass.objects.all(),
        label='Target class',
        help_text='Every student in the CSV will be enrolled in this class.',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    csv_file = forms.FileField(
        label='CSV file',
        help_text=(
            'Required columns: <strong>first_name</strong>, <strong>last_name</strong>. '
            'Optional: username, variable_symbol, '
            'parent_email, parent_first_name, parent_last_name, password. '
            'Header row is required. UTF-8 or UTF-8-BOM encoding.'
        ),
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.csv,text/csv'}),
    )

    def clean_csv_file(self):
        f = self.cleaned_data['csv_file']
        if f.size > 2 * 1024 * 1024:   # 2 MB hard limit
            raise forms.ValidationError('File is too large (max 2 MB).')
        return f
