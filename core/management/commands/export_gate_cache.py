from django.core.management.base import BaseCommand

from rfid import services


class Command(BaseCommand):
    help = "Write the gate security-bit cache used when the LMS is offline."

    def handle(self, *a, **o):
        self.stdout.write(f"Gate cache written with {services.export_gate_cache()} tags -> {services.gate_cache_path()}")
