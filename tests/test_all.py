"""Automated tests mapped to requirements (see docs/RTM.csv). Run:  python manage.py test tests -v 2"""
import json
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from catalog import search
from catalog.models import Biblio, Item
from circulation import services
from circulation.models import Fine, Loan, Transaction
from core import audit
from core.models import AuditLog, StaffCard
from core.ops import backup, update
from core.roles import ensure_roles
from interop import ncip, sip2
from members.models import Member
from migration_tool import importer
from notifications import services as notif
from notifications.models import Notification
from rfid import services as rfid
from rfid.models import GateEvent, RFIDTag

KEY = {"HTTP_X_API_KEY": "test-key"}


def make_world():
    ensure_roles()
    User = get_user_model()
    for name, role, card in (("admin", "Admin", "C1"), ("lib", "Librarian", "C2"), ("desk", "Circulation", "C3"), ("view", "Viewer", "C4")):
        u = User.objects.create_user(name, password="pw-Test-12345")
        u.groups.add(Group.objects.get(name=role))
        if role == "Admin":
            u.is_superuser = u.is_staff = True
            u.save()
        StaffCard.objects.create(user=u, card_uid=card)
    b = Biblio.objects.create(title="Test Driven Development", author="Kent Beck", isbn="9780321146533", call_number="005.1 BEC")
    ref = Biblio.objects.create(title="Reference Atlas")
    items = {
        "A": Item.objects.create(biblio=b, accession_no="ACC1", barcode="BC1", shelf_location="S1"),
        "B": Item.objects.create(biblio=b, accession_no="ACC2", barcode="BC2", shelf_location="S1"),
        "C": Item.objects.create(biblio=b, accession_no="ACC3", barcode="BC3", shelf_location="S2"),
        "R": Item.objects.create(biblio=ref, accession_no="REF1", barcode="BCR", shelf_location="REF", is_reference=True),
    }
    Member.objects.create(member_no="M1", name="Ok Member", email="ok@example.com")
    Member.objects.create(member_no="MB", name="Blocked", is_blocked=True, block_reason="card suspended")
    mf = Member.objects.create(member_no="MF", name="Fined")
    Fine.objects.create(member=mf, amount=Decimal("75.00"))
    return items


@override_settings()
class Base(TestCase):
    def setUp(self):
        import os
        os.environ["INTEROP_API_KEY"] = "test-key"
        os.environ["UPDATE_SIGNING_KEY"] = "test-signing"
        self.items = make_world()
        self.c = Client()


class CirculationTests(Base):  # FR04, AC03, AC04
    def test_checkout_checkin_renew_cycle_and_history(self):
        loan = services.checkout("BC1", "M1", "tester")
        self.assertEqual(Item.objects.get(barcode="BC1").status, "ON_LOAN")
        old_due = loan.due_at
        loan = services.renew("BC1", "tester")
        self.assertGreater(loan.due_at, old_due)
        services.checkin("BC1", "tester")
        self.assertEqual(Item.objects.get(barcode="BC1").status, "AVAILABLE")
        self.assertEqual(list(Transaction.objects.order_by("id").values_list("tx_type", flat=True)), ["CHECKOUT", "RENEW", "CHECKIN"])
        self.assertTrue(AuditLog.objects.filter(action="CHECKOUT_OK").exists())

    def test_reference_item_blocked(self):
        with self.assertRaises(services.CirculationError) as e:
            services.checkout("BCR", "M1", "tester")
        self.assertEqual(e.exception.code, "REFERENCE_ITEM")

    def test_blocked_member_and_fine_limit(self):
        with self.assertRaises(services.CirculationError) as e:
            services.checkout("BC1", "MB", "tester")
        self.assertEqual(e.exception.code, "MEMBER_BLOCKED")
        with self.assertRaises(services.CirculationError) as e:
            services.checkout("BC1", "MF", "tester")
        self.assertEqual(e.exception.code, "FINE_LIMIT_EXCEEDED")
        self.assertEqual(Transaction.objects.filter(success=False).count(), 2)  # denials are recorded too

    def test_fine_limit_is_configurable(self):
        from core.models import Setting
        Setting.objects.create(key="FINE_LIMIT", value="100")
        self.assertIsNotNone(services.checkout("BC1", "MF", "tester"))

    def test_overdue_checkin_creates_fine(self):
        loan = services.checkout("BC1", "M1", "tester")
        Loan.objects.filter(pk=loan.pk).update(due_at=timezone.now() - timezone.timedelta(days=3))
        _, fine = services.checkin("BC1", "tester")
        self.assertEqual(fine.amount, Decimal("3.00"))

    def test_renewal_limit(self):
        services.checkout("BC1", "M1", "t")
        services.renew("BC1", "t")
        services.renew("BC1", "t")
        with self.assertRaises(services.CirculationError):
            services.renew("BC1", "t")


