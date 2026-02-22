"""
app/views/treasurer.py
──────────────────────
All treasurer-only views:
  • Overview dashboard
  • Create PaymentRequest
  • Log bank transfer (manual Transaction entry)
  • Quick-confirm a pending Transaction
  • Log / edit / delete a fund Expense
  • AJAX endpoint: unconfirmed requests for a student
"""

import json

from django.contrib import messages
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from ..forms import ExpenseForm, LogTransactionForm, PaymentRequestForm
from ..models import Expense, PaymentRequest, Transaction, User
from .utils import require_POST_or_405, treasurer_required, unconfirmed_requests_for_student


# ── Overview dashboard ────────────────────────────────────────────────────────

@treasurer_required
def treasurer_dashboard_view(req):
    """
    Treasurer-only overview:
    - Fund totals (collected, spent, balance)
    - All active payment requests with per-request progress
    - All students with per-student paid/missing/pending summary
    - Pending tab: student-submitted payments + completely-missing payments
    - Recent expenses
    """
    today = timezone.now().date()

    # ── Payment requests ──────────────────────────────────────────────────────
    all_requests = PaymentRequest.objects.prefetch_related(
        'transactions', 'assigned_to'
    ).order_by('-created_at')

    students = User.objects.filter(
        is_active=True
    ).order_by('last_name', 'first_name', 'username')
    student_count = students.count()

    for pr in all_requests:
        pr.confirmed_count = pr.transactions.filter(status=Transaction.Status.CONFIRMED).count()
        pr.pending_count   = pr.transactions.filter(status=Transaction.Status.PENDING).count()
        pr.expected_count  = student_count if pr.assign_to_all else pr.assigned_to.count()
        pr.missing_count   = max(0, pr.expected_count - pr.confirmed_count - pr.pending_count)
        pr.collected       = (
            pr.transactions.filter(status=Transaction.Status.CONFIRMED)
            .aggregate(s=Sum('amount'))['s'] or 0
        )
        pr.expected_total  = pr.amount * pr.expected_count
        pr.is_overdue      = bool(pr.due_date and pr.due_date < today)

    # ── Per-student summary ───────────────────────────────────────────────────
    confirmed_txs = (
        Transaction.objects.filter(status=Transaction.Status.CONFIRMED)
        .select_related('student', 'payment_request')
    )
    pending_txs = (
        Transaction.objects.filter(status=Transaction.Status.PENDING)
        .select_related('student', 'payment_request')
    )

    confirmed_map:   dict[int, set] = {}
    pending_map:     dict[int, set] = {}
    paid_amount_map: dict[int, int] = {}

    for tx in confirmed_txs:
        confirmed_map.setdefault(tx.student_id, set()).add(tx.payment_request_id)
        paid_amount_map[tx.student_id] = paid_amount_map.get(tx.student_id, 0) + int(tx.amount)

    for tx in pending_txs:
        pending_map.setdefault(tx.student_id, set()).add(tx.payment_request_id)

    student_rows = []
    for student in students:
        s_confirmed = confirmed_map.get(student.id, set())
        s_pending   = pending_map.get(student.id, set())

        assigned_ids = set(
            PaymentRequest.objects.filter(
                Q(assign_to_all=True) | Q(assigned_to=student)
            ).values_list('id', flat=True)
        )

        missing_ids = assigned_ids - s_confirmed - s_pending
        paid_total  = paid_amount_map.get(student.id, 0)
        owed_total  = (
            PaymentRequest.objects.filter(id__in=missing_ids | s_pending)
            .aggregate(s=Sum('amount'))['s'] or 0
        )

        student_rows.append({
            'student':       student,
            'paid_count':    len(s_confirmed),
            'pending_count': len(s_pending),
            'missing_count': len(missing_ids),
            'paid_total':    paid_total,
            'owed_total':    owed_total,
        })

    # ── Fund totals ───────────────────────────────────────────────────────────
    # (fund_collected / fund_spent / fund_balance are injected globally by the
    #  app.context_processors.fund_balance context processor, so we don't need
    #  to recompute them here.)

    # ── Pending tab: submitted + missing ─────────────────────────────────────
    confirmed_pairs = set(
        Transaction.objects.filter(status=Transaction.Status.CONFIRMED)
        .values_list('student_id', 'payment_request_id')
    )
    pending_pairs = {
        (tx.student_id, tx.payment_request_id): tx
        for tx in Transaction.objects.filter(status=Transaction.Status.PENDING)
        .select_related('student', 'payment_request')
    }

    submitted_items = []   # student sent payment, treasurer hasn't confirmed yet
    missing_items   = []   # no transaction at all

    for pr in all_requests:
        if pr.assign_to_all:
            assigned_students = list(students)
        else:
            assigned_students = list(pr.assigned_to.filter(is_active=True))

        for student in assigned_students:
            pair = (student.id, pr.id)
            if pair in confirmed_pairs:
                continue
            if pair in pending_pairs:
                submitted_items.append({
                    'student':         student,
                    'payment_request': pr,
                    'tx':              pending_pairs[pair],
                })
            else:
                missing_items.append({
                    'student':         student,
                    'payment_request': pr,
                })

    recent_expenses = Expense.objects.order_by('-spent_at')[:8]

    return render(req, 'treasurer_dashboard.html', {
        'all_requests':    all_requests,
        'student_rows':    student_rows,
        'submitted_items': submitted_items,
        'missing_items':   missing_items,
        'recent_expenses': recent_expenses,
        'today':           today,
    })


