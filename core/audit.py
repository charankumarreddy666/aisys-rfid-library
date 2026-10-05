import logging

from core.logging_utils import mask
from core.models import AuditLog

logger = logging.getLogger("libsys.audit")


def log(actor, action, target="", detail=""):
    name = getattr(actor, "username", None) or str(actor or "system")
    entry = AuditLog.objects.create(actor=name[:150], action=action[:64], target=str(target)[:255], detail=mask(detail))
    logger.info("audit actor=%s action=%s target=%s", name, action, target)
    return entry
