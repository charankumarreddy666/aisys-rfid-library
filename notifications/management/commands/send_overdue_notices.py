from django.core.management.base import BaseCommand

from notifications import services


class Command(BaseCommand):
    help = "Queue overdue notices honouring each member's channel preferences."

    def handle(self, *args, **opts):
        self.stdout.write(f"Queued {services.overdue_notices()} notice(s)")
