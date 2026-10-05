"""RFID workflows: tagging, gate events (idempotent, offline-capable), shelf inventory."""
import json
import re

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from catalog.models import Item
from core import audit, config
from rfid.adapters import get_adapter, record_event
from rfid.models import DeviceEvent, GateEvent, InventorySession, RFIDTag, TagEvent

UID_RE = re.compile(r"^[0-9A-F]{8,32}$")


class RfidError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def normalize_uid(uid):
    value = (uid or "").strip().upper()
    if not UID_RE.match(value):
        raise RfidError("BAD_TAG_UID", "Tag UID must be 8-32 hexadecimal characters.")
    return value


@transaction.atomic
def tag_item(accession_no, tag_uid, actor, retag=False):
    uid = normalize_uid(tag_uid)
    item = Item.objects.select_related("biblio").filter(accession_no=(accession_no or "").strip()).first()
    if item is None:
        raise RfidError("ITEM_NOT_FOUND", "No catalogue record with that accession number - catalogue the item first.")
    other = RFIDTag.objects.filter(tag_uid=uid).select_related("item").first()
    if other and other.item_id != item.id:
        raise RfidError("TAG_IN_USE", f"Tag already linked to {other.item.accession_no}.")
    current = RFIDTag.objects.filter(item=item).first()
    name = getattr(actor, "username", str(actor))
    if current and current.tag_uid == uid:
        return current
    if current and not retag:
        raise RfidError("ITEM_ALREADY_TAGGED", f"Item already has tag {current.tag_uid}. Use re-tag to replace it.")
    if current:
        old, current.tag_uid = current.tag_uid, uid
        current.tagged_by = name
        current.save()
        TagEvent.objects.create(tag_uid=uid, event="RETAGGED", detail=f"replaced {old}", actor=name)
        audit.log(actor, "TAG_REPLACED", item.accession_no, f"{old} -> {uid}")
        return current
    tag = RFIDTag.objects.create(tag_uid=uid, item=item, tagged_by=name, security_bit=item.status != Item.Status.ON_LOAN)
    TagEvent.objects.create(tag_uid=uid, event="TAGGED", detail=item.accession_no, actor=name)
    audit.log(actor, "TAG_ASSIGNED", item.accession_no, uid)
    return tag


# ------------------------------------------------------------------ gate
def gate_cache_path():
    return settings.DATA_DIR / "gate_cache.json"


def export_gate_cache():
    """Snapshot of tag security state, used by gates when the LMS is unreachable."""
    data = {t.tag_uid: {"secured": t.security_bit, "accession": t.item.accession_no}
            for t in RFIDTag.objects.select_related("item").iterator()}
    gate_cache_path().write_text(json.dumps({"generated": timezone.now().isoformat(), "tags": data}), encoding="utf-8")
    return len(data)


def _lookup_online(uid):
    tag = RFIDTag.objects.select_related("item").filter(tag_uid=uid).first()
    return None if tag is None else {"secured": tag.security_bit, "accession": tag.item.accession_no}


def _lookup_offline(uid):
    path = gate_cache_path()
    if not path.exists():
        raise RfidError("NO_GATE_CACHE", "LMS offline and no gate cache present. Run export_gate_cache while online.")
    return json.loads(path.read_text(encoding="utf-8"))["tags"].get(uid)


