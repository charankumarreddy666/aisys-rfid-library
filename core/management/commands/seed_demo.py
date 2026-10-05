import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from catalog.models import Biblio, Item
from core.models import StaffCard
from core.roles import ensure_roles
from circulation.models import Fine
from members.models import Member
from rfid import services as rfid

BOOKS = [
    ("Clean Code", "Robert C. Martin", "9780132350884", "005.1 MAR", "A-01"),
    ("Introduction to Algorithms", "Thomas H. Cormen", "9780262033848", "005.1 COR", "A-01"),
    ("Head First Design Patterns", "Eric Freeman", "9780596007126", "005.12 FRE", "A-01"),
    ("The Pragmatic Programmer", "Andrew Hunt", "9780201616224", "005.1 HUN", "A-01"),
    ("Database System Concepts", "Abraham Silberschatz", "9780078022159", "005.74 SIL", "B-02"),
    ("Computer Networks", "Andrew Tanenbaum", "9780132126953", "004.6 TAN", "B-02"),
    ("Operating System Concepts", "Abraham Silberschatz", "9781118063330", "005.43 SIL", "B-02"),
    ("Encyclopaedia of Library Science", "Various", "", "020.3 ENC", "REF-01"),
]


class Command(BaseCommand):
    help = "Create SYNTHETIC demo users, members, catalogue items and RFID tags (idempotent)."

    def handle(self, *a, **o):
        ensure_roles()
        pwd = os.environ.get("DEMO_PASSWORD", "Demo#12345")
        User = get_user_model()
        users = [("admin", "Admin", "04AA000001"), ("librarian1", "Librarian", "04AA000002"),
                 ("circdesk1", "Circulation", "04AA000003"), ("viewer1", "Viewer", "04AA000004")]
        for name, role, card in users:
            u, created = User.objects.get_or_create(username=name, defaults={"email": f"{name}@library.example"})
            if created:
                u.set_password(pwd)
            if name == "admin":
                u.is_staff = u.is_superuser = True
            u.save()
            u.groups.set([Group.objects.get(name=role)])
            StaffCard.objects.get_or_create(user=u, defaults={"card_uid": card})
        for n in range(1, 9):
            Member.objects.get_or_create(member_no=f"M{n:04d}", defaults={
                "name": f"Demo Member {n}", "email": f"member{n}@library.example", "phone": f"90000000{n:02d}"})
        Member.objects.filter(member_no="M0003").update(is_blocked=True, block_reason="Library card suspended (demo)")
        m4 = Member.objects.get(member_no="M0004")
        if not m4.fines.exists():
            Fine.objects.create(member=m4, amount=75, reason="Overdue (demo, above the 50.00 limit)")
        for i, (title, author, isbn, call, shelf) in enumerate(BOOKS, start=1):
            b, _ = Biblio.objects.get_or_create(title=title, defaults={"author": author, "isbn": isbn, "call_number": call})
            acc = f"ACC{i:06d}"
            it, _ = Item.objects.get_or_create(accession_no=acc, defaults={
                "biblio": b, "barcode": f"BC{i:06d}", "shelf_location": shelf, "is_reference": shelf.startswith("REF")})
            rfid.tag_item(acc, f"E200{i:012X}", "seed")
        self.stdout.write(self.style.SUCCESS(
            "Demo data ready. Users: admin, librarian1, circdesk1, viewer1  (password = DEMO_PASSWORD, default Demo#12345)\n"
            "Smart cards: 04AA000001..04AA000004. Members M0001-M0008 (M0003 blocked, M0004 fines above limit).\n"
            "Items ACC000001-ACC000008, barcodes BC000001-BC000008, tags E200000000000001.. (hex)."))
