import json
import re

from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.conf import settings

from core.roles import require_perm
from core.security import MAX_BODY, api_key_ok
from rfid import services
from rfid.models import DeviceEvent, GateEvent, InventorySession, RFIDTag, TagEvent


@require_perm("gate.view")
def console(request):
    ctx = {
        "tags": RFIDTag.objects.select_related("item", "item__biblio").order_by("-tagged_at")[:15],
        "events": DeviceEvent.objects.all()[:15],
        "gates": GateEvent.objects.all()[:10],
        "sessions": InventorySession.objects.all()[:5],
        "tag_history": TagEvent.objects.all()[:8],
    }
    return render(request, "rfid/console.html", ctx)


@require_perm("tag.manage")
@require_POST
def ui_tag(request):
    try:
        tag = services.tag_item(request.POST.get("accession_no"), request.POST.get("tag_uid"), request.user,
                                retag=bool(request.POST.get("retag")))
        messages.success(request, f"Tag {tag.tag_uid} is linked to {tag.item.accession_no} - {tag.item.biblio.title}.")
    except services.RfidError as err:
        messages.error(request, f"{err.message} [{err.code}]")
    return redirect("rfid_console")


@require_perm("gate.simulate")
@require_POST
def ui_gate(request):
    import uuid

    try:
        res = services.process_gate_event(request.POST.get("event_id") or uuid.uuid4().hex, request.POST.get("tag_uid"),
                                          lms_online=not bool(request.POST.get("offline")))
        if res.get("duplicate"):
            messages.info(request, "Duplicate event ignored (already processed).")
        elif res["alarm"]:
            messages.error(request, f"ALARM: {res['kind']} - accession {res.get('accession_no') or 'unknown'}. CCTV image saved and e-mail queued.")
        else:
            messages.success(request, "Authorised pass - no alarm.")
    except services.RfidError as err:
        messages.error(request, f"{err.message} [{err.code}]")
    return redirect("rfid_console")


@require_perm("inventory.run")
@require_POST
def ui_inventory(request):
    uids = re.split(r"[\s,;]+", request.POST.get("tags", ""))
    try:
        s = services.run_inventory(request.POST.get("shelf"), [u for u in uids if u], request.user)
        messages.success(request, f"Shelf {s.shelf}: expected {s.expected}, scanned {s.scanned}, missing {len(s.missing)}, misplaced {len(s.misplaced)}, unknown {len(s.unknown)}.")
    except services.RfidError as err:
        messages.error(request, f"{err.message} [{err.code}]")
    return redirect("rfid_console")


@require_perm("gate.view")
def cctv(request, name):
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.png", name):
        raise Http404
    path = settings.DATA_DIR / "cctv" / name
    if not path.exists():
        raise Http404
    return FileResponse(open(path, "rb"), content_type="image/png")


# ---------------------------------------------------------------- JSON API (device clients)
def _json(request):
    if len(request.body) > MAX_BODY:
        raise ValueError("body too large")
    data = json.loads(request.body or b"{}")
    if not isinstance(data, dict):
        raise ValueError("JSON object expected")
    return data


def _api(handler):
    @csrf_exempt
    @require_http_methods(["POST"])
    def wrapped(request):
        if not api_key_ok(request):
            return JsonResponse({"error": "invalid or missing X-API-Key"}, status=401)
        try:
            return JsonResponse(handler(_json(request)))
        except services.RfidError as err:
            return JsonResponse({"error": err.code, "message": err.message}, status=422)
        except (ValueError, KeyError) as err:
            return JsonResponse({"error": "BAD_REQUEST", "message": str(err)}, status=400)

    return wrapped


@_api
def api_tag(d):
    tag = services.tag_item(d["accession_no"], d["tag_uid"], d.get("operator", "api"), bool(d.get("retag")))
    return {"tag_uid": tag.tag_uid, "accession_no": tag.item.accession_no, "title": tag.item.biblio.title}


@_api
def api_gate(d):
    return services.process_gate_event(d.get("event_id"), d.get("tag_uid"), d.get("kind", "PASS"),
                                       lms_online=d.get("lms_online"), device_id=d.get("device_id", "gate-1"))


@_api
def api_inventory(d):
    s = services.run_inventory(d["shelf"], d.get("tags", []), d.get("operator", "api"))
    return {"session": s.pk, "expected": s.expected, "scanned": s.scanned, "missing": s.missing,
            "misplaced": s.misplaced, "unknown": s.unknown}


@csrf_exempt
def api_gate_cache(request):
    if not api_key_ok(request):
        return JsonResponse({"error": "invalid or missing X-API-Key"}, status=401)
    count = services.export_gate_cache()
    return HttpResponse(services.gate_cache_path().read_bytes(), content_type="application/json", headers={"X-Tag-Count": str(count)})
