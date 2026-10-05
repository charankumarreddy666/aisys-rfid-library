from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from catalog import barcode, netcat, search
from catalog.models import Biblio, Item
from core import audit
from core.roles import require_perm


def _year(value):
    value = (value or "").strip()
    return int(value) if value.isdigit() and 1000 <= int(value) <= 2100 else None


@require_perm("catalog.view")
def catalog_list(request):
    from core.roles import has_perm

    prefill = {}
    if request.method == "POST":
        if not has_perm(request.user, "catalog.edit"):
            return redirect("catalog")
        action = request.POST.get("action")
        if action == "lookup":
            prefill = netcat.lookup(request.POST.get("isbn")) or {}
            prefill["isbn"] = request.POST.get("isbn", "")
            if len(prefill) == 1:
                messages.warning(request, "No record found for that ISBN in the external catalogue.")
        elif action == "add":
            title = request.POST.get("title", "").strip()
            if not title:
                messages.error(request, "Title is required.")
            else:
                b = Biblio.objects.create(
                    title=title[:300], author=request.POST.get("author", "")[:200], isbn=request.POST.get("isbn", "")[:20],
                    call_number=request.POST.get("call_number", "")[:60], publisher=request.POST.get("publisher", "")[:200],
                    year=_year(request.POST.get("year")),
                )
                audit.log(request.user, "BIBLIO_CREATED", b.pk, title)
                messages.success(request, "Title created. Add a copy (item) on the next page.")
                return redirect("biblio_detail", pk=b.pk)
    q = request.GET.get("q", "").strip()
    results = search.search(q) if q else Biblio.objects.annotate(n=Count("items")).order_by("-id")[:25]
    return render(request, "catalog/list.html", {"q": q, "results": results, "prefill": prefill, "fts": search.available()})


@require_perm("catalog.view")
def biblio_detail(request, pk):
    from core.roles import has_perm

    biblio = get_object_or_404(Biblio, pk=pk)
    if request.method == "POST" and has_perm(request.user, "catalog.edit"):
        acc = request.POST.get("accession_no", "").strip()
        bc = request.POST.get("barcode", "").strip() or acc
        if not acc:
            messages.error(request, "Accession number is required.")
        elif Item.objects.filter(Q(accession_no=acc) | Q(barcode=bc)).exists():
            messages.error(request, "That accession number or barcode already exists.")
        else:
            Item.objects.create(
                biblio=biblio, accession_no=acc[:40], barcode=bc[:40], shelf_location=request.POST.get("shelf_location", "")[:40],
                is_reference=bool(request.POST.get("is_reference")),
            )
            audit.log(request.user, "ITEM_CREATED", acc, biblio.title)
            messages.success(request, f"Copy {acc} added.")
        return redirect("biblio_detail", pk=pk)
    items = biblio.items.select_related("tag")
    return render(request, "catalog/detail.html", {"biblio": biblio, "items": items})


@require_perm("catalog.view")
def item_label(request, item_id):
    item = get_object_or_404(Item.objects.select_related("biblio"), pk=item_id)
    return render(request, "catalog/label.html", {"item": item, "barcode_svg": barcode.svg(item.barcode)})


@require_perm("catalog.view")
def bookshelf(request):
    shelves = {}
    for it in Item.objects.select_related("biblio").exclude(shelf_location="").order_by("shelf_location", "biblio__call_number")[:600]:
        shelves.setdefault(it.shelf_location, []).append(it)
    return render(request, "catalog/shelves.html", {"shelves": shelves})


def opac(request):
    """Public read-only catalogue search."""
    q = request.GET.get("q", "").strip()
    rows = []
    if q:
        for b in search.search(q, limit=50):
            avail = b.items.filter(status=Item.Status.AVAILABLE, is_reference=False).count()
            rows.append({"biblio": b, "copies": b.items.count(), "available": avail})
    return render(request, "opac.html", {"q": q, "rows": rows})
