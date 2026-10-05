"""Device-neutral adapter interfaces and MOCK implementations.

To integrate a real vendor SDK: subclass the abstract class, then register it in `_REGISTRY`
for the matching RFID_MODE value. Nothing else in the application imports vendor code.
"""
import struct
import uuid
import zlib
from abc import ABC, abstractmethod

from django.conf import settings

from core import config


def record_event(device_type, kind, payload=None, device_id="", event_id=None):
    from rfid.models import DeviceEvent

    return DeviceEvent.objects.create(
        event_id=event_id or uuid.uuid4().hex, device_type=device_type, device_id=device_id, kind=kind, payload=payload or {}
    )


class StaffReader(ABC):
    @abstractmethod
    def read_tag(self, simulated_uid):
        """Return the UID presented to the staff-station reader."""


class HandheldReader(ABC):
    @abstractmethod
    def confirm(self, ok, tag_uid=""):
        """Give visible + audible confirmation for one read."""


class Gate(ABC):
    @abstractmethod
    def alarm(self, reason, tag_uid=""):
        ...


class SmartCardReader(ABC):
    @abstractmethod
    def authenticate(self, card_uid):
        """Return a username for a valid card, else None."""


class Printer(ABC):
    @abstractmethod
    def print_text(self, name, text):
        ...


class Camera(ABC):
    @abstractmethod
    def capture(self, event_id):
        ...


# ---------------------------------------------------------------- mocks
class MockStaffReader(StaffReader):
    def read_tag(self, simulated_uid):
        record_event("staff_reader", "TAG_READ", {"tag_uid": simulated_uid}, "staff-1")
        return simulated_uid


class MockHandheld(HandheldReader):
    def confirm(self, ok, tag_uid=""):
        record_event("handheld", "CONFIRM", {"tag_uid": tag_uid, "visible": "GREEN" if ok else "RED",
                                             "audible": "BEEP_OK" if ok else "BEEP_ERROR"}, "handheld-1")


class MockGate(Gate):
    def alarm(self, reason, tag_uid=""):
        record_event("gate", "ALARM", {"reason": reason, "tag_uid": tag_uid}, "gate-1")


class MockSmartCard(SmartCardReader):
    def authenticate(self, card_uid):
        from core.models import StaffCard

        card = StaffCard.objects.filter(card_uid=card_uid, active=True).select_related("user").first()
        record_event("smartcard", "AUTH_OK" if card else "AUTH_FAIL", {"card_uid": card_uid}, "card-1")
        return card.user.username if card else None


class MockPrinter(Printer):
    def print_text(self, name, text):
        spool = settings.DATA_DIR / "print_spool"
        spool.mkdir(parents=True, exist_ok=True)
        safe = "".join(c for c in name if c.isalnum() or c in "-_")[:60] or "job"
        path = spool / f"{safe}.txt"
        path.write_text(text, encoding="utf-8")
        record_event("printer", "PRINT", {"file": path.name}, "printer-1")
        return str(path)


def _png(width, height, rgb):
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class MockCamera(Camera):
    def capture(self, event_id):
        folder = settings.DATA_DIR / "cctv"
        folder.mkdir(parents=True, exist_ok=True)
        safe = "".join(c for c in event_id if c.isalnum() or c in "-_")[:60]
        path = folder / f"{safe}.png"
        path.write_bytes(_png(160, 90, (60, 70, 90)))  # placeholder frame
        record_event("camera", "CAPTURE", {"file": path.name}, "cam-1")
        return path.name


_REGISTRY = {
    "mock": {
        "staff_reader": MockStaffReader, "handheld": MockHandheld, "gate": MockGate,
        "smartcard": MockSmartCard, "printer": MockPrinter, "camera": MockCamera,
    }
}


def get_adapter(name):
    mode = config.get("RFID_MODE")
    try:
        return _REGISTRY[mode][name]()
    except KeyError:
        raise NotImplementedError(f"No '{name}' adapter registered for RFID_MODE={mode!r}. Implement it in rfid/adapters.py.")
