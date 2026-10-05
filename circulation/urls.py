from django.urls import path

from circulation import views

urlpatterns = [path("", views.desk, name="desk")]
