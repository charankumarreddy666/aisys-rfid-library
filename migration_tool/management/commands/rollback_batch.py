from django.core.management.base import BaseCommand

from migration_tool import importer


class Command(BaseCommand):
    help = "Remove every record created by one import batch."

    def add_arguments(self, parser):
        parser.add_argument("batch_id", type=int)

    def handle(self, *args, **o):
        b = importer.rollback_batch(o["batch_id"])
        self.stdout.write(f"Batch {b.pk}: {b.status}")
