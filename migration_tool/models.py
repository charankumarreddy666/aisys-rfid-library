from django.db import models


class ImportBatch(models.Model):
    class Status(models.TextChoices):
        DRY_RUN = "DRY_RUN", "Dry run (nothing written)"
        COMMITTED = "COMMITTED", "Committed"
        ROLLED_BACK = "ROLLED_BACK", "Rolled back"
        FAILED = "FAILED", "Failed"

    source_file = models.CharField(max_length=300)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.FAILED)
    dry_run = models.BooleanField(default=True)
    started = models.DateTimeField(auto_now_add=True)
    finished = models.DateTimeField(null=True, blank=True)
    total_rows = models.PositiveIntegerField(default=0)
    valid_rows = models.PositiveIntegerField(default=0)
    rejected_rows = models.PositiveIntegerField(default=0)
    duplicate_rows = models.PositiveIntegerField(default=0)
    migrated_rows = models.PositiveIntegerField(default=0)
    backup_file = models.CharField(max_length=300, blank=True)
    error = models.CharField(max_length=300, blank=True)

    def __str__(self):
        return f"Batch {self.pk} ({self.status})"


class StagingRow(models.Model):
    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="rows")
    row_no = models.PositiveIntegerField()
    data = models.JSONField()
    status = models.CharField(max_length=10, db_index=True)  # VALID / REJECTED / DUPLICATE / MIGRATED
    error = models.CharField(max_length=300, blank=True)
