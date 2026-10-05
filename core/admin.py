from django.contrib import admin

from core.models import AuditLog, Setting, StaffCard


@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ("key", "value", "updated")


@admin.register(StaffCard)
class StaffCardAdmin(admin.ModelAdmin):
    list_display = ("card_uid", "user", "active")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("ts", "actor", "action", "target")
    search_fields = ("actor", "action", "target", "detail")
    list_filter = ("action",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
