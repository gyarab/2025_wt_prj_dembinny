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
    Upload a CSV file to bulk-create StudentProfile records for a class.

    Expected CSV columns (header row required):
        username, first_name, last_name[, variable_symbol, parent_email, parent_first_name, parent_last_name]

    ``variable_symbol`` is **optional** – if omitted or empty the VS will be
    auto-generated from the class VS prefix (see SchoolClass.vs_prefix and
    StudentProfile.save()).

    For each row the importer will:
    1. Get-or-create a CustomUser (student, role=STUDENT) using username.
    2. Optionally get-or-create a parent CustomUser (role=PARENT) using parent_email.
    3. Create a StudentProfile linking the student user to the chosen class.
    """

    school_class = forms.ModelChoiceField(
        queryset=SchoolClass.objects.all(),
        label='Target class',
        help_text='All imported students will be placed into this class.',
    )
    csv_file = forms.FileField(
        label='CSV file',
        help_text=(
            'Required columns: username, first_name, last_name. '
            'Optional columns: variable_symbol (auto-generated if absent), '
            'parent_email, parent_first_name, parent_last_name.'
        ),
    )

    def clean_csv_file(self):
        f = self.cleaned_data['csv_file']
        try:
            text = f.read().decode('utf-8-sig')   # handle Excel BOM
            reader = csv.DictReader(io.StringIO(text))
            required = {'username', 'first_name', 'last_name'}
            if not required.issubset(set(reader.fieldnames or [])):
                raise forms.ValidationError(
                    f'CSV is missing required columns: {required - set(reader.fieldnames or [])}'
                )
            rows = list(reader)
            if not rows:
                raise forms.ValidationError('The CSV file is empty.')
            return rows
        except UnicodeDecodeError:
            raise forms.ValidationError('File must be UTF-8 encoded.')

