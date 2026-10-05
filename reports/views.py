import csv
from datetime import datetime, timedelta

from django.db.models import Count, Max, Q
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from circulation.models import Fine, Transaction
from core.roles import require_perm
from members.models import Member
from rfid.models import DeviceEvent, GateEvent, RFIDTag

REPORTS = {
    "tagged_items": "Tagged items",
    "members": "Members",
    "circulation": "Circulation",
    "operators": "Operator activity",
    "rfid_clients": "RFID client activity",
    "gate_events": "Gate events",
    "fines": "Fines",
}


def _date(value, end=False):
    try:
        d = datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError):
        return None
    d = timezone.make_aware(d)
    return d + timedelta(days=1) if end else d


def _range(qs, field, p):
    start, end = _date(p.get("from")), _date(p.get("to"), end=True)
    if start:
        qs = qs.filter(**{f"{field}__gte": start})
    if end:
        qs = qs.filter(**{f"{field}__lt": end})
    return qs


def build(rtype, p):
    q = (p.get("q") or "").strip()
    if rtype == "tagged_items":
        qs = RFIDTag.objects.select_related("item", "item__biblio")
        if q:
            qs = qs.filter(Q(tag_uid__icontains=q) | Q(item__accession_no__icontains=q) | Q(item__biblio__title__icontains=q))
        return ["Tag UID", "Accession", "Title", "Shelf", "Secured", "Tagged at", "Tagged by"], [
            [t.tag_uid, t.item.accession_no, t.item.biblio.title, t.item.shelf_location, "yes" if t.security_bit else "no",
             t.tagged_at.strftime("%Y-%m-%d %H:%M"), t.tagged_by] for t in qs[:2000]]
    if rtype == "members":
        qs = Member.objects.all()
        if q:
            qs = qs.filter(Q(member_no__icontains=q) | Q(name__icontains=q))
        return ["Member no", "Name", "Category", "Blocked", "Active loans", "Fines owed"], [
            [m.member_no, m.name, m.category, "yes" if m.is_blocked else "no",
             m.loans.filter(returned_at__isnull=True).count(), m.outstanding_fines()] for m in qs[:2000]]
    if rtype == "circulation":
        qs = _range(Transaction.objects.all(), "ts", p)
        for key, field in (("operator", "operator"), ("tx_type", "tx_type"), ("channel", "channel")):
            if p.get(key):
                qs = qs.filter(**{field: p[key]})
        if q:
            qs = qs.filter(Q(item_ref__icontains=q) | Q(member_no__icontains=q))
        return ["Time", "Type", "Channel", "Item", "Member", "Operator", "Result", "Reason"], [
            [t.ts.strftime("%Y-%m-%d %H:%M:%S"), t.tx_type, t.channel, t.item_ref, t.member_no, t.operator,
             "ok" if t.success else "denied", t.reason] for t in qs[:5000]]
    if rtype == "operators":
        qs = _range(Transaction.objects.all(), "ts", p)
        rows = qs.values("operator").annotate(total=Count("id"), ok=Count("id", filter=Q(success=True)),
                                              denied=Count("id", filter=Q(success=False))).order_by("-total")
        return ["Operator", "Transactions", "Successful", "Denied"], [[r["operator"], r["total"], r["ok"], r["denied"]] for r in rows]
    if rtype == "rfid_clients":
        qs = _range(DeviceEvent.objects.all(), "ts", p)
        rows = qs.values("device_type", "device_id").annotate(events=Count("id"), last=Max("ts")).order_by("-events")
        return ["Device type", "Device id", "Events", "Last seen"], [
            [r["device_type"], r["device_id"], r["events"], r["last"].strftime("%Y-%m-%d %H:%M")] for r in rows]
    if rtype == "gate_events":
        qs = _range(GateEvent.objects.all(), "ts", p)
        if p.get("kind"):
            qs = qs.filter(kind=p["kind"])
        return ["Time", "Kind", "Tag", "Accession", "Alarm", "CCTV image", "LMS offline"], [
            [g.ts.strftime("%Y-%m-%d %H:%M:%S"), g.kind, g.tag_uid, g.accession_no, "yes" if g.alarm else "no",
             g.cctv_image, "yes" if g.offline_mode else "no"] for g in qs[:5000]]
    if rtype == "fines":
        qs = _range(Fine.objects.select_related("member"), "created", p)
        return ["Date", "Member", "Amount", "Reason", "Paid"], [
            [f.created.strftime("%Y-%m-%d"), f.member.member_no, f.amount, f.reason, "yes" if f.paid else "no"] for f in qs[:5000]]
    return None


def _safe(cell):
    s = str(cell)
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s  # CSV/Excel formula-injection guard


@require_perm("reports.view")
def report(request):
    rtype = request.GET.get("type", "circulation")
    if rtype not in REPORTS:
        rtype = "circulation"
    headers, rows = build(rtype, request.GET)
    if request.GET.get("format") == "csv":
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="{rtype}.csv"'
        w = csv.writer(resp)
        w.writerow(headers)
        for r in rows:
            w.writerow([_safe(c) for c in r])
        return resp
    return render(request, "reports/report.html", {"types": REPORTS, "rtype": rtype, "title": REPORTS[rtype],
                                                   "headers": headers, "rows": rows, "p": request.GET})
