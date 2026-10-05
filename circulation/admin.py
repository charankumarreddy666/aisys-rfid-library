from django.contrib import admin

from circulation.models import Fine, Loan, Transaction

admin.site.register(Loan)
admin.site.register(Fine)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("ts", "tx_type", "channel", "item_ref", "member_no", "operator", "success", "reason")
    list_filter = ("tx_type", "channel", "success")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
