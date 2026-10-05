from django.apps import AppConfig


class CatalogConfig(AppConfig):
    name = "catalog"

    def ready(self):
        from django.db.models.signals import post_delete, post_save

        from catalog import search
        from catalog.models import Biblio

        post_save.connect(lambda sender, instance, **kw: search.index(instance), sender=Biblio, weak=False, dispatch_uid="biblio_index")
        post_delete.connect(lambda sender, instance, **kw: search.remove(instance.pk), sender=Biblio, weak=False, dispatch_uid="biblio_unindex")
