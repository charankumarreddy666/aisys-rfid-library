from django.conf import settings
from django.db import models


class Setting(models.Model):
    key = models.CharField(max_length=64, unique=True)
    value = models.CharField(max_length=255)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.key}={self.value}"


class AuditLog(models.Model):
    """Append-only record of every administrative and circulation action."""

    ts = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.CharField(max_length=150)
    action = models.CharField(max_length=64, db_index=True)
    target = models.CharField(max_length=255, blank=True)
    detail = models.TextField(blank=True)

    class Meta:
        ordering = ["-ts", "-id"]

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionError("Audit entries are append-only")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Audit entries cannot be deleted")

    def __str__(self):
        return f"{self.ts:%Y-%m-%d %H:%M} {self.actor} {self.action}"


class StaffCard(models.Model):
    """Maps a smart-card UID to a staff user (used by the mock credential provider)."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_card")
    card_uid = models.CharField(max_length=64, unique=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.card_uid} -> {self.user}"
