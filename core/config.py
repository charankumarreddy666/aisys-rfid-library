"""Runtime configuration: Admin 'Setting' rows override environment values, which override defaults."""
import os
from decimal import Decimal

DEFAULTS = {
    "RFID_MODE": "mock",
    "LMS_ONLINE": "true",
    "LOAN_DAYS": "14",
    "RENEW_DAYS": "14",
    "MAX_RENEWALS": "2",
    "FINE_PER_DAY": "1.00",
    "FINE_LIMIT": "50.00",
    "GATE_ALERT_EMAIL": "security@library.example",
    "INTEROP_API_KEY": "",
    "UPDATE_SIGNING_KEY": "",
}


def get(key):
    from core.models import Setting

    row = Setting.objects.filter(key=key).first()
    if row is not None:
        return row.value
    return os.environ.get(key, DEFAULTS.get(key, ""))


def get_int(key):
    return int(get(key))


def get_decimal(key):
    return Decimal(get(key))


def get_bool(key):
    return get(key).strip().lower() in ("1", "true", "yes", "on")
