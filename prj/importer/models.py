"""
importer/models.py
──────────────────
Audit log for CSV student imports.

ImportBatch  – one uploaded CSV file = one batch.
ImportRow    – one row of the CSV = one row record, with outcome.
"""

from django.conf import settings
from django.db import models


class ImportBatch(models.Model):
    """Records a single CSV upload event."""

    class Status(models.TextChoices):
        PENDING   = 'pending',   'Pending'
        COMPLETED = 'completed', 'Completed'
        FAILED    = 'failed',    'Failed'

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='import_batches',
    )
    school_class = models.ForeignKey(
        'accounts.SchoolClass',
        on_delete=models.SET_NULL,
        null=True,
        related_name='import_batches',
    )
    original_filename = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    total_rows   = models.PositiveIntegerField(default=0)
    imported     = models.PositiveIntegerField(default=0)
    skipped      = models.PositiveIntegerField(default=0)
    errors       = models.PositiveIntegerField(default=0)
    created_at   = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Import Batch'
        verbose_name_plural = 'Import Batches'

    def __str__(self):
        return f"Batch #{self.pk} – {self.school_class} ({self.created_at:%Y-%m-%d %H:%M})"


class ImportRow(models.Model):
    """Records the outcome of a single CSV data row."""

    class Outcome(models.TextChoices):
        IMPORTED = 'imported', 'Imported'
        SKIPPED  = 'skipped',  'Skipped'
        ERROR    = 'error',    'Error'

    batch      = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name='rows')
    row_number = models.PositiveIntegerField()
    first_name = models.CharField(max_length=150)
    last_name  = models.CharField(max_length=150)
    username   = models.CharField(max_length=150, blank=True)
    variable_symbol = models.CharField(max_length=10, blank=True)
    parent_email    = models.CharField(max_length=254, blank=True)
    # Plain-text password stored only for **newly created** accounts so it can
    # be exported to a credential sheet for the teacher.  Left blank when the
    # account already existed and its password was not changed.
    plain_password  = models.CharField(
        max_length=128,
        blank=True,
        verbose_name='Initial password',
        help_text='Plain-text password set at import time (empty for pre-existing accounts).',
    )
    outcome    = models.CharField(max_length=20, choices=Outcome.choices)
    message    = models.TextField(blank=True)   # error detail or "new user" / "existing"

    class Meta:
        ordering = ['batch', 'row_number']
        verbose_name = 'Import Row'
        verbose_name_plural = 'Import Rows'

    def __str__(self):
        return f"Row {self.row_number} ({self.first_name} {self.last_name}) → {self.outcome}"
