from pathlib import Path

from django.core.management.base import BaseCommand

from core.ops import backup
from migration_tool import importer


class Command(BaseCommand):
    help = "AC 10 drill: back up, run a migration that crashes half-way, restore, and prove the original data is intact."

    def add_arguments(self, parser):
        parser.add_argument("file", help="spreadsheet to import (e.g. data/sample_20000.xlsx)")

    def handle(self, *args, **o):
        before = backup.fingerprint()
        self.stdout.write("1. Fingerprint of original data captured.")
        try:
            importer.run_import(Path(o["file"]), dry_run=False, actor="ac10-drill", simulate_failure=True)
        except importer.SimulatedFailure as exc:
            self.stdout.write(f"2. Migration crashed as planned: {exc}")
        after_fail = backup.fingerprint()
        self.stdout.write(f"3. Items now in DB: {after_fail['Item']['count']} (was {before['Item']['count']}) - data is partially changed.")
        latest = sorted(backup.backup_dir().glob("*pre-import-*.sqlite3"))[-1]
        backup.restore_backup(latest)
        restored = backup.fingerprint()
        ok = restored == before
        self.stdout.write(f"4. Restored from {latest.name}.")
        self.stdout.write("5. RESULT: original data intact - fingerprints match." if ok else "5. RESULT: MISMATCH - investigate!")
        if not ok:
            raise SystemExit(1)