class InteropTests(Base):  # FR03, AC03
    def _ncip(self, op, user="", item=""):
        xml = (f'<NCIPMessage xmlns="http://www.niso.org/2008/ncip"><{op}><UserId><UserIdentifierValue>{user}</UserIdentifierValue></UserId>'
               f'<ItemId><ItemIdentifierValue>{item}</ItemIdentifierValue></ItemId></{op}></NCIPMessage>')
        return self.c.post("/interop/ncip", xml, content_type="application/xml", **KEY).content.decode()

    def test_ncip_flow(self):
        self.assertIn("<DateDue>", self._ncip("CheckOutItem", "M1", "BC1"))
        self.assertIn("<DateForReturn>", self._ncip("RenewItem", item="BC1"))
        self.assertIn("CheckInItemResponse", self._ncip("CheckInItem", item="BC1"))
        self.assertEqual(Transaction.objects.filter(channel="NCIP", success=True).count(), 3)

    def test_ncip_problem_and_security(self):
        self.assertIn("MEMBER_BLOCKED", self._ncip("CheckOutItem", "MB", "BC1"))
        self.assertEqual(self.c.post("/interop/ncip", "<x/>", content_type="application/xml").status_code, 401)
        bad = '<!DOCTYPE a [<!ENTITY x "y">]><NCIPMessage/>'
        self.assertIn("Invalid Message Syntax", ncip.handle(bad))

    def test_sip2_flow(self):
        pad = " " * 4
        co = f"11NN20260101{pad}000000" + " " * 18 + "AOlib|AAM1|AB BC2|".replace("AB BC2", "ABBC2")
        self.assertTrue(sip2.handle(co).startswith("121"))
        self.assertTrue(sip2.handle("29N" + "N" + "20260101    000000" + " " * 18 + "AOlib|AAM1|ABBC2|").startswith("300N"))
        ci = "09N20260101    000000" + "20260101    000000" + "AOlib|ABBC2|"
        self.assertTrue(sip2.handle(ci).startswith("101"))
        deny = sip2.handle("11NN20260101    000000" + " " * 18 + "AOlib|AAMB|ABBC1|")
        self.assertTrue(deny.startswith("120"))