# ── Create Payment Request ────────────────────────────────────────────────────

@treasurer_required
def create_payment_request_view(req):
    """
    Treasurer-only form for creating a new PaymentRequest.

    - 'Assign to whole class' → assign_to_all=True, assigned_to cleared.
    - Otherwise → specific students stored in assigned_to.
    """
    if req.method == 'POST':
        form = PaymentRequestForm(req.POST)
        if form.is_valid():
            pr = form.save(commit=False)
            pr.created_by = req.user
            pr.save()
            if pr.assign_to_all:
                pr.assigned_to.clear()
            else:
                form.save_m2m()
            messages.success(req, f'Payment request "{pr.title}" created successfully.')
            return redirect('treasurer_dashboard')
        else:
            messages.error(req, 'Please fix the errors below.')
    else:
        form = PaymentRequestForm()

    students = User.objects.filter(
        is_active=True, is_treasurer=False
    ).order_by('last_name', 'first_name', 'username')

    return render(req, 'create_payment_request.html', {
        'form':     form,
        'students': students,
    })


# ── Log Bank Transfer ─────────────────────────────────────────────────────────

@treasurer_required
def log_transaction_view(req, pr_id=None, student_id=None):
    """
    Treasurer-only form for manually logging an incoming bank transfer.

    Entry points:
      • /treasurer/transactions/log/                       — blank form
      • /treasurer/transactions/log/<pr_id>/<student_id>/ — pre-filled shortcut

    On POST a Transaction is created with the chosen status.
    When status is CONFIRMED, any existing PENDING record for the same
    (student, request) pair is deleted (superseded).
    """
    students = User.objects.filter(
        is_active=True
    ).order_by('last_name', 'first_name', 'username')

    # Build { student_pk: [{id, title, amount}, …] } for the JS dropdown
    requests_by_student = {
        str(s.pk): [
            {'id': pr.id, 'title': str(pr), 'amount': str(pr.amount)}
            for pr in unconfirmed_requests_for_student(s)
        ]
        for s in students
    }

    # Resolve pre-fill values from URL params or ?student= query param
    initial     = {}
    pre_student = None

    if student_id:
        pre_student = User.objects.filter(
            pk=student_id, is_active=True
        ).first()
        if pre_student:
            initial['student'] = pre_student
    elif req.method == 'GET' and req.GET.get('student'):
        try:
            pre_student = User.objects.get(
                pk=int(req.GET['student']), is_active=True
            )
            initial['student'] = pre_student
        except (User.DoesNotExist, ValueError):
            pass

    if pr_id and pre_student:
        pre_pr = unconfirmed_requests_for_student(pre_student).filter(pk=pr_id).first()
        if pre_pr:
            initial['payment_request'] = pre_pr
            initial['amount']          = pre_pr.amount

    # If there's an existing PENDING tx for this pair, pre-fill amount & note
    pending_tx = None
    if pr_id and student_id:
        pending_tx = Transaction.objects.filter(
            payment_request_id=pr_id,
            student_id=student_id,
            status=Transaction.Status.PENDING,
        ).first()
        if pending_tx:
            initial.setdefault('amount', pending_tx.amount)
            initial.setdefault('note',   pending_tx.note)

    if req.method == 'POST':
        # Restrict the payment_request queryset to the posted student's assignments
        posted_student_id = req.POST.get('student')
        pr_qs = PaymentRequest.objects.none()
        if posted_student_id:
            try:
                posted_student = User.objects.get(pk=posted_student_id)
                # Use the full assigned set so validation can surface a clear error
                pr_qs = PaymentRequest.objects.filter(
                    Q(assign_to_all=True) | Q(assigned_to=posted_student)
                )
            except User.DoesNotExist:
                pr_qs = PaymentRequest.objects.all()

        form = LogTransactionForm(req.POST, pr_queryset=pr_qs)
        if form.is_valid():
            cd      = form.cleaned_data
            student = cd['student']
            pr      = cd['payment_request']
            status  = cd['status']
            now     = timezone.now()

            if status == Transaction.Status.CONFIRMED:
                Transaction.objects.filter(
                    student=student,
                    payment_request=pr,
                    status=Transaction.Status.PENDING,
                ).delete()

            Transaction.objects.create(
                student         = student,
                payment_request = pr,
                amount          = cd['amount'],
                status          = status,
                note            = cd.get('note', ''),
                paid_at         = cd['paid_at'],
                confirmed_at    = now if status == Transaction.Status.CONFIRMED else None,
            )

            status_label = dict(Transaction.Status.choices).get(status, status)
            messages.success(
                req,
                f'✅ Transfer logged: {student.get_full_name() or student.username} '
                f'→ "{pr.title}" ({cd["amount"]} CZK) — {status_label}.'
            )
            return redirect('treasurer_dashboard')
        else:
            messages.error(req, 'Please fix the errors below.')
    else:
        pr_qs = PaymentRequest.objects.all()
        if pre_student:
            pr_qs = PaymentRequest.objects.filter(
                Q(assign_to_all=True) | Q(assigned_to=pre_student)
            )
        form = LogTransactionForm(initial=initial, pr_queryset=pr_qs)

    return render(req, 'log_transaction.html', {
        'form':                form,
        'students':            students,
        'requests_by_student': json.dumps(requests_by_student),
        'pending_tx':          pending_tx,
    })


