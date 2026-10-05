from django.urls import path

from interop import views

urlpatterns = [
    path("ncip", views.ncip_endpoint, name="ncip"),
    path("sip2", views.sip2_endpoint, name="sip2"),
]
