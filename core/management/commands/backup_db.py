from django.core.management.base import BaseCommand

from core.ops import backup


class Command(BaseCommand):
    help = "Create a verified database backup (file + checksum manifest) in data/backups."

    def add_arguments(self, parser):
        parser.add_argument("--label", default="manual")

    def handle(self, *a, **o):
        self.stdout.write(f"Backup written: {backup.create_backup(o['label'])}")