# ── Quick-confirm a pending Transaction ───────────────────────────────────────

@treasurer_required
@require_POST_or_405
def confirm_pending_view(req):
    """
    POST-only endpoint: confirm a pending Transaction directly from the
    treasurer dashboard without opening the full log form.

    Accepts:
      - 'tx_id'  (preferred) — the pk of an existing PENDING Transaction
      - 'student_id' + 'pr_id'  — fallback lookup if tx_id not provided
    """
    tx = None
    tx_id = req.POST.get('tx_id')
    if tx_id:
        try:
            tx = Transaction.objects.get(pk=int(tx_id), status=Transaction.Status.PENDING)
        except (Transaction.DoesNotExist, ValueError):
            tx = None

    if not tx:
        try:
            s_id  = int(req.POST.get('student_id') or 0)
            p_id  = int(req.POST.get('pr_id') or 0)
        except ValueError:
            s_id = p_id = 0

        if s_id and p_id:
            tx = Transaction.objects.filter(
                student_id=s_id,
                payment_request_id=p_id,
                status=Transaction.Status.PENDING,
            ).first()

    if not tx:
        messages.error(req, 'Pending transaction not found.')
        return redirect('treasurer_dashboard')

    now = timezone.now()
    Transaction.objects.create(
        student         = tx.student,
        payment_request = tx.payment_request,
        amount          = tx.amount,
        status          = Transaction.Status.CONFIRMED,
        note            = tx.note or '',
        paid_at         = tx.paid_at,
        confirmed_at    = now,
    )
    tx.delete()

    name = tx.student.get_full_name() or tx.student.username
    messages.success(req, f'✅ Confirmed payment for {name} → "{tx.payment_request.title}"')
    return redirect('treasurer_dashboard')


# ── AJAX: unconfirmed requests for one student ────────────────────────────────

@treasurer_required
def student_requests_json(req, student_id):
    """
    Returns a JSON array of unconfirmed PaymentRequests for *student_id*.
    Used by the JS on the log-transaction form to refresh the dropdown.
    """
    student = User.objects.filter(
        pk=student_id, is_active=True
    ).first()
    if not student:
        return JsonResponse([], safe=False)

    data = [
        {'id': pr.id, 'title': str(pr), 'amount': str(pr.amount)}
        for pr in unconfirmed_requests_for_student(student)
    ]
    return JsonResponse(data, safe=False)



# ── Log / Edit Expense ────────────────────────────────────────────────────────

@treasurer_required
def log_expense_view(req, expense_id=None):
    """
    Treasurer-only form to create or edit a class fund expense.

    GET  /treasurer/expenses/log/          — blank form (new expense)
    GET  /treasurer/expenses/log/<id>/     — pre-filled form (edit existing)
    POST                                   — validate, save, redirect to dashboard
    """
    instance = None
    if expense_id:
        try:
            instance = Expense.objects.get(pk=expense_id)
        except Expense.DoesNotExist:
            messages.error(req, 'Expense not found.')
            return redirect('treasurer_dashboard')

    if req.method == 'POST':
        form = ExpenseForm(req.POST, instance=instance)
        if form.is_valid():
            expense = form.save(commit=False)
            if not instance:
                expense.recorded_by = req.user
            expense.save()
            verb = 'updated' if instance else 'logged'
            messages.success(
                req,
                f'✅ Expense "{expense.title}" ({expense.amount} CZK) {verb} successfully.',
            )
            return redirect('treasurer_dashboard')
        else:
            messages.error(req, 'Please fix the errors below.')
    else:
        form = ExpenseForm(instance=instance)

    return render(req, 'log_expense.html', {
        'form':     form,
        'instance': instance,
    })


# ── Delete Expense ────────────────────────────────────────────────────────────

@treasurer_required
@require_POST_or_405
def delete_expense_view(req, expense_id):
    """POST-only: delete a single expense and redirect back to the dashboard."""
    try:
        expense = Expense.objects.get(pk=expense_id)
        title = expense.title
        expense.delete()
        messages.success(req, f'🗑 Expense "{title}" deleted.')
    except Expense.DoesNotExist:
        messages.error(req, 'Expense not found.')
    return redirect('treasurer_dashboard')
