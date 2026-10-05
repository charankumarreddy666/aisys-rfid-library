from django.urls import path

from rfid import views

urlpatterns = [
    path("", views.console, name="rfid_console"),
    path("ui/tag/", views.ui_tag, name="rfid_ui_tag"),
    path("ui/gate/", views.ui_gate, name="rfid_ui_gate"),
    path("ui/inventory/", views.ui_inventory, name="rfid_ui_inventory"),
    path("cctv/<str:name>", views.cctv, name="rfid_cctv"),
    path("api/tag", views.api_tag),
    path("api/gate", views.api_gate),
    path("api/inventory", views.api_inventory),
    path("api/gate-cache", views.api_gate_cache),
]
