from django.db import migrations


def create_fts(apps, schema_editor):
    """SQLite FTS5 virtual table for real-time full-text search. Silently skipped if FTS5 is unavailable
    (the application then falls back to LIKE search)."""
    try:
        schema_editor.execute("CREATE VIRTUAL TABLE IF NOT EXISTS biblio_fts USING fts5(biblio_id UNINDEXED, content)")
    except Exception:
        return
    Biblio = apps.get_model("catalog", "Biblio")
    for b in Biblio.objects.all().iterator():
        content = " ".join([b.title, b.author, b.isbn, b.call_number, b.publisher])
        schema_editor.execute("INSERT INTO biblio_fts(biblio_id, content) VALUES (%s, %s)", [b.pk, content])


def drop_fts(apps, schema_editor):
    schema_editor.execute("DROP TABLE IF EXISTS biblio_fts")


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]
    operations = [migrations.RunPython(create_fts, drop_fts)]
