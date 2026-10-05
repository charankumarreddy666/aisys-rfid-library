"""Backup / restore of the SQLite database with checksum manifest and a data fingerprint."""
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.db import connections

from core.version import current_version


class BackupError(Exception):
    pass


def db_path():
    return Path(connections["default"].settings_dict["NAME"])


def backup_dir():
    p = settings.DATA_DIR / "backups"
    p.mkdir(parents=True, exist_ok=True)
    return p


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fingerprint():
    """Hash of the core library records - used to PROVE data is unchanged after a restore."""
    from catalog.models import Biblio, Item
    from circulation.models import Fine, Loan
    from members.models import Member

    out = {}
    for model in (Biblio, Item, Member, Loan, Fine):
        rows = list(model.objects.order_by("pk").values())
        out[model.__name__] = {"count": len(rows), "sha256": hashlib.sha256(repr(rows).encode()).hexdigest()}
    return out


def create_backup(label="manual"):
    out = backup_dir() / f"{datetime.now():%Y%m%d-%H%M%S-%f}_{label}.sqlite3"
    src, dst = sqlite3.connect(db_path()), sqlite3.connect(out)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    manifest = {"file": out.name, "created": datetime.now().isoformat(), "sha256": sha256_file(out),
                "app_version": current_version(), "fingerprint": fingerprint()}
    out.with_suffix(".json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out


def restore_backup(path):
    path = Path(path)
    manifest_path = path.with_suffix(".json")
    if not path.exists():
        raise BackupError(f"Backup not found: {path}")
    if manifest_path.exists():
        expected = json.loads(manifest_path.read_text(encoding="utf-8"))["sha256"]
        if sha256_file(path) != expected:
            raise BackupError("Backup file checksum does not match its manifest - refusing to restore.")
    connections.close_all()
    src, dst = sqlite3.connect(path), sqlite3.connect(db_path())
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    connections.close_all()
    return path
