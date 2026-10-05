from django.db import models


class Biblio(models.Model):
    """Bibliographic (title-level) record."""

    title = models.CharField(max_length=300)
    author = models.CharField(max_length=200, blank=True)
    isbn = models.CharField(max_length=20, blank=True, db_index=True)
    call_number = models.CharField(max_length=60, blank=True)
    publisher = models.CharField(max_length=200, blank=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    source_key = models.CharField(max_length=60, blank=True, db_index=True)
    import_batch = models.ForeignKey("migration_tool.ImportBatch", null=True, blank=True, on_delete=models.SET_NULL)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]
        verbose_name_plural = "bibliographic records"

    def __str__(self):
        return self.title


class Item(models.Model):
    """Physical copy of a title."""

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        ON_LOAN = "ON_LOAN", "On loan"
        MISSING = "MISSING", "Missing"

    biblio = models.ForeignKey(Biblio, on_delete=models.CASCADE, related_name="items")
    accession_no = models.CharField(max_length=40, unique=True)
    barcode = models.CharField(max_length=40, unique=True)
    shelf_location = models.CharField(max_length=40, blank=True, db_index=True)
    is_reference = models.BooleanField(default=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.AVAILABLE)
    import_batch = models.ForeignKey("migration_tool.ImportBatch", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["accession_no"]

    def __str__(self):
        return f"{self.accession_no} ({self.biblio.title})"


class Acquisition(models.Model):
    """Minimal acquisition order. Receiving creates catalogue records (admin action)."""

    vendor = models.CharField(max_length=120)
    title = models.CharField(max_length=300)
    author = models.CharField(max_length=200, blank=True)
    isbn = models.CharField(max_length=20, blank=True)
    quantity = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=10, default="ORDERED", choices=[("ORDERED", "Ordered"), ("RECEIVED", "Received")])
    created = models.DateTimeField(auto_now_add=True)


class Serial(models.Model):
    title = models.CharField(max_length=300)
    issn = models.CharField(max_length=12, blank=True)
    frequency = models.CharField(max_length=20, default="Monthly")
    last_issue = models.CharField(max_length=40, blank=True)
