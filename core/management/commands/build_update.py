from django.core.management.base import BaseCommand, CommandError

from core.ops import update


class Command(BaseCommand):
    help = "Build a signed offline update package from a payload folder."

    def add_arguments(self, parser):
        parser.add_argument("--release", required=True)
        parser.add_argument("--payload", required=True)
        parser.add_argument("--out", required=True)
        parser.add_argument("--notes", default="")

    def handle(self, *a, **o):
        try:
            p = update.build_package(o["release"], o["payload"], o["out"], o["notes"])
        except update.UpdateError as exc:
            raise CommandError(str(exc))
        self.stdout.write(f"Update package built: {p}")
