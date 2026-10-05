from django.db import models

from catalog.models import Item
from members.models import Member


class Loan(models.Model):
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="loans")
    member = models.ForeignKey(Member, on_delete=models.PROTECT, related_name="loans")
    out_at = models.DateTimeField()
    due_at = models.DateTimeField()
    returned_at = models.DateTimeField(null=True, blank=True)
    renewals = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-out_at"]


class Fine(models.Model):
    member = models.ForeignKey(Member, on_delete=models.PROTECT, related_name="fines")
    loan = models.ForeignKey(Loan, null=True, blank=True, on_delete=models.SET_NULL)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    reason = models.CharField(max_length=120, default="Overdue")
    paid = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)


class Transaction(models.Model):
    """Auditable circulation history (successes and denials)."""

    ts = models.DateTimeField(auto_now_add=True, db_index=True)
    tx_type = models.CharField(max_length=12)  # CHECKOUT / CHECKIN / RENEW
    channel = models.CharField(max_length=8, default="WEB")  # WEB / NCIP / SIP2 / RFID
    item = models.ForeignKey(Item, null=True, blank=True, on_delete=models.SET_NULL)
    item_ref = models.CharField(max_length=60, blank=True)
    member_no = models.CharField(max_length=30, blank=True)
    operator = models.CharField(max_length=150)
    success = models.BooleanField(default=True)
    reason = models.CharField(max_length=40, blank=True)
    detail = models.CharField(max_length=250, blank=True)

    class Meta:
        ordering = ["-ts", "-id"]
