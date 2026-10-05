from django.contrib import admin

from migration_tool.models import ImportBatch, StagingRow


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "source_file", "status", "total_rows", "valid_rows", "rejected_rows", "duplicate_rows", "migrated_rows", "started")


@admin.register(StagingRow)
class StagingRowAdmin(admin.ModelAdmin):
    list_display = ("batch", "row_no", "status", "error")
    list_filter = ("status",)
