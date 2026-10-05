from django.core.management.base import BaseCommand, CommandError

from core.ops import backup


class Command(BaseCommand):
    help = "Restore the database from a backup file (checksum is verified first). Stop the web server first."

    def add_arguments(self, parser):
        parser.add_argument("file")

    def handle(self, *a, **o):
        try:
            backup.restore_backup(o["file"])
        except backup.BackupError as exc:
            raise CommandError(str(exc))
        self.stdout.write("Database restored.")
