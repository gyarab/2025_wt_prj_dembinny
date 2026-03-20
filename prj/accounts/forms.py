"""
accounts/forms.py
─────────────────
Forms for account management and CSV bulk-import of students.
"""

import csv
import io

from django import forms

from .models import CustomUser, SchoolClass, StudentProfile


class StudentCSVImportForm(forms.Form):
    """
    Phase-1 upload form: choose a class and upload a CSV file.

    The form validates the file is well-formed and returns the decoded rows
    via ``cleaned_data['csv_file']`` so the view can pass them to
    ``accounts.services.parse_student_csv()`` for a preview.

    CSV format
    ──────────
    Required columns (header row must be present):
        first_name, last_name

    Optional columns:
        username           – derived from first_name + last_name if absent
        variable_symbol    – auto-generated from SchoolClass.vs_prefix if absent
        parent_email       – creates / links a Parent user
        parent_first_name
        parent_last_name
        password           – set once; random 12-char password used if absent
    """

    school_class = forms.ModelChoiceField(
        queryset=SchoolClass.objects.all(),
        label='Target class',
        help_text='All students in the CSV will be enrolled in this class.',
    )
    csv_file = forms.FileField(
        label='CSV file',
        help_text=(
            'Required columns: <strong>first_name, last_name</strong>. '
            'Optional: username, variable_symbol, '
            'parent_email, parent_first_name, parent_last_name, password. '
            'Header row required. UTF-8 or UTF-8-BOM encoding.'
        ),
    )

    def clean_csv_file(self):
        f = self.cleaned_data['csv_file']

        # Enforce a 1 MB size limit
        if f.size > 1_048_576:
            raise forms.ValidationError('File is too large (max 1 MB).')

        try:
            text = f.read().decode('utf-8-sig')      # handle Excel BOM
        except UnicodeDecodeError:
            raise forms.ValidationError('File must be UTF-8 encoded.')

        reader = csv.DictReader(io.StringIO(text))
        fieldnames = [n.strip().lower() for n in (reader.fieldnames or [])]

        required = {'first_name', 'last_name'}
        missing = required - set(fieldnames)
        if missing:
            raise forms.ValidationError(
                f'CSV is missing required columns: {", ".join(sorted(missing))}'
            )

        rows = [
            {k.strip().lower(): (v or '').strip() for k, v in row.items()}
            for row in reader
        ]
        if not rows:
            raise forms.ValidationError('The CSV file contains no data rows.')

        return rows

