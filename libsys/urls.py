from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import include, path

from catalog import views as catalog_views
from core import views as core_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", core_views.dashboard, name="dashboard"),
    path("login/", LoginView.as_view(template_name="login.html"), name="login"),
    path("login/smartcard/", core_views.smartcard_login, name="smartcard_login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("health", core_views.health, name="health"),
    path("system/", core_views.system, name="system"),
    path("opac/", catalog_views.opac, name="opac"),
    path("catalog/", include("catalog.urls")),
    path("members/", include("members.urls")),
    path("circulation/", include("circulation.urls")),
    path("rfid/", include("rfid.urls")),
    path("interop/", include("interop.urls")),
    path("reports/", include("reports.urls")),
]
