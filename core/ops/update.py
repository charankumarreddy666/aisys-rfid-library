"""Offline update / upgrade / patch packages: signed, checksummed, with automatic rollback snapshot.

Package layout (zip):  manifest.json, manifest.sig, payload/<relative paths>
"""
import hashlib
import hmac
import json
import shutil
import zipfile
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core.management import call_command

from core import audit, config
from core.ops import backup
from core.version import current_version

PROTECTED = ("data/", ".env", ".git/", "venv/")


class UpdateError(Exception):
    pass


def _key():
    key = config.get("UPDATE_SIGNING_KEY")
    if not key:
        raise UpdateError("UPDATE_SIGNING_KEY is not configured.")
    return key.encode()


def _sign(manifest_bytes):
    return hmac.new(_key(), manifest_bytes, hashlib.sha256).hexdigest()


def _vtuple(v):
    return tuple(int(x) for x in v.split("."))


def _safe(rel):
    p = PurePosixPath(rel)
    if p.is_absolute() or ".." in p.parts or rel.startswith(PROTECTED) or rel == "VERSION":
        raise UpdateError(f"Unsafe or protected path in package: {rel}")
    return p


def build_package(version, payload_dir, out_zip, notes=""):
    payload_dir, files = Path(payload_dir), []
    for f in sorted(p for p in payload_dir.rglob("*") if p.is_file()):
        rel = f.relative_to(payload_dir).as_posix()
        _safe(rel)
        files.append({"path": rel, "sha256": hashlib.sha256(f.read_bytes()).hexdigest()})
    manifest = json.dumps({"name": "library-update", "version": version, "requires": current_version(), "files": files,
                           "migrate": True, "notes": notes}, indent=2).encode()
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", manifest)
        z.writestr("manifest.sig", _sign(manifest))
        for f in files:
            z.write(payload_dir / f["path"], f"payload/{f['path']}")
    return Path(out_zip)


def verify_package(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        manifest_bytes, sig = z.read("manifest.json"), z.read("manifest.sig").decode().strip()
        if not hmac.compare_digest(sig, _sign(manifest_bytes)):
            raise UpdateError("Signature check failed - package is not authentic or was modified.")
        manifest = json.loads(manifest_bytes)
        for f in manifest["files"]:
            _safe(f["path"])
            if hashlib.sha256(z.read(f"payload/{f['path']}")).hexdigest() != f["sha256"]:
                raise UpdateError(f"Checksum mismatch for {f['path']}.")
    return manifest


def apply_package(zip_path, actor="cli", force=False):
    manifest = verify_package(zip_path)
    old, new = current_version(), manifest["version"]
    if not force and _vtuple(new) <= _vtuple(old):
        raise UpdateError(f"Package version {new} is not newer than installed {old}.")
    base = settings.BASE_DIR
    db_backup = backup.create_backup(f"pre-update-{new}")
    snap = settings.DATA_DIR / "rollback" / f"{old}_to_{new}"
    if snap.exists():
        shutil.rmtree(snap)
    (snap / "files").mkdir(parents=True)
    replaced, created = [], []
    for rel in [f["path"] for f in manifest["files"]] + ["VERSION"]:
        target = base / rel
        if target.exists():
            (snap / "files" / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, snap / "files" / rel)
            replaced.append(rel)
        else:
            created.append(rel)
    (snap / "rollback.json").write_text(json.dumps({"from": old, "to": new, "db_backup": str(db_backup),
                                                    "replaced": replaced, "created": created}, indent=2), encoding="utf-8")
    with zipfile.ZipFile(zip_path) as z:
        for f in manifest["files"]:
            dest = base / f["path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(z.read(f"payload/{f['path']}"))
    (base / "VERSION").write_text(new + "\n", encoding="utf-8")
    if manifest.get("migrate"):
        call_command("migrate", interactive=False, verbosity=0)
    audit.log(actor, "UPDATE_APPLIED", new, f"from {old}; snapshot {snap.name}")
    return {"from": old, "to": new, "snapshot": snap.name, "db_backup": db_backup.name}


def rollback(name=None, actor="cli"):
    root = settings.DATA_DIR / "rollback"
    candidates = sorted((p for p in root.glob("*_to_*") if p.is_dir() and not p.name.endswith(".rolledback") and (p / "rollback.json").exists()),
                        key=lambda p: p.stat().st_mtime) if root.exists() else []
    if not candidates:
        raise UpdateError("No rollback snapshot available.")
    snap = (root / name) if name else candidates[-1]
    info = json.loads((snap / "rollback.json").read_text(encoding="utf-8"))
    base = settings.BASE_DIR
    for rel in info["replaced"]:
        shutil.copy2(snap / "files" / rel, base / rel)
    for rel in info["created"]:
        if rel != "VERSION" and (base / rel).exists():
            (base / rel).unlink()
    backup.restore_backup(info["db_backup"])
    done = snap.with_name(snap.name + ".rolledback")
    if done.exists():
        shutil.rmtree(done)
    snap.rename(done)
    audit.log(actor, "UPDATE_ROLLED_BACK", info["to"], f"restored version {info['from']} and database")
    return info
