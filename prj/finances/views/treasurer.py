"""
finances/views/treasurer.py
────────────────────────────
All treasurer-only views: overview dashboard, create PaymentRequest,
log/confirm Transactions, log/edit/delete Expenses, and the AJAX endpoint.

SECURITY: Every queryset is scoped to the treasurer's own SchoolClass via
get_treasurer_class(req.user).  A treasurer cannot read or modify data that
belongs to another class.
"""

import json

from django.contrib import messages
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from ..forms import ExpenseForm, LogTransactionForm, PaymentRequestForm
from ..models import Expense, PaymentRequest, Transaction
from .utils import (
    get_class_bank_account,
    get_class_payment_requests,
    get_class_students,
    get_treasurer_class,
    require_POST_or_405,
    treasurer_required,
    unconfirmed_requests_for_student,
)


# ── Overview dashboard ────────────────────────────────────────────────────────

@treasurer_required
def treasurer_dashboard_view(req):
    """
    Treasurer-only overview — all data scoped to the treasurer's SchoolClass:
    - Fund totals (via context processor, also class-scoped)
    - Payment requests belonging to this class
    - Per-student paid/missing/pending summary (students in this class only)
    - Pending tab: submitted + missing payments
    - Recent expenses for this class
    """
    today = timezone.now().date()

    school_class = get_treasurer_class(req.user)

    # ── Core querysets scoped to this class ───────────────────────────────────
    all_requests = (
        get_class_payment_requests(school_class)
        .prefetch_related('transactions', 'assigned_to')
        .order_by('-created_at')
    )
    students      = get_class_students(school_class)
    student_count = students.count()

    # ── Per-request progress stats ────────────────────────────────────────────
    for pr in all_requests:
        pr.confirmed_count = pr.transactions.filter(status=Transaction.Status.CONFIRMED).count()
        pr.pending_count   = pr.transactions.filter(status=Transaction.Status.PENDING).count()
        pr.expected_count  = student_count if pr.assign_to_all else pr.assigned_to.count()
        pr.missing_count   = max(0, pr.expected_count - pr.confirmed_count - pr.pending_count)
        pr.collected = (
            pr.transactions.filter(status=Transaction.Status.CONFIRMED)
            .aggregate(s=Sum('amount'))['s'] or 0
        )
        pr.expected_total = pr.amount * pr.expected_count
        pr.is_overdue = bool(pr.due_date and pr.due_date < today)

    # ── Transaction maps (only for this class's requests) ─────────────────────
    class_request_ids = all_requests.values_list('id', flat=True)

    confirmed_txs = (
        Transaction.objects
        .filter(status=Transaction.Status.CONFIRMED, payment_request_id__in=class_request_ids)
        .select_related('student', 'payment_request')
    )
    pending_txs = (
        Transaction.objects
        .filter(status=Transaction.Status.PENDING, payment_request_id__in=class_request_ids)
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

    # ── Per-student summary rows ──────────────────────────────────────────────
    student_rows = []
    for student in students:
        s_confirmed = confirmed_map.get(student.id, set())
        s_pending   = pending_map.get(student.id, set())
        assigned_ids = set(
            all_requests.filter(
                Q(assign_to_all=True) | Q(assigned_to=student)
            ).values_list('id', flat=True)
        )
        missing_ids = assigned_ids - s_confirmed - s_pending
        owed_total = (
            all_requests.filter(id__in=missing_ids | s_pending)
            .aggregate(s=Sum('amount'))['s'] or 0
        )
        student_rows.append({
            'student':       student,
            'paid_count':    len(s_confirmed),
            'pending_count': len(s_pending),
            'missing_count': len(missing_ids),
            'paid_total':    paid_amount_map.get(student.id, 0),
            'owed_total':    owed_total,
        })

    # ── Pending / missing items ───────────────────────────────────────────────
    confirmed_pairs = set(
        Transaction.objects
        .filter(status=Transaction.Status.CONFIRMED, payment_request_id__in=class_request_ids)
        .values_list('student_id', 'payment_request_id')
    )
    pending_pairs = {
        (tx.student_id, tx.payment_request_id): tx
        for tx in Transaction.objects
        .filter(status=Transaction.Status.PENDING, payment_request_id__in=class_request_ids)
        .select_related('student', 'payment_request')
    }

    submitted_items = []
    missing_items   = []

    for pr in all_requests:
        assigned_students = (
            list(students) if pr.assign_to_all
            else list(pr.assigned_to.filter(
                is_active=True,
                student_profile__school_class=school_class,
            ))
        )
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

    recent_expenses = (
        Expense.objects
        .filter(school_class=school_class)
        .order_by('-spent_at')[:8]
    )

    return render(req, 'finances/treasurer_dashboard.html', {
        'school_class':    school_class,
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
    school_class = get_treasurer_class(req.user)
    students = get_class_students(school_class)

    if req.method == 'POST':
        form = PaymentRequestForm(req.POST)
        if form.is_valid():
            pr = form.save(commit=False)
            pr.created_by  = req.user
            pr.school_class = school_class   # ← enforce class ownership
            pr.save()
            if pr.assign_to_all:
                pr.assigned_to.clear()
            else:
                form.save_m2m()
                # Remove any assigned_to students not in this class
                pr.assigned_to.set(
                    pr.assigned_to.filter(student_profile__school_class=school_class)
                )
            messages.success(req, f'Payment request "{pr.title}" created successfully.')
            return redirect('treasurer_dashboard')
        messages.error(req, 'Please fix the errors below.')
    else:
        form = PaymentRequestForm()

    return render(req, 'finances/create_payment_request.html', {
        'form':         form,
        'students':     students,
        'school_class': school_class,
    })


# ── Log Bank Transfer ─────────────────────────────────────────────────────────

@treasurer_required
def log_transaction_view(req, pr_id=None, student_id=None):
    school_class = get_treasurer_class(req.user)
    students     = get_class_students(school_class)

    requests_by_student = {
        str(s.pk): [
            {'id': pr.id, 'title': str(pr), 'amount': str(pr.amount)}
            for pr in unconfirmed_requests_for_student(s, school_class)
        ]
        for s in students
    }

    initial     = {}
    pre_student = None

    if student_id:
        pre_student = students.filter(pk=student_id).first()
        if pre_student:
            initial['student'] = pre_student
    elif req.method == 'GET' and req.GET.get('student'):
        try:
            pre_student = students.get(pk=int(req.GET['student']))
            initial['student'] = pre_student
        except Exception:
            pass

    if pr_id and pre_student:
        pre_pr = unconfirmed_requests_for_student(pre_student, school_class).filter(pk=pr_id).first()
        if pre_pr:
            initial['payment_request'] = pre_pr
            initial['amount']          = pre_pr.amount

    pending_tx = None
    if pr_id and student_id:
        # Guard: the payment request must belong to this class
        pending_tx = Transaction.objects.filter(
            payment_request_id=pr_id,
            payment_request__school_class=school_class,
            student_id=student_id,
            student__student_profile__school_class=school_class,
            status=Transaction.Status.PENDING,
        ).first()
        if pending_tx:
            initial.setdefault('amount', pending_tx.amount)
            initial.setdefault('note',   pending_tx.note)

    if req.method == 'POST':
        posted_student_id = req.POST.get('student')
        pr_qs = PaymentRequest.objects.none()
        if posted_student_id:
            try:
                posted_student = students.get(pk=posted_student_id)
                pr_qs = get_class_payment_requests(school_class).filter(
                    Q(assign_to_all=True) | Q(assigned_to=posted_student)
                )
            except Exception:
                pr_qs = get_class_payment_requests(school_class)

        form = LogTransactionForm(req.POST, student_queryset=students, pr_queryset=pr_qs)
        if form.is_valid():
            cd      = form.cleaned_data
            student = cd['student']
            pr      = cd['payment_request']

            # Double-check ownership before writing
            if (
                not students.filter(pk=student.pk).exists()
                or pr.school_class_id != (school_class.pk if school_class else None)
            ):
                messages.error(req, 'Access denied — that student or request is not in your class.')
                return redirect('treasurer_dashboard')

            status = cd['status']
            now    = timezone.now()

            if status == Transaction.Status.CONFIRMED:
                Transaction.objects.filter(
                    student=student, payment_request=pr,
                    status=Transaction.Status.PENDING,
                ).delete()

            Transaction.objects.create(
                student=student,
                payment_request=pr,
                school_class=school_class,
                amount=cd['amount'],
                status=status,
                note=cd.get('note', ''),
                paid_at=cd['paid_at'],
                confirmed_at=now if status == Transaction.Status.CONFIRMED else None,
            )
            status_label = dict(Transaction.Status.choices).get(status, status)
            messages.success(
                req,
                f'✅ Transfer logged: {student.get_full_name() or student.username} '
                f'→ "{pr.title}" ({cd["amount"]} CZK) — {status_label}.'
            )
            return redirect('treasurer_dashboard')
        messages.error(req, 'Please fix the errors below.')
    else:
        pr_qs = get_class_payment_requests(school_class)
        if pre_student:
            pr_qs = pr_qs.filter(
                Q(assign_to_all=True) | Q(assigned_to=pre_student)
            )
        form = LogTransactionForm(initial=initial, student_queryset=students, pr_queryset=pr_qs)

    return render(req, 'finances/log_transaction.html', {
        'form':                form,
        'students':            students,
        'requests_by_student': json.dumps(requests_by_student),
        'pending_tx':          pending_tx,
        'school_class':        school_class,
    })


# ── Quick-confirm a pending Transaction ───────────────────────────────────────

@treasurer_required
@require_POST_or_405
def confirm_pending_view(req):
    """POST-only: confirm a pending Transaction — scoped to this class."""
    school_class = get_treasurer_class(req.user)

    tx = None
    tx_id = req.POST.get('tx_id')
    if tx_id:
        try:
            tx = Transaction.objects.get(
                pk=int(tx_id),
                status=Transaction.Status.PENDING,
                payment_request__school_class=school_class,
            )
        except (Transaction.DoesNotExist, ValueError):
            pass

    if not tx:
        try:
            s_id = int(req.POST.get('student_id') or 0)
            p_id = int(req.POST.get('pr_id') or 0)
        except ValueError:
            s_id = p_id = 0
        if s_id and p_id:
            tx = Transaction.objects.filter(
                student_id=s_id,
                payment_request_id=p_id,
                payment_request__school_class=school_class,
                status=Transaction.Status.PENDING,
            ).first()

    if not tx:
        messages.error(req, 'Pending transaction not found.')
        return redirect('treasurer_dashboard')

    now = timezone.now()
    Transaction.objects.create(
        student=tx.student,
        payment_request=tx.payment_request,
        school_class=school_class,
        amount=tx.amount,
        status=Transaction.Status.CONFIRMED,
        note=tx.note or '',
        paid_at=tx.paid_at,
        confirmed_at=now,
    )
    tx.delete()

    name = tx.student.get_full_name() or tx.student.username
    messages.success(req, f'✅ Confirmed payment for {name} → "{tx.payment_request.title}"')
    return redirect('treasurer_dashboard')


# ── AJAX: unconfirmed requests for one student ────────────────────────────────

@treasurer_required
def student_requests_json(req, student_id):
    school_class = get_treasurer_class(req.user)
    students     = get_class_students(school_class)

    # Only respond for students who actually belong to this class
    student = students.filter(pk=student_id).first()
    if not student:
        return JsonResponse([], safe=False)
    data = [
        {'id': pr.id, 'title': str(pr), 'amount': str(pr.amount)}
        for pr in unconfirmed_requests_for_student(student, school_class)
    ]
    return JsonResponse(data, safe=False)


# ── Log / Edit Expense ────────────────────────────────────────────────────────

@treasurer_required
def log_expense_view(req, expense_id=None):
    school_class = get_treasurer_class(req.user)

    instance = None
    if expense_id:
        try:
            # Guard: only load expenses that belong to this class
            instance = Expense.objects.get(pk=expense_id, school_class=school_class)
        except Expense.DoesNotExist:
            messages.error(req, 'Expense not found.')
            return redirect('treasurer_dashboard')

    if req.method == 'POST':
        form = ExpenseForm(req.POST, instance=instance)
        if form.is_valid():
            expense = form.save(commit=False)
            if not instance:
                expense.recorded_by  = req.user
                expense.school_class = school_class   # ← enforce class ownership
            expense.save()
            verb = 'updated' if instance else 'logged'
            messages.success(req, f'✅ Expense "{expense.title}" ({expense.amount} CZK) {verb}.')
            return redirect('treasurer_dashboard')
        messages.error(req, 'Please fix the errors below.')
    else:
        form = ExpenseForm(instance=instance)

    return render(req, 'finances/log_expense.html', {
        'form':         form,
        'instance':     instance,
        'school_class': school_class,
    })


# ── Delete Expense ────────────────────────────────────────────────────────────

@treasurer_required
@require_POST_or_405
def delete_expense_view(req, expense_id):
    school_class = get_treasurer_class(req.user)
    try:
        # Guard: only delete expenses that belong to this class
        expense = Expense.objects.get(pk=expense_id, school_class=school_class)
        title = expense.title
        expense.delete()
        messages.success(req, f'🗑 Expense "{title}" deleted.')
    except Expense.DoesNotExist:
        messages.error(req, 'Expense not found.')
    return redirect('treasurer_dashboard')
