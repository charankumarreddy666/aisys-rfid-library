import json

from django.core.management.base import BaseCommand, CommandError

from migration_tool import importer


class Command(BaseCommand):
    help = "Import an .xlsx/.csv file. Default is a DRY RUN; add --commit to write (a backup is taken first)."

    def add_arguments(self, parser):
        parser.add_argument("file")
        parser.add_argument("--commit", action="store_true", help="really migrate valid rows")
        parser.add_argument("--simulate-failure", action="store_true", help="crash mid-load (for the restore drill)")

    def handle(self, *args, **o):
        try:
            batch = importer.run_import(o["file"], dry_run=not o["commit"], actor="cli", simulate_failure=o["simulate_failure"])
        except FileNotFoundError:
            raise CommandError(f"File not found: {o['file']}")
        self.stdout.write(json.dumps(importer.reconcile(batch), indent=2))
        self.stdout.write(f"Reports are in the data/reports folder (batch_{batch.pk}_*).")
