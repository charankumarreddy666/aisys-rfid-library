from django.contrib import admin

from notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created", "channel", "recipient", "subject", "status", "attempts")
    list_filter = ("channel", "status")
