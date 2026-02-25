"""
importer/views.py
─────────────────
Three-step CSV import flow (System Admin only):

  Step 1  GET  /import/               – upload form
  Step 1  POST /import/               – parse CSV → preview
  Step 2  GET  /import/preview/       – review rows, confirm or cancel
  Step 2  POST /import/confirm/       – execute import → result
  Step 3  GET  /import/history/       – list past batches
  Step 3  GET  /import/history/<id>/  – single batch detail

Note: Only System Admins can import students.  Treasurers (all tiers)
      are denied at the decorator level.
"""

from django.contrib import messages
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import import_required
from accounts.models import SchoolClass

from .forms import StudentCSVUploadForm
from .models import ImportBatch
from .parser import ParsedRow, ParseResult, parse_csv_bytes
from .services import execute_import

# Session key used to carry parsed rows between upload and confirm steps
_SESSION_KEY = 'importer_preview'


# ── Step 1 – Upload & parse ───────────────────────────────────────────────────

@import_required
def upload_view(req):
    """
    GET  → show the upload form.
    POST → read + parse the CSV, store the result in the session, redirect to
           the preview page.
    """
    if req.method == 'POST':
        form = StudentCSVUploadForm(req.POST, req.FILES)
        if form.is_valid():
            school_class: SchoolClass = form.cleaned_data['school_class']
            csv_file = req.FILES['csv_file']

            try:
                parse_result = parse_csv_bytes(csv_file.read())
            except ValueError as exc:
                messages.error(req, str(exc))
                return render(req, 'importer/upload.html', {'form': form})

            if parse_result.field_errors:
                for err in parse_result.field_errors:
                    messages.error(req, err)
                return render(req, 'importer/upload.html', {'form': form})

            # Stash serialisable data in the session
            req.session[_SESSION_KEY] = {
                'school_class_id': school_class.pk,
                'filename':        csv_file.name,
                'rows': [
                    {
                        'row_number':        r.row_number,
                        'first_name':        r.first_name,
                        'last_name':         r.last_name,
                        'username':          r.username,
                        'parent_email':      r.parent_email,
                        'parent_first_name': r.parent_first_name,
                        'parent_last_name':  r.parent_last_name,
                        'variable_symbol':   r.variable_symbol,
                        'password':          r.password,
                        'errors':            r.errors,
                    }
                    for r in parse_result.rows
                ],
            }
            return redirect('importer:preview')
    else:
        form = StudentCSVUploadForm()

    return render(req, 'importer/upload.html', {'form': form})


# ── Step 2a – Preview ─────────────────────────────────────────────────────────

@import_required
def preview_view(req):
    """
    Show a table of all parsed rows so the treasurer can review before
    anything is written to the database.
    """
    session_data = req.session.get(_SESSION_KEY)
    if not session_data:
        messages.warning(req, 'No import in progress. Please upload a CSV first.')
        return redirect('importer:upload')

    school_class = get_object_or_404(SchoolClass, pk=session_data['school_class_id'])
    parse_result = _hydrate(session_data)

    return render(req, 'importer/preview.html', {
        'parse_result': parse_result,
        'school_class': school_class,
        'filename':     session_data.get('filename', ''),
    })


# ── Step 2b – Confirm & execute ───────────────────────────────────────────────

@import_required
def confirm_view(req):
    """
    POST-only.  Execute the import and render the result page.
    """
    if req.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session_data = req.session.pop(_SESSION_KEY, None)
    if not session_data:
        messages.warning(req, 'Import session expired. Please upload the CSV again.')
        return redirect('importer:upload')

    school_class = get_object_or_404(SchoolClass, pk=session_data['school_class_id'])
    parse_result = _hydrate(session_data)

    batch, imported_students = execute_import(
        parse_result=parse_result,
        school_class=school_class,
        uploaded_by=req.user,
        filename=session_data.get('filename', ''),
    )

    return render(req, 'importer/result.html', {
        'batch':             batch,
        'imported_students': imported_students,
        'school_class':      school_class,
    })


# ── Step 3 – Past batch detail ────────────────────────────────────────────────

@import_required
def batch_detail_view(req, batch_id: int):
    """Re-view the audit log of a past import batch."""
    batch = get_object_or_404(
        ImportBatch.objects.prefetch_related('rows'),
        pk=batch_id,
    )
    return render(req, 'importer/batch_detail.html', {'batch': batch})


@import_required
def batch_list_view(req):
    """List all past import batches for this treasurer's classes."""
    batches = ImportBatch.objects.select_related('school_class', 'uploaded_by').all()
    return render(req, 'importer/batch_list.html', {'batches': batches})


# ── Internal helpers ──────────────────────────────────────────────────────────

def _hydrate(session_data: dict) -> ParseResult:
    """Re-build a ParseResult from serialised session data."""
    rows = [
        ParsedRow(
            row_number=d['row_number'],
            first_name=d['first_name'],
            last_name=d['last_name'],
            username=d['username'],
            parent_email=d['parent_email'],
            parent_first_name=d['parent_first_name'],
            parent_last_name=d['parent_last_name'],
            variable_symbol=d['variable_symbol'],
            password=d['password'],
            errors=d['errors'],
        )
        for d in session_data['rows']
    ]
    return ParseResult(rows=rows)
