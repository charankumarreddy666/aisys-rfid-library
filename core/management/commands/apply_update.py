import json

from django.core.management.base import BaseCommand, CommandError

from core.ops import update


class Command(BaseCommand):
    help = "Apply a signed offline update package (backs up DB + files first). Restart the server afterwards."

    def add_arguments(self, parser):
        parser.add_argument("package")
        parser.add_argument("--force", action="store_true", help="allow same/older version")

    def handle(self, *a, **o):
        try:
            res = update.apply_package(o["package"], force=o["force"])
        except (update.UpdateError, FileNotFoundError, KeyError) as exc:
            raise CommandError(f"Update refused: {exc}")
        self.stdout.write(json.dumps(res, indent=2))
        self.stdout.write("Update applied. Restart the web server. To undo: python manage.py rollback_update")
