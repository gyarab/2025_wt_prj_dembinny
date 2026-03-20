"""
importer/views.py
─────────────────
Three-step CSV import flow (System Admin only):

  Step 1  GET  /import/               – upload form
  Step 1  POST /import/               – parse CSV → preview
  Step 2  GET  /import/preview/       – review rows, edit inline, confirm or cancel
  Step 2  POST /import/preview/       – save inline edits back to session → re-render
  Step 2  POST /import/confirm/       – execute import → result
  Step 3  GET  /import/history/       – list past batches
  Step 3  GET  /import/history/<id>/  – single batch detail

Note: Only System Admins can import students.
"""

from django.contrib import messages
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import import_required
from accounts.models import FundGroup, SchoolClass

from .forms import StudentCSVUploadForm
from .models import ImportBatch
from .parser import IMPORTABLE_ROLES, ParsedRow, ParseResult, parse_csv_bytes, _derive_username
from .services import execute_import

# Session key used to carry parsed rows between upload and confirm steps
_SESSION_KEY = 'importer_preview'

# System-level role choices shown in the preview dropdown
_SYSTEM_ROLE_CHOICES = [
    ('student',              'Student'),
    ('treasurer_full',       'Treasurer (Full)'),
    ('treasurer_accountant', 'Treasurer (Accountant)'),
    ('treasurer_bookkeeper', 'Treasurer (Bookkeeper)'),
    ('parent',               'Parent'),
]


def _build_role_choices(school_class_id: int | None) -> list[tuple[str, str]]:
    """
    Return role choices for the preview dropdown.
    Includes system roles + any FundGroups created for the target class.
    """
    choices = list(_SYSTEM_ROLE_CHOICES)
    if school_class_id:
        for fg in FundGroup.objects.filter(school_class_id=school_class_id).order_by('name'):
            choices.append((fg.name, fg.name))
    return choices


def _build_group_role_choices(school_class_id: int | None) -> list[tuple[str, str]]:
    """Return (name, name) tuples for FundGroups of the given class."""
    if not school_class_id:
        return []
    return [
        (fg.name, fg.name)
        for fg in FundGroup.objects.filter(school_class_id=school_class_id).order_by('name')
    ]


def _get_extra_roles(school_class_id: int | None) -> set[str]:
    """Return the set of FundGroup names valid for *school_class_id*."""
    if not school_class_id:
        return set()
    return set(FundGroup.objects.filter(school_class_id=school_class_id).values_list('name', flat=True))


def _get_fund_groups_by_name(school_class_id: int | None) -> dict:
    """Return a {name: FundGroup} dict for the given class."""
    if not school_class_id:
        return {}
    return {fg.name: fg for fg in FundGroup.objects.filter(school_class_id=school_class_id)}


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
                extra_roles = _get_extra_roles(school_class.pk)
                parse_result = parse_csv_bytes(csv_file.read(), extra_roles=extra_roles)
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
                        'email':             r.email,
                        'username':          r.username,
                        'role':              r.role,
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


# ── Step 2a – Preview (GET + inline-edit POST) ───────────────────────────────

@import_required
def preview_view(req):
    """
    GET  → show editable table of all parsed rows.
    POST → save inline edits (first_name, last_name, email, role, variable_symbol,
           parent_email) back into the session, then re-render.
    """
    session_data = req.session.get(_SESSION_KEY)
    if not session_data:
        messages.warning(req, 'No import in progress. Please upload a CSV first.')
        return redirect('importer:upload')

    school_class = get_object_or_404(SchoolClass, pk=session_data['school_class_id'])
    extra_roles  = _get_extra_roles(school_class.pk)
    valid_roles  = IMPORTABLE_ROLES | {r.lower() for r in extra_roles}
    system_role_choices = list(_SYSTEM_ROLE_CHOICES)
    group_role_choices  = _build_group_role_choices(school_class.pk)

    if req.method == 'POST':
        rows = session_data['rows']
        edit_errors = []

        for rd in rows:
            idx = str(rd['row_number'])
            # Apply edits from POST data; fall back to existing value if field absent
            rd['first_name']   = req.POST.get(f'first_name_{idx}',   rd['first_name']).strip()
            rd['last_name']    = req.POST.get(f'last_name_{idx}',    rd['last_name']).strip()
            rd['email']        = req.POST.get(f'email_{idx}',        rd['email']).strip()
            rd['role']         = req.POST.get(f'role_{idx}',         rd['role']).strip()
            rd['variable_symbol'] = req.POST.get(f'vs_{idx}',        rd['variable_symbol']).strip()
            rd['parent_email'] = req.POST.get(f'parent_email_{idx}', rd['parent_email']).strip()

            # Re-derive username from edited identity fields (unless explicitly set)
            if not rd['username']:
                if rd['email'] and '@' in rd['email']:
                    rd['username'] = rd['email'].split('@')[0][:30]
                elif rd['first_name'] and rd['last_name']:
                    rd['username'] = _derive_username(rd['first_name'], rd['last_name'])

            # Re-validate the edited row
            errs = []
            has_name     = bool(rd['first_name'] and rd['last_name'])
            has_identity = bool(rd['username'] or rd['email'] or has_name)
            if not has_identity:
                errs.append(
                    'Provide at least one identifier: username, email, '
                    'or both first_name and last_name.'
                )
            if rd['email'] and '@' not in rd['email']:
                errs.append(f'email "{rd["email"]}" is not a valid email address.')
            if rd['role'].lower() not in valid_roles:
                errs.append(f'role "{rd["role"]}" is not valid.')
            vs = rd['variable_symbol']
            if vs:
                if not vs.isdigit():
                    errs.append(f'variable_symbol "{vs}" must be digits only.')
                elif len(vs) > 10:
                    errs.append(f'variable_symbol "{vs}" must be at most 10 digits.')
            if rd['parent_email'] and '@' not in rd['parent_email']:
                errs.append(f'parent_email "{rd["parent_email"]}" is not a valid email.')
            rd['errors'] = errs
            if errs:
                edit_errors.append(rd['row_number'])

        # Persist updated rows back into session
        session_data['rows'] = rows
        req.session[_SESSION_KEY] = session_data
        req.session.modified = True

        if edit_errors:
            messages.warning(req, f'Rows {edit_errors} still have errors — fix them or they will be skipped.')
        else:
            messages.success(req, 'Edits saved.')

    parse_result = _hydrate(session_data)
    return render(req, 'importer/preview.html', {
        'parse_result':       parse_result,
        'school_class':       school_class,
        'filename':           session_data.get('filename', ''),
        'system_role_choices': system_role_choices,
        'group_role_choices':  group_role_choices,
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
    fund_groups_by_name = _get_fund_groups_by_name(school_class.pk)

    batch, imported_students = execute_import(
        parse_result=parse_result,
        school_class=school_class,
        uploaded_by=req.user,
        filename=session_data.get('filename', ''),
        fund_groups_by_name=fund_groups_by_name,
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
    """List all past import batches (system-wide, visible to System Admins only)."""
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
            email=d.get('email', ''),
            username=d['username'],
            role=d.get('role', 'student'),
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
