from django.urls import path

from reports import views

urlpatterns = [path("", views.report, name="reports")]