class RfidTests(Base):  # FR05-FR07, AC02, AC05, AC06
    def test_tagging_validates_and_links(self):  # AC02
        tag = rfid.tag_item("ACC1", "e200aabbccdd0001", "lib")
        self.assertEqual((tag.item.accession_no, tag.tag_uid), ("ACC1", "E200AABBCCDD0001"))
        with self.assertRaises(rfid.RfidError) as e:
            rfid.tag_item("NOPE", "E200AABBCCDD0002", "lib")
        self.assertEqual(e.exception.code, "ITEM_NOT_FOUND")
        with self.assertRaises(rfid.RfidError):
            rfid.tag_item("ACC2", "E200AABBCCDD0001", "lib")      # tag already used
        with self.assertRaises(rfid.RfidError):
            rfid.tag_item("ACC1", "E200AABBCCDD0009", "lib")      # needs explicit re-tag
        rfid.tag_item("ACC1", "E200AABBCCDD0009", "lib", retag=True)
        self.assertEqual(RFIDTag.objects.get(item__accession_no="ACC1").tag_uid, "E200AABBCCDD0009")
        with self.assertRaises(rfid.RfidError):
            rfid.tag_item("ACC2", "XYZ", "lib")

    def _tag_all(self):
        for i, acc in enumerate(["ACC1", "ACC2", "ACC3"], start=1):
            rfid.tag_item(acc, f"E200000000{i:06d}", "lib")

    def test_inventory_missing_and_misplaced(self):  # AC05
        self._tag_all()
        s = rfid.run_inventory("S1", ["E200000000000001", "E200000000000003", "E2FFFFFFFFFF0001"], "lib")
        self.assertEqual([m["accession_no"] for m in s.missing], ["ACC2"])
        self.assertEqual([m["accession_no"] for m in s.misplaced], ["ACC3"])
        self.assertEqual(s.unknown, ["E2FFFFFFFFFF0001"])
        from rfid.models import DeviceEvent
        kinds = {e.payload.get("visible") for e in DeviceEvent.objects.filter(kind="CONFIRM")}
        self.assertEqual(kinds, {"GREEN", "RED"})

    def test_gate_unauthorised_removal_and_duplicate(self):  # AC06
        self._tag_all()
        r = rfid.process_gate_event("EV1", "E200000000000001")
        self.assertTrue(r["alarm"])
        self.assertEqual(r["accession_no"], "ACC1")
        ge = GateEvent.objects.get(event_id="EV1")
        self.assertTrue(ge.cctv_image.endswith(".png"))
        self.assertEqual(Notification.objects.filter(channel="email", status="QUEUED").count(), 1)
        again = rfid.process_gate_event("EV1", "E200000000000001")   # duplicate event
        self.assertTrue(again["duplicate"])
        self.assertEqual(GateEvent.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 1)

    def test_checked_out_item_passes_gate(self):
        self._tag_all()
        services.checkout("BC1", "M1", "t")
        self.assertFalse(rfid.process_gate_event("EV2", "E200000000000001")["alarm"])
        services.checkin("BC1", "t")
        self.assertTrue(rfid.process_gate_event("EV3", "E200000000000001")["alarm"])

    def test_gate_works_with_lms_offline_cache(self):  # FR07
        self._tag_all()
        rfid.export_gate_cache()
        r = rfid.process_gate_event("EV4", "E200000000000002", lms_online=False)
        self.assertTrue(r["alarm"] and r["accession_no"] == "ACC2")
        self.assertTrue(GateEvent.objects.get(event_id="EV4").offline_mode)

    def test_gate_api_requires_key(self):
        self._tag_all()
        body = json.dumps({"event_id": "EV9", "tag_uid": "E200000000000001"})
        self.assertEqual(self.c.post("/rfid/api/gate", body, content_type="application/json").status_code, 401)
        r = self.c.post("/rfid/api/gate", body, content_type="application/json", **KEY)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["alarm"])


class NotificationTests(Base):  # FR09
    def test_preferences_and_retry(self):
        m = Member.objects.get(member_no="M1")
        m.notify_sms = False
        self.assertIsNone(notif.queue("sms", "9000000000", "s", "b", member=m))
        n = notif.queue("email", "fail@example.com", "s", "b", member=m)
        for _ in range(3):
            notif.process_queue()
        n.refresh_from_db()
        self.assertEqual((n.status, n.attempts), ("FAILED", 3))
        ok = notif.queue("email", "ok@example.com", "s", "b")
        notif.process_queue()
        ok.refresh_from_db()
        self.assertEqual(ok.status, "SENT")


