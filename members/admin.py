from django.contrib import admin

from members.models import Member


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("member_no", "name", "category", "is_blocked", "active")
    search_fields = ("member_no", "name")
    list_filter = ("is_blocked", "category", "active")
