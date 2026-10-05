from django.db import models


class Notification(models.Model):
    channel = models.CharField(max_length=6, choices=[("email", "Email"), ("sms", "SMS"), ("print", "Print")])
    recipient = models.CharField(max_length=150)
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField()
    status = models.CharField(max_length=7, default="QUEUED", db_index=True)  # QUEUED / SENT / FAILED
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=200, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created", "-id"]
