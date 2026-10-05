from django.contrib import admin, messages

from catalog.models import Acquisition, Biblio, Item, Serial


class ItemInline(admin.TabularInline):
    model = Item
    extra = 0


@admin.register(Biblio)
class BiblioAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "isbn", "call_number", "year")
    search_fields = ("title", "author", "isbn")
    inlines = [ItemInline]


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("accession_no", "barcode", "biblio", "shelf_location", "status", "is_reference")
    search_fields = ("accession_no", "barcode")
    list_filter = ("status", "is_reference")


@admin.action(description="Receive selected orders (create catalogue records)")
def receive(modeladmin, request, queryset):
    for order in queryset.filter(status="ORDERED"):
        biblio = Biblio.objects.create(title=order.title, author=order.author, isbn=order.isbn)
        for n in range(order.quantity):
            acc = f"ACQ{order.pk:05d}-{n + 1:02d}"
            Item.objects.create(biblio=biblio, accession_no=acc, barcode=acc, shelf_location="NEW")
        order.status = "RECEIVED"
        order.save()
    messages.success(request, "Orders received and catalogue records created.")


@admin.register(Acquisition)
class AcquisitionAdmin(admin.ModelAdmin):
    list_display = ("title", "vendor", "quantity", "status")
    actions = [receive]


@admin.register(Serial)
class SerialAdmin(admin.ModelAdmin):
    list_display = ("title", "issn", "frequency", "last_issue")
