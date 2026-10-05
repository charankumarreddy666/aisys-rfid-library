import json

from django.core.management.base import BaseCommand, CommandError

from core.ops import update


class Command(BaseCommand):
    help = "Undo the most recent update: restores previous files, VERSION and database."

    def add_arguments(self, parser):
        parser.add_argument("--name", help="snapshot folder name, e.g. 1.0.0_to_1.0.1")

    def handle(self, *a, **o):
        try:
            info = update.rollback(o.get("name"))
        except update.UpdateError as exc:
            raise CommandError(str(exc))
        self.stdout.write(json.dumps({"rolled_back_from": info["to"], "restored": info["from"]}, indent=2))