def process_gate_event(event_id, tag_uid=None, kind="PASS", lms_online=None, device_id="gate-1"):
    """Idempotent: re-sending the same event_id returns the first result without side effects."""
    event_id = (event_id or "").strip()[:64]
    if not event_id:
        raise RfidError("BAD_EVENT", "event_id is required.")
    online = config.get_bool("LMS_ONLINE") if lms_online is None else lms_online
    try:
        with transaction.atomic():
            DeviceEvent.objects.create(event_id=event_id, device_type="gate", device_id=device_id, kind=kind,
                                       payload={"tag_uid": tag_uid, "lms_online": online})
    except IntegrityError:
        prior = GateEvent.objects.filter(event_id=event_id).first()
        return {"duplicate": True, "kind": prior.kind if prior else None, "alarm": prior.alarm if prior else False}

    if kind == "FOOTFALL":
        GateEvent.objects.create(event_id=event_id, kind=GateEvent.Kind.FOOTFALL, offline_mode=not online)
        return {"duplicate": False, "kind": "FOOTFALL", "alarm": False}

    uid = normalize_uid(tag_uid)
    info = _lookup_online(uid) if online else _lookup_offline(uid)
    accession = info["accession"] if info else ""
    if info is None:
        verdict = GateEvent.Kind.UNKNOWN
    elif info["secured"]:
        verdict = GateEvent.Kind.UNAUTHORISED
    else:
        verdict = GateEvent.Kind.AUTHORISED
    alarm = verdict != GateEvent.Kind.AUTHORISED
    image = ""
    if alarm:
        get_adapter("gate").alarm(verdict.value, uid)
        image = get_adapter("camera").capture(event_id)
        from notifications.services import queue

        queue("email", config.get("GATE_ALERT_EMAIL"), f"Gate alarm: {verdict.label}",
              f"{verdict.label}. Tag {uid}, accession {accession or 'n/a'}, event {event_id}, CCTV {image}.")
    else:
        RFIDTag.objects.filter(tag_uid=uid).update(last_seen=timezone.now())
    ge = GateEvent.objects.create(event_id=event_id, kind=verdict, tag_uid=uid, accession_no=accession, alarm=alarm,
                                  cctv_image=image, offline_mode=not online)
    audit.log(device_id, "GATE_EVENT", accession or uid, f"{verdict.value} offline={not online}")
    return {"duplicate": False, "kind": ge.kind, "alarm": alarm, "accession_no": accession, "cctv_image": image}


# ------------------------------------------------------------- inventory
@transaction.atomic
def run_inventory(shelf, scanned_uids, actor):
    shelf = (shelf or "").strip()
    if not shelf:
        raise RfidError("BAD_SHELF", "Shelf is required.")
    scanned = {normalize_uid(u) for u in scanned_uids if str(u).strip()}
    expected = {t.tag_uid: t for t in RFIDTag.objects.select_related("item", "item__biblio")
                .filter(item__shelf_location=shelf, item__status=Item.Status.AVAILABLE)}
    present = {t.tag_uid: t for t in RFIDTag.objects.select_related("item", "item__biblio").filter(tag_uid__in=scanned)}
    handheld = get_adapter("handheld")
    missing = [{"tag_uid": u, "accession_no": t.item.accession_no, "title": t.item.biblio.title}
               for u, t in sorted(expected.items()) if u not in scanned]
    misplaced = [{"tag_uid": u, "accession_no": t.item.accession_no, "title": t.item.biblio.title,
                  "belongs_on": t.item.shelf_location}
                 for u, t in sorted(present.items()) if t.item.shelf_location != shelf]
    unknown = sorted(u for u in scanned if u not in present)
    for uid in sorted(scanned):
        ok = uid in present and present[uid].item.shelf_location == shelf
        handheld.confirm(ok, uid)
    now = timezone.now()
    RFIDTag.objects.filter(tag_uid__in=list(present)).update(last_seen=now)
    session = InventorySession.objects.create(shelf=shelf, started_by=getattr(actor, "username", str(actor)),
                                              expected=len(expected), scanned=len(scanned),
                                              missing=missing, misplaced=misplaced, unknown=unknown)
    record_event("handheld", "SESSION_DONE", {"session": session.pk, "missing": len(missing), "misplaced": len(misplaced)}, "handheld-1")
    audit.log(actor, "INVENTORY_RUN", shelf, f"expected={len(expected)} scanned={len(scanned)} missing={len(missing)} misplaced={len(misplaced)}")
    return session
