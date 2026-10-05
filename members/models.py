from django.db import models
from django.db.models import Sum


class Member(models.Model):
    member_no = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150)
    email = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    category = models.CharField(max_length=30, default="Student")
    active = models.BooleanField(default=True)
    is_blocked = models.BooleanField(default=False)
    block_reason = models.CharField(max_length=200, blank=True)
    notify_email = models.BooleanField(default=True)
    notify_sms = models.BooleanField(default=False)
    notify_print = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["member_no"]

    def __str__(self):
        return f"{self.member_no} {self.name}"

    def outstanding_fines(self):

        return self.fines.filter(paid=False).aggregate(t=Sum("amount"))["t"] or 0