class SearchAndUiTests(Base):  # FR02, FR08, AC07, AC08
    def test_realtime_index(self):
        self.assertEqual([b.title for b in search.search("kent")], ["Test Driven Development"])
        Biblio.objects.create(title="Brand New Quantum Title")
        self.assertEqual(len(search.search("quantum")), 1)

    def test_smartcard_login_and_rbac(self):  # AC07
        r = self.c.post("/login/smartcard/", {"card_uid": "C4"})   # Viewer
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.c.get("/circulation/").status_code, 403)
        self.assertEqual(self.c.get("/reports/").status_code, 200)
        self.assertEqual(self.c.get("/system/").status_code, 403)
        self.assertTrue(AuditLog.objects.filter(action="ACCESS_DENIED").exists())
        self.assertEqual(Client().post("/login/smartcard/", {"card_uid": "NOPE"}).status_code, 200)
        c2 = Client()
        c2.post("/login/smartcard/", {"card_uid": "C3"})        # Circulation role
        self.assertEqual(c2.get("/circulation/").status_code, 200)
        self.assertEqual(c2.get("/reports/").status_code, 403)

    def test_dashboard_reports_and_csv(self):  # AC08
        services.checkout("BC1", "M1", "lib")
        rfid.tag_item("ACC2", "E200000000000002", "lib")
        self.c.login(username="admin", password="pw-Test-12345")
        self.assertEqual(self.c.get("/").status_code, 200)
        for t in ("tagged_items", "members", "circulation", "operators", "rfid_clients", "gate_events", "fines"):
            self.assertEqual(self.c.get(f"/reports/?type={t}").status_code, 200, t)
        r = self.c.get("/reports/?type=circulation&operator=lib&from=2020-01-01&format=csv")
        self.assertIn("CHECKOUT", r.content.decode())
        Member.objects.create(member_no="=1+1", name="=cmd")
        csv_text = self.c.get("/reports/?type=members&format=csv").content.decode()
        self.assertIn("'=1+1", csv_text)

    def test_health_and_opac_public(self):
        self.assertEqual(self.c.get("/health").json()["status"], "ok")
        self.assertContains(self.c.get("/opac/?q=driven"), "Test Driven Development")

    def test_audit_log_is_append_only(self):
        e = audit.log("x", "A")
        with self.assertRaises(PermissionError):
            e.delete()
        e.detail = "changed"
        with self.assertRaises(PermissionError):
            e.save()

    def test_log_masking(self):
        e = audit.log("x", "A", "", "mail jane.doe@example.com phone 9876543210")
        self.assertNotIn("jane.doe", e.detail)
        self.assertNotIn("98765432", e.detail)


class MigrationTests(TransactionTestCase):  # FR10, AC01
    def setUp(self):
        import os
        os.environ["UPDATE_SIGNING_KEY"] = "test-signing"
        self.tmp = Path(tempfile.mkdtemp())
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["accession_no", "title", "author", "isbn", "call_number", "publisher", "year", "shelf_location", "is_reference"])
        ws.append(["N1", "Good One", "A", "9780132350884", "1", "P", 2001, "S1", "no"])
        ws.append(["N2", "Good Two", "A", "", "2", "P", 2002, "S1", "yes"])
        ws.append(["N3", "", "A", "", "", "", "", "", ""])                       # invalid: no title
        ws.append(["N1", "Dup of one", "A", "", "", "", "", "", ""])             # duplicate in file
        ws.append(["EXIST", "Dup of existing", "A", "", "", "", "", "", ""])     # duplicate of existing DB record
        ws.append(["N6", "Bad year", "A", "", "", "", 2999, "", ""])
        self.file = self.tmp / "t.xlsx"
        wb.save(self.file)
        b = Biblio.objects.create(title="Existing")
        Item.objects.create(biblio=b, accession_no="EXIST", barcode="EXIST")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_dry_run_commit_reconcile_rollback(self):
        before = backup.fingerprint()
        dry = importer.run_import(self.file, dry_run=True)
        self.assertEqual((dry.total_rows, dry.valid_rows, dry.rejected_rows, dry.duplicate_rows), (6, 2, 2, 2))
        self.assertEqual(Item.objects.count(), 1)
        b = importer.run_import(self.file, dry_run=False)
        rec = importer.reconcile(b)
        self.assertTrue(rec["source_equals_valid_plus_rejected_plus_duplicates"] and rec["target_matches_migrated"])
        self.assertEqual(Item.objects.count(), 3)
        self.assertTrue(Item.objects.get(accession_no="N2").is_reference)
        self.assertTrue(b.backup_file)
        self.assertEqual(len(search.search("Good")), 2)
        importer.rollback_batch(b.pk)
        self.assertEqual(backup.fingerprint(), before)       # existing data untouched
        self.assertEqual(len(search.search("Good")), 0)

    def test_failed_migration_then_restore_proves_data_intact(self):  # AC10
        before = backup.fingerprint()
        with self.assertRaises(importer.SimulatedFailure):
            importer.run_import(self.file, dry_run=False, simulate_failure=True)
        self.assertNotEqual(backup.fingerprint(), before)    # partial load happened
        latest = sorted(backup.backup_dir().glob("*pre-import-*.sqlite3"))[-1]
        backup.restore_backup(latest)
        self.assertEqual(backup.fingerprint(), before)

    def test_corrupt_backup_is_refused(self):
        p = backup.create_backup("x")
        p.write_bytes(p.read_bytes() + b"tamper")
        with self.assertRaises(backup.BackupError):
            backup.restore_backup(p)


