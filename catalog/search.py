"""Full-text search. Uses SQLite FTS5 kept in sync in real time; falls back to LIKE queries."""
import re

from django.db import connection
from django.db.models import Q

TABLE = "biblio_fts"
_available = None


def available():
    global _available
    if _available is None:
        try:
            with connection.cursor() as cur:
                cur.execute(f"SELECT 1 FROM {TABLE} LIMIT 1")
            _available = True
        except Exception:
            _available = False
    return _available


def _content(b):
    return " ".join([b.title, b.author, b.isbn, b.call_number, b.publisher])


def index(biblio):
    if not available():
        return
    with connection.cursor() as cur:
        cur.execute(f"DELETE FROM {TABLE} WHERE biblio_id = %s", [biblio.pk])
        cur.execute(f"INSERT INTO {TABLE}(biblio_id, content) VALUES (%s, %s)", [biblio.pk, _content(biblio)])


def remove(pk):
    if available():
        with connection.cursor() as cur:
            cur.execute(f"DELETE FROM {TABLE} WHERE biblio_id = %s", [pk])


def reindex_many(biblios):
    if not available():
        return
    rows = [(b.pk, _content(b)) for b in biblios]
    with connection.cursor() as cur:
        cur.executemany(f"INSERT INTO {TABLE}(biblio_id, content) VALUES (%s, %s)", rows)


def purge_orphans():
    if available():
        with connection.cursor() as cur:
            cur.execute(f"DELETE FROM {TABLE} WHERE CAST(biblio_id AS INTEGER) NOT IN (SELECT id FROM catalog_biblio)")


def search(query, limit=100):
    from catalog.models import Biblio

    tokens = re.findall(r"\w+", query or "")
    if not tokens:
        return Biblio.objects.none()
    if available():
        match = " ".join(f'"{t}"*' for t in tokens)
        with connection.cursor() as cur:
            cur.execute(f"SELECT biblio_id FROM {TABLE} WHERE {TABLE} MATCH %s ORDER BY rank LIMIT %s", [match, limit])
            ids = [int(r[0]) for r in cur.fetchall()]
        found = {b.pk: b for b in Biblio.objects.filter(pk__in=ids)}
        return [found[i] for i in ids if i in found]
    q = Q()
    for t in tokens:
        q &= (Q(title__icontains=t) | Q(author__icontains=t) | Q(isbn__icontains=t) | Q(call_number__icontains=t))
    return list(Biblio.objects.filter(q)[:limit])
