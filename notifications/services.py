"""Provider-neutral notifications. Swap MockProvider for a real SMTP/SMS gateway by registering a class."""
from abc import ABC, abstractmethod

from django.conf import settings
from django.utils import timezone

from notifications.models import Notification

MAX_ATTEMPTS = 3


class Provider(ABC):
    @abstractmethod
    def send(self, n):
        ...


class MockProvider(Provider):
    folder = {"email": "outbox", "sms": "sms_outbox", "print": "print_spool"}

    def send(self, n):
        if "fail" in n.recipient:  # lets tests/demos exercise the retry path
            raise RuntimeError("simulated provider outage")
        out = settings.DATA_DIR / self.folder[n.channel]
        out.mkdir(parents=True, exist_ok=True)
        (out / f"notification_{n.pk}.txt").write_text(f"To: {n.recipient}\nSubject: {n.subject}\n\n{n.body}\n", encoding="utf-8")


PROVIDERS = {"email": MockProvider, "sms": MockProvider, "print": MockProvider}


def queue(channel, recipient, subject, body, member=None):
    if member is not None and not getattr(member, f"notify_{channel}", True):
        return None  # per-user preference: channel disabled
    return Notification.objects.create(channel=channel, recipient=recipient, subject=subject[:200], body=body)


def process_queue():
    sent = failed = 0
    for n in Notification.objects.filter(status="QUEUED"):
        n.attempts += 1
        try:
            PROVIDERS[n.channel]().send(n)
            n.status, n.sent_at, n.last_error = "SENT", timezone.now(), ""
            sent += 1
        except Exception as exc:
            n.last_error = str(exc)[:200]
            if n.attempts >= MAX_ATTEMPTS:
                n.status = "FAILED"
                failed += 1
        n.save()
    return {"sent": sent, "failed": failed}


def overdue_notices():
    from circulation.models import Loan

    count = 0
    for loan in Loan.objects.filter(returned_at__isnull=True, due_at__lt=timezone.now()).select_related("member", "item__biblio"):
        m = loan.member
        body = f"Dear {m.name}, '{loan.item.biblio.title}' was due on {loan.due_at:%d %b %Y}. Please return or renew it."
        for channel, to in (("email", m.email), ("sms", m.phone), ("print", m.member_no)):
            if to and queue(channel, to, "Overdue notice", body, member=m):
                count += 1
    return count
