from django.contrib import admin

from rfid.models import DeviceEvent, GateEvent, InventorySession, RFIDTag, TagEvent

for model in (RFIDTag, TagEvent, DeviceEvent, GateEvent, InventorySession):
    admin.site.register(model)