class UpdateTests(TransactionTestCase):  # FR12, AC09
    def setUp(self):
        import os
        from django.conf import settings
        os.environ["UPDATE_SIGNING_KEY"] = "test-signing"
        self.tmp = Path(tempfile.mkdtemp())
        self.base = settings.BASE_DIR
        self.version_before = (self.base / "VERSION").read_text()
        self.target = self.base / "docs" / "_test_update_file.txt"
        (self.tmp / "payload" / "docs").mkdir(parents=True)
        (self.tmp / "payload" / "docs" / "_test_update_file.txt").write_text("new content")

    def tearDown(self):
        (self.base / "VERSION").write_text(self.version_before)
        if self.target.exists():
            self.target.unlink()
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(Path(self.base / "data" / "rollback"), ignore_errors=True)

    def test_apply_then_rollback(self):
        self.target.write_text("old content")
        ver = self.version_before.strip()
        newer = ".".join([ver.split(".")[0], ver.split(".")[1], str(int(ver.split(".")[2]) + 1)])
        pkg = update.build_package(newer, self.tmp / "payload", self.tmp / "u.zip")
        res = update.apply_package(pkg)
        self.assertEqual(res["to"], newer)
        self.assertEqual(self.target.read_text(), "new content")
        self.assertEqual((self.base / "VERSION").read_text().strip(), newer)
        update.rollback()
        self.assertEqual(self.target.read_text(), "old content")
        self.assertEqual((self.base / "VERSION").read_text().strip(), ver)

    def test_rollback_ignores_already_rolled_back_snapshots(self):  # DEF-002 regression
        self.target.write_text("old content")
        ver = self.version_before.strip()
        newer = ".".join([ver.split(".")[0], ver.split(".")[1], str(int(ver.split(".")[2]) + 1)])
        pkg = update.build_package(newer, self.tmp / "payload", self.tmp / "u.zip")
        update.apply_package(pkg)
        update.rollback()
        with self.assertRaises(update.UpdateError):
            update.rollback()   # nothing left to roll back; must NOT reuse the finished snapshot

    def test_tampered_package_rejected(self):
        import zipfile
        pkg = update.build_package("9.9.9", self.tmp / "payload", self.tmp / "u.zip")
        bad = self.tmp / "bad.zip"
        with zipfile.ZipFile(pkg) as zin, zipfile.ZipFile(bad, "w") as zout:
            for n in zin.namelist():
                zout.writestr(n, b"evil" if n.startswith("payload/") else zin.read(n))
        with self.assertRaises(update.UpdateError):
            update.apply_package(bad)

    def test_same_version_and_unsafe_path_refused(self):
        pkg = update.build_package(self.version_before.strip(), self.tmp / "payload", self.tmp / "u.zip")
        with self.assertRaises(update.UpdateError):
            update.apply_package(pkg)
        (self.tmp / "payload" / ".env").write_text("X=1")
        with self.assertRaises(update.UpdateError):
            update.build_package("9.9.9", self.tmp / "payload", self.tmp / "v.zip")
        (self.tmp / "payload" / ".env").unlink()
