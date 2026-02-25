"""
importer/admin.py
─────────────────
Admin registrations for ImportBatch and ImportRow.
"""

from django.contrib import admin

from .models import ImportBatch, ImportRow


class ImportRowInline(admin.TabularInline):
    model = ImportRow
    extra = 0
    readonly_fields = ('row_number', 'first_name', 'last_name', 'username',
                       'variable_symbol', 'parent_email', 'outcome', 'message')
    can_delete = False


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display  = ('id', 'school_class', 'uploaded_by', 'status',
                     'total_rows', 'imported', 'skipped', 'errors', 'created_at')
    list_filter   = ('status', 'school_class')
    readonly_fields = ('uploaded_by', 'school_class', 'original_filename', 'status',
                       'total_rows', 'imported', 'skipped', 'errors',
                       'created_at', 'completed_at')
    inlines = [ImportRowInline]
