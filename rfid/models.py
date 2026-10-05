from django.db import models

from catalog.models import Item


class RFIDTag(models.Model):
    tag_uid = models.CharField(max_length=32, unique=True)
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name="tag")
    security_bit = models.BooleanField(default=True, help_text="True = secured (gate alarms if it leaves)")
    tagged_at = models.DateTimeField(auto_now_add=True)
    tagged_by = models.CharField(max_length=150, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.tag_uid} -> {self.item.accession_no}"


class TagEvent(models.Model):
    """Tag monitoring history."""

    tag_uid = models.CharField(max_length=32, db_index=True)
    event = models.CharField(max_length=12)  # TAGGED / RETAGGED / SEEN
    detail = models.CharField(max_length=200, blank=True)
    actor = models.CharField(max_length=150, blank=True)
    ts = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-ts", "-id"]


class DeviceEvent(models.Model):
    """Every message from/to a device. event_id makes processing idempotent."""

    event_id = models.CharField(max_length=64, unique=True)
    device_type = models.CharField(max_length=20, db_index=True)
    device_id = models.CharField(max_length=60, blank=True)
    kind = models.CharField(max_length=30)
    payload = models.JSONField(default=dict)
    ts = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-ts", "-id"]


class GateEvent(models.Model):
    class Kind(models.TextChoices):
        UNAUTHORISED = "UNAUTHORISED_REMOVAL", "Unauthorised removal"
        UNKNOWN = "UNKNOWN_TAG", "Unknown tag"
        AUTHORISED = "AUTHORISED_PASS", "Authorised pass"
        FOOTFALL = "FOOTFALL", "Footfall"

    event_id = models.CharField(max_length=64, unique=True)
    kind = models.CharField(max_length=24, choices=Kind.choices, db_index=True)
    tag_uid = models.CharField(max_length=32, blank=True)
    accession_no = models.CharField(max_length=40, blank=True)
    alarm = models.BooleanField(default=False)
    cctv_image = models.CharField(max_length=200, blank=True)
    offline_mode = models.BooleanField(default=False)
    ts = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-ts", "-id"]


class InventorySession(models.Model):
    shelf = models.CharField(max_length=40)
    started_by = models.CharField(max_length=150)
    ts = models.DateTimeField(auto_now_add=True)
    expected = models.PositiveIntegerField(default=0)
    scanned = models.PositiveIntegerField(default=0)
    missing = models.JSONField(default=list)
    misplaced = models.JSONField(default=list)
    unknown = models.JSONField(default=list)

    class Meta:
        ordering = ["-ts", "-id"]
