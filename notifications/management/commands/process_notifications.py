from django.core.management.base import BaseCommand

from notifications import services


class Command(BaseCommand):
    help = "Send queued notifications through the configured providers (retries up to 3 times)."

    def handle(self, *args, **opts):
        self.stdout.write(str(services.process_queue()))
