"""Structured (JSON) logging with masking of personal data."""
import json
import logging
import re
from datetime import datetime, timezone

_EMAIL = re.compile(r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+)")
_PHONE = re.compile(r"\+?\d{10,15}")


def mask(text):
    """Mask e-mail addresses and long phone-like numbers before they reach logs/audit."""
    text = "" if text is None else str(text)
    text = _EMAIL.sub(lambda m: f"{m.group(1)}***@{m.group(2)}", text)
    return _PHONE.sub(lambda m: "*" * (len(m.group(0)) - 2) + m.group(0)[-2:], text)


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": mask(record.getMessage()),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)
