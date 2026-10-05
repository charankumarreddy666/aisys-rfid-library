from django.urls import path

from catalog import views

urlpatterns = [
    path("", views.catalog_list, name="catalog"),
    path("<int:pk>/", views.biblio_detail, name="biblio_detail"),
    path("label/<int:item_id>/", views.item_label, name="item_label"),
    path("shelves/", views.bookshelf, name="bookshelf"),
]
