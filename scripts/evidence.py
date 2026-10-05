"""Automated evidence run for the AISYS SOP: lint, tests, migration, AC01-AC10 checks, screenshots, video, report.

Runs against an ISOLATED database in evidence/run_data (your real data/ folder is never touched).
Usage:  python scripts/evidence.py [--no-screenshots] [--skip-offline-install] [--port 8765]
"""
import argparse
import csv
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
ap = argparse.ArgumentParser()
ap.add_argument("--no-screenshots", action="store_true")
ap.add_argument("--skip-offline-install", action="store_true")
ap.add_argument("--port", type=int, default=8765)
args, _ = ap.parse_known_args()

OUT = ROOT / "evidence"
LOGS, SHOTS, RUN = OUT / "logs", OUT / "screenshots", OUT / "run_data"
for d in (LOGS, SHOTS):
    shutil.rmtree(d, ignore_errors=True)
shutil.rmtree(RUN, ignore_errors=True)
for d in (LOGS, SHOTS, RUN):
    d.mkdir(parents=True, exist_ok=True)

KEY = "evidence-interop-key"
ENV = dict(os.environ, DATA_DIR=str(RUN), INTEROP_API_KEY=KEY, UPDATE_SIGNING_KEY="evidence-signing-key",
           DEMO_PASSWORD="Demo#12345", DEBUG="true", SECRET_KEY="evidence-secret-key-" + "x" * 30,
           LMS_ONLINE="true", PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
PY = sys.executable
BASE = f"http://127.0.0.1:{args.port}"
STEPS, CHECKS, PERF, SHOT_LIST = [], [], [], []
T0 = time.time()
_n = [0]


def run(title, cmd, req="", warn_only=False, env=None, timeout=1800, log=None):
    """Run a subprocess, store its output in evidence/logs, record PASS/FAIL/WARN."""
    _n[0] += 1
    name = f"{_n[0]:02d}_{re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')}.txt"
    t = time.time()
    print(f"[{_n[0]:02d}] {title} ...", flush=True)
    try:
        p = subprocess.run(cmd, cwd=ROOT, env=env or ENV, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        out, rc = (p.stdout or "") + (("\n--- stderr ---\n" + p.stderr) if p.stderr.strip() else ""), p.returncode
    except FileNotFoundError as exc:
        out, rc = f"command not found: {exc}", 127
    except subprocess.TimeoutExpired:
        out, rc = "timeout", 124
    (LOGS / (log or name)).write_text(f"$ {' '.join(map(str, cmd))}\n\n{out}", encoding="utf-8")
    status = "PASS" if rc == 0 else ("WARN" if warn_only else "FAIL")
    STEPS.append({"title": title, "req": req, "status": status, "secs": round(time.time() - t, 1), "log": f"logs/{log or name}"})
    print(f"     -> {status} ({STEPS[-1]['secs']}s)", flush=True)
    return rc, out


def check(ac, text, ok, detail=""):
    CHECKS.append({"ac": ac, "text": text, "ok": bool(ok), "detail": str(detail)[:300]})
    print(f"     [{'ok' if ok else 'XX'}] {ac}: {text}", flush=True)
    return ok


def manage(*a, **kw):
    return run(kw.pop("title", "manage.py " + " ".join(a)), [PY, "manage.py", *a], **kw)


def json_block(text):
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {}


# ------------------------------------------------------------------ 1. environment + quality gates
django_ver = subprocess.run([PY, "-c", "import django;print(django.get_version())"], capture_output=True, text=True).stdout.strip()
(LOGS / "00_environment.txt").write_text(f"Python {sys.version}\nDjango {django_ver}\nPlatform {sys.platform}\nRun started {datetime.now():%Y-%m-%d %H:%M:%S}\n", encoding="utf-8")
STEPS.append({"title": "Environment captured", "req": "NFR03", "status": "PASS", "secs": 0, "log": "logs/00_environment.txt"})
run("Lint (ruff)", [PY, "-m", "ruff", "check", "."], "NFR06", warn_only=True)
run("Dependency vulnerability scan (pip-audit)", [PY, "-m", "pip_audit", "-r", "requirements.txt"], "NFR02/NFR04", warn_only=True)
run("Software bill of materials", [PY, "scripts/gen_sbom.py"], "NFR04")
manage("makemigrations", "--check", "--dry-run", title="Migrations are up to date", req="NFR06")
TEST_ENV = dict(ENV, DATA_DIR=str(OUT / "test_data"))
shutil.rmtree(OUT / "test_data", ignore_errors=True)
(OUT / "test_data").mkdir(parents=True)
rc, out = manage("test", "tests", "-v", "2", title="Automated test suite", req="NFR05", env=TEST_ENV)
shutil.rmtree(OUT / "test_data", ignore_errors=True)
m = re.search(r"Ran (\d+) tests? in ([\d.]+)s", out)
check("TESTS", f"Automated tests passed ({m.group(1) if m else '?'} tests)", rc == 0 and "OK" in out)

# ------------------------------------------------------------------ 2. evidence database
manage("migrate", "-v", "0", title="Create evidence database", req="FR11")
manage("seed_demo", title="Seed synthetic demo data", req="Stage 3")
run("Generate 20,000-row synthetic spreadsheet", [PY, "scripts/gen_sample_data.py", str(RUN / "sample_20000.xlsx"), "20000"], "FR10")
sample = str(RUN / "sample_20000.xlsx")


def shell(code):
    return subprocess.run([PY, "manage.py", "shell", "-c", code], cwd=ROOT, env=ENV, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip().splitlines()[-1:]


items_before = shell("from catalog.models import Item;print(Item.objects.count())")

# ------------------------------------------------------------------ 3. AC01 migration
t = time.time()
rc, out = manage("import_spreadsheet", sample, title="AC01 dry-run import (nothing written)", req="FR10")
PERF.append(("20,000-row dry run (stage + validate)", round(time.time() - t, 1)))
dry = json_block(out)
check("AC01", "Dry run wrote nothing", shell("from catalog.models import Item;print(Item.objects.count())") == items_before)
t = time.time()
rc, out = manage("import_spreadsheet", sample, "--commit", title="AC01 committed import with reconciliation", req="FR10")
PERF.append(("20,000-row committed import (incl. backup + reconcile)", round(time.time() - t, 1)))
res = json_block(out)
check("AC01", "Invalid rows rejected", res.get("rejected", 0) > 0, f"rejected={res.get('rejected')}")
check("AC01", "Duplicates identified", res.get("duplicates", 0) > 0, f"duplicates={res.get('duplicates')}")
check("AC01", "Source = migrated + rejected + duplicates", res.get("source_equals_valid_plus_rejected_plus_duplicates") is True and res.get("source_rows") == 20000,
      f"{res.get('source_rows')} = {res.get('migrated')} + {res.get('rejected')} + {res.get('duplicates')}")
check("AC01", "Target count matches migrated count", res.get("target_matches_migrated") is True, res.get("target_items_in_batch"))
batch_id = res.get("batch", 0)
reports = RUN / "reports"
for f in reports.glob(f"batch_{batch_id}_*"):
    shutil.copy(f, LOGS / f.name)
code = ("import time;from catalog import search;t=time.time();[search.search('fundamentals volume %d' % n) for n in range(100,160)];"
        "print(round((time.time()-t)/60*1000,1))")
lat = shell(code)
PERF.append(("Full-text search latency with 19,000+ titles (ms/query)", lat[0] if lat else "n/a"))
rc, out = manage("rollback_batch", str(batch_id), title="AC01 rollback of the batch", req="FR10")
after = shell("from catalog.models import Item;print(Item.objects.count())")
check("AC01", "Rollback restores original item count", after == items_before, f"{items_before} -> {after}")

# ------------------------------------------------------------------ 4. AC10 restore drill
rc, out = manage("demo_failed_migration", sample, title="AC10 failed migration then restore from backup", req="NFR01")
check("AC10", "Partial data appeared after the crash", "partially changed" in out)
check("AC10", "Restore proves original data intact", "original data intact" in out and rc == 0)

# ------------------------------------------------------------------ 5. AC09 offline update + rollback
keep = {p: p.read_bytes() for p in (ROOT / "VERSION", ROOT / "templates" / "_banner.html")}
try:
    v0 = (ROOT / "VERSION").read_text().strip()
    pkg = str(RUN / "update_1.0.1.zip")
    manage("build_update", "--release", "1.0.1", "--payload", "update_payload_1.0.1", "--out", pkg, "--notes", "Evidence run patch", title="AC09 build signed update package", req="FR12")
    rc, out = manage("apply_update", pkg, "--force", title="AC09 apply offline update", req="FR12")
    check("AC09", "Update applied (version changed)", rc == 0 and (ROOT / "VERSION").read_text().strip() == "1.0.1", (ROOT / "VERSION").read_text().strip())
    rc, out = manage("rollback_update", title="AC09 roll back the update", req="FR12")
    check("AC09", "Rollback restored previous version", rc == 0 and (ROOT / "VERSION").read_text().strip() == v0, (ROOT / "VERSION").read_text().strip())
finally:
    for p, data in keep.items():
        p.write_bytes(data)

if not args.skip_offline_install:
    wheels = ROOT / "wheels"
    rc, _ = run("AC09 download wheels (one-time, needs internet)", [PY, "-m", "pip", "download", "-r", "requirements.txt", "-d", str(wheels), "-q"], "FR12", warn_only=True)
    if rc == 0:
        venv = OUT / "offline_venv"
        shutil.rmtree(venv, ignore_errors=True)
        run("AC09 create clean virtual environment", [PY, "-m", "venv", str(venv)], "NFR03")
        vpy = str(venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
        rc, out = run("AC09 install with --no-index (no internet)", [vpy, "-m", "pip", "install", "--no-index", f"--find-links={wheels}", "-r", "requirements.txt"], "FR12")
        rc2, out2 = run("AC09 offline-installed app passes system check", [vpy, "manage.py", "check"], "FR12")
        check("AC09", "Installs from local wheels without internet", rc == 0 and rc2 == 0)
    else:
        check("AC09", "Installs from local wheels without internet", False, "could not download wheels (no internet for the one-time prepare step)")

# ------------------------------------------------------------------ 6. live server
srv_log = open(LOGS / "server.log", "w", encoding="utf-8")
server = subprocess.Popen([PY, "manage.py", "runserver", f"127.0.0.1:{args.port}", "--noreload"], cwd=ROOT, env=ENV, stdout=srv_log, stderr=subprocess.STDOUT)


def http(method, path, body=None, headers=None, key=True, raw=False):
    h = dict(headers or {})
    if key:
        h["X-API-Key"] = KEY
    data = body.encode() if isinstance(body, str) else body
    req = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            txt = r.read().decode("utf-8", "replace")
            return r.status, txt
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


up = False
for _ in range(60):
    try:
        up = urllib.request.urlopen(BASE + "/health", timeout=2).status == 200
        break
    except Exception:
        time.sleep(0.5)
STEPS.append({"title": "Start web server", "req": "NFR07", "status": "PASS" if up else "FAIL", "secs": 0, "log": "logs/server.log"})
api_log = []


def api(label, method, path, body=None, **kw):
    code, txt = http(method, path, body, **kw)
    api_log.append(f"### {label}\n{method} {path}\n{body or ''}\n-> HTTP {code}\n{txt}\n")
    return code, txt


try:
    if up:
        code, txt = api("Health", "GET", "/health", key=False)
        check("NFR07", "Health endpoint reports ok", code == 200 and '"ok"' in txt, txt[:120])

        def ncip(op, user="", item=""):
            return api(f"NCIP {op}", "POST", "/interop/ncip",
                       f'<NCIPMessage xmlns="http://www.niso.org/2008/ncip"><{op}><UserId><UserIdentifierValue>{user}</UserIdentifierValue></UserId>'
                       f'<ItemId><ItemIdentifierValue>{item}</ItemIdentifierValue></ItemId></{op}></NCIPMessage>')[1]

        check("NFR02", "API without key is refused (401)", api("No key", "POST", "/interop/ncip", "<x/>", key=False)[0] == 401)
        check("AC03", "NCIP CheckOutItem returns due date", "<DateDue>" in ncip("CheckOutItem", "M0002", "BC000005"))
        check("AC03", "NCIP RenewItem returns new date", "<DateForReturn>" in ncip("RenewItem", "", "BC000005"))
        check("AC03", "NCIP CheckInItem succeeds", "CheckInItemResponse" in ncip("CheckInItem", "", "BC000005") and "Problem" not in ncip("LookupItem", "", "BC000005"))
        check("AC04", "NCIP denies blocked member", "MEMBER_BLOCKED" in ncip("CheckOutItem", "M0003", "BC000006"))
        check("AC04", "NCIP denies reference item", "REFERENCE_ITEM" in ncip("CheckOutItem", "M0001", "BC000008"))
        check("AC04", "NCIP denies member over fine limit", "FINE_LIMIT_EXCEEDED" in ncip("CheckOutItem", "M0004", "BC000006"))
        d1, d2 = "20261005    000000", "                  "
        s1 = api("SIP2 checkout (11)", "POST", "/interop/sip2", f"11NN{d1}{d2}AOlib|AAM0002|ABBC000006|")[1]
        s2 = api("SIP2 renew (29)", "POST", "/interop/sip2", f"29NN{d1}{d2}AOlib|AAM0002|ABBC000006|")[1]
        s3 = api("SIP2 checkin (09)", "POST", "/interop/sip2", f"09N{d1}{d1}AOlib|ABBC000006|")[1]
        check("AC03", "SIP2 checkout / renew / checkin flow", s1.startswith("121") and s2.startswith("300N") and s3.startswith("101"), f"{s1[:6]} {s2[:6]} {s3[:6]}")
        hist = shell("from circulation.models import Transaction as T;print(T.objects.filter(channel__in=['NCIP','SIP2']).count(), T.objects.filter(success=False).count())")
        check("AC03", "Auditable history recorded for NCIP/SIP2 (incl. denials)", bool(hist) and int(hist[0].split()[0]) >= 9 and int(hist[0].split()[1]) >= 3, hist)
        c, t_ = api("Gate: unauthorised item", "POST", "/rfid/api/gate", json.dumps({"event_id": "EVID-G1", "tag_uid": "E200000000000002"}))
        g = json.loads(t_) if c == 200 else {}
        check("AC06", "Unauthorised removal raises alarm with accession number", g.get("alarm") is True and g.get("accession_no") == "ACC000002", g)
        check("AC06", "Mock CCTV image attached", str(g.get("cctv_image", "")).endswith(".png"))
        q = shell("from notifications.models import Notification as N;print(N.objects.filter(channel='email',status='QUEUED').count())")
        check("AC06", "Email notification queued", q and int(q[0]) >= 1, q)
        check("AC06", "Duplicate gate event ignored", json.loads(api("Gate duplicate", "POST", "/rfid/api/gate", json.dumps({"event_id": "EVID-G1", "tag_uid": "E200000000000002"}))[1]).get("duplicate") is True)
        api("Gate footfall", "POST", "/rfid/api/gate", json.dumps({"event_id": "EVID-F1", "kind": "FOOTFALL"}))
        api("Gate cache download", "GET", "/rfid/api/gate-cache")
        off = json.loads(api("Gate with LMS offline", "POST", "/rfid/api/gate", json.dumps({"event_id": "EVID-G2", "tag_uid": "E200000000000003", "lms_online": False}))[1])
        check("AC06", "Gate decides from cache while LMS offline", off.get("alarm") is True and off.get("accession_no") == "ACC000003", off)
        inv = json.loads(api("Inventory shelf A-01", "POST", "/rfid/api/inventory", json.dumps({"shelf": "A-01", "tags": ["E200000000000001", "E200000000000002", "E200000000000005"]}))[1])
        check("AC05", "Inventory reports missing items", {m["accession_no"] for m in inv.get("missing", [])} == {"ACC000003", "ACC000004"}, inv.get("missing"))
        check("AC05", "Inventory reports misplaced items", [m["accession_no"] for m in inv.get("misplaced", [])] == ["ACC000005"], inv.get("misplaced"))
        ev = shell("from rfid.models import DeviceEvent as D;print(D.objects.filter(kind='CONFIRM',payload__visible='GREEN').count(), D.objects.filter(kind='CONFIRM',payload__visible='RED').count())")
        check("AC05", "Visible + audible confirmation events recorded", bool(ev) and all(int(x) > 0 for x in ev[0].split()), ev)
        c, t_ = api("Tag (re-tag) via API", "POST", "/rfid/api/tag", json.dumps({"accession_no": "ACC000008", "tag_uid": "E2009999999999AA", "retag": True}))
        check("AC02", "API validates record and links tag", c == 200 and "ACC000008" in t_, t_[:150])
        check("AC02", "API refuses unknown accession number", api("Tag unknown item", "POST", "/rfid/api/tag", json.dumps({"accession_no": "NOPE", "tag_uid": "E200000000000077"}))[0] == 422)

    class Session:
        """Cookie-based browser-like session using only the standard library (no browser needed)."""

        def __init__(self):
            self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

        def get(self, path):
            try:
                r = self.op.open(BASE + path, timeout=30)
                return r.status, r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                return e.code, e.read().decode("utf-8", "replace")

        def post(self, path, data):
            page = self.get(path)[1]
            m = re.search(r'csrfmiddlewaretoken" value="([^"]+)', page)
            data = dict(data, csrfmiddlewaretoken=m.group(1) if m else "")
            req = urllib.request.Request(BASE + path, urllib.parse.urlencode(data).encode(), headers={"Referer": BASE + path})
            try:
                r = self.op.open(req, timeout=30)
                return r.status, r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                return e.code, e.read().decode("utf-8", "replace")

    if up:
        sv = Session()
        sv.post("/login/smartcard/", {"card_uid": "04AA000004"})
        check("AC07", "Smart-card login works (viewer1)", "viewer1" in sv.get("/")[1])
        check("AC07", "Viewer role: circulation denied (403)", sv.get("/circulation/")[0] == 403)
        check("AC07", "Viewer role: system page denied (403)", sv.get("/system/")[0] == 403)
        check("AC07", "Viewer role: reports allowed", sv.get("/reports/")[0] == 200)
        sc = Session()
        sc.post("/login/smartcard/", {"card_uid": "04AA000003"})
        check("AC07", "Circulation role: desk allowed, reports denied", sc.get("/circulation/")[0] == 200 and sc.get("/reports/")[0] == 403)
        check("AC07", "Unknown smart card is refused", "circdesk1" not in Session().post("/login/smartcard/", {"card_uid": "BAD-CARD"})[1])
        sa = Session()
        sa.post("/login/", {"username": "admin", "password": "Demo#12345"})
        code, dash = sa.get("/")
        check("AC08", "Dashboard shows statistics", code == 200 and "RFID-tagged copies" in dash)
        for rt in ("tagged_items", "members", "circulation", "operators", "rfid_clients", "gate_events", "fines"):
            check("AC08", f"Report '{rt}' renders", sa.get(f"/reports/?type={rt}")[0] == 200)
        code, csv_text = sa.get("/reports/?type=circulation&operator=ncip-client&format=csv")
        check("AC08", "Filtered report exports to CSV", code == 200 and "CHECKOUT" in csv_text)
        check("FR11", "System page (health, versions, audit) available to admin", sa.get("/system/")[0] == 200)
        # Credential check: every seeded username/password/role combination
        for user, circ, rep, system in (("admin", 200, 200, 200), ("librarian1", 200, 200, 403),
                                        ("circdesk1", 200, 403, 403), ("viewer1", 403, 200, 403)):
            sx = Session()
            sx.post("/login/", {"username": user, "password": "Demo#12345"})
            check("AC07", f"Password login works for {user}", user in sx.get("/")[1] and "Log out" in sx.get("/")[1])
            got = (sx.get("/circulation/")[0], sx.get("/reports/")[0], sx.get("/system/")[0])
            check("AC07", f"Role permissions correct for {user} (circulation/reports/system)", got == (circ, rep, system), str(got))
        sbad = Session()
        sbad.post("/login/", {"username": "admin", "password": "wrong-password"})
        check("AC07", "Wrong password is refused", "Log out" not in sbad.get("/")[1])
        sl = Session()
        sl.post("/login/smartcard/", {"card_uid": "04AA000002"})
        check("AC07", "Smart-card login works (librarian1)", "librarian1" in sl.get("/")[1])
    (LOGS / "api_exchanges.txt").write_text("\n".join(api_log), encoding="utf-8")
    STEPS.append({"title": "Live API exchanges (NCIP, SIP2, gate, inventory, tag)", "req": "FR03/FR05-07", "status": "PASS" if all(c["ok"] for c in CHECKS if c["ac"] in ("AC02", "AC03", "AC05", "AC06")) else "FAIL", "secs": 0, "log": "logs/api_exchanges.txt"})

    # -------------------------------------------------------------- 7. browser: screenshots + video
    def screenshots():
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return False, "playwright not installed"
        with sync_playwright() as p:
            browser, err = None, ""
            for kw in ({"channel": "chrome"}, {"channel": "msedge"}, {}):
                try:
                    browser = p.chromium.launch(headless=True, **kw)
                    break
                except Exception as exc:
                    err = str(exc)[:200]
            if browser is None:
                return False, "no browser available: " + err
            vdir = OUT / "video_tmp"
            shutil.rmtree(vdir, ignore_errors=True)
            ctx = browser.new_context(viewport={"width": 1366, "height": 820}, record_video_dir=str(vdir), record_video_size={"width": 1366, "height": 820})
            page = ctx.new_page()
            page.set_default_timeout(15000)
            seq = [0]

            def shot(ac, caption):
                seq[0] += 1
                page.wait_for_timeout(600)
                name = f"{seq[0]:02d}_{ac}_{re.sub(r'[^a-z0-9]+', '_', caption.lower()).strip('_')[:50]}.png"
                page.screenshot(path=str(SHOTS / name), full_page=True)
                SHOT_LIST.append({"ac": ac, "caption": caption, "file": f"screenshots/{name}"})

            def go(path):
                r = page.goto(BASE + path)
                return r.status if r else 0

            def flash():
                el = page.locator(".msg").first
                return el.inner_text() if el.count() else ""

            def login(user):
                go("/login/")
                page.fill("#id_username", user)
                page.fill("#id_password", "Demo#12345")
                page.click("button[type=submit]")

            def logout():
                go("/")  # a 403/404 page has no nav, so return to a normal page first
                page.click("button:has-text('Log out')")
                page.wait_for_load_state()

            def step(fn):
                try:
                    fn()
                except Exception as exc:
                    check("UI", f"Browser step '{fn.__name__}' completed", False, str(exc)[:200])
                    try:
                        shot("ERR", f"{fn.__name__} failed")
                    except Exception:
                        pass

            def s_login():
                go("/login/")
                shot("AC07", "Staff login page")
                login("admin")
                check("AC07", "Password login works", page.url.rstrip("/") == BASE, page.url)
                shot("AC08", "Dashboard after login")

            def s_catalog_tag():  # AC02
                go("/catalog/")
                page.fill("#isbn0", "9780132350884")
                with page.expect_navigation():
                    page.click("button:has-text('Fetch details')")  # not the label that also contains this text
                check("AC02", "Net cataloguing pre-fills the title form", page.input_value("#t") == "Clean Code", page.input_value("#t"))
                shot("AC02", "Net cataloguing pre-fills title details by ISBN")
                page.fill("#t", "Evidence Run Title")
                page.click("text=Create title")
                page.fill("#acc", "EVID0001")
                page.fill("#sh", "A-01")
                page.click("text=Add copy")
                shot("AC02", "New title with copy EVID0001 (not yet tagged)")
                go("/rfid/")
                page.fill("#ta", "EVID0001")
                page.fill("#tu", "E200AAAA00000001")
                page.click("text=Link tag to item")
                msg = flash()
                check("AC02", "UI links tag to the validated item", "EVID0001" in msg and "linked" in msg, msg)
                shot("AC02", "Tag-to-item relationship displayed")
                page.fill("#ta", "DOES-NOT-EXIST")
                page.fill("#tu", "E200AAAA00000002")
                page.click("text=Link tag to item")
                check("AC02", "UI refuses tagging an unknown record", "ITEM_NOT_FOUND" in flash(), flash())
                shot("AC02", "Tagging refused for unknown record")

            def s_circulation():  # AC03/AC04
                go("/circulation/")

                def act(form_action, **fields):
                    for k, v in fields.items():
                        page.fill(f"form:has(input[name=action][value={form_action}]) input[name={k}]", v)
                    page.click(f"form:has(input[name=action][value={form_action}]) button")

                act("checkout", member_no="M0001", item="BC000001")
                check("AC03", "UI check-out succeeds", "Checked out" in flash(), flash())
                shot("AC03", "Check-out of BC000001 to M0001")
                act("renew", item="BC000001")
                check("AC03", "UI renewal succeeds", "Renewed" in flash(), flash())
                shot("AC03", "Renewal extends the due date")
                act("due", item="BC000001")
                shot("AC03", "Due-date enquiry")
                act("checkin", item="BC000001")
                check("AC03", "UI check-in succeeds", "Checked in" in flash(), flash())
                shot("AC03", "Check-in with transaction history")
                for label, fields, code in (("reference item", {"member_no": "M0001", "item": "BC000008"}, "REFERENCE_ITEM"),
                                            ("blocked member", {"member_no": "M0003", "item": "BC000001"}, "MEMBER_BLOCKED"),
                                            ("fine over limit", {"member_no": "M0004", "item": "BC000001"}, "FINE_LIMIT_EXCEEDED")):
                    act("checkout", **fields)
                    check("AC04", f"UI blocks {label}", code in flash(), flash())
                    shot("AC04", f"Circulation blocked: {label}")

            def s_rfid():  # AC05/AC06
                go("/rfid/")
                page.click("text=Run inventory")
                check("AC05", "UI inventory lists missing and misplaced", "missing" in flash().lower(), flash())
                shot("AC05", "Handheld inventory: missing, misplaced and GREEN/RED confirmations")
                page.fill("#gu", "E200000000000004")
                page.fill("#ge", "UI-GATE-1")
                page.click("text=Send gate event")
                check("AC06", "UI gate event raises alarm", "ALARM" in flash(), flash())
                shot("AC06", "Gate alarm with accession number, CCTV image and queued email")
                page.fill("#gu", "E200000000000004")
                page.fill("#ge", "UI-GATE-1")
                page.click("text=Send gate event")
                check("AC06", "UI ignores duplicate gate event", "Duplicate" in flash(), flash())
                shot("AC06", "Duplicate gate event ignored")

            def s_roles():  # AC07
                logout()
                go("/login/smartcard/")
                page.fill("#uid", "04AA000004")
                page.click("text=Log in with card")
                check("AC07", "Smart-card login works (viewer)", "viewer1" in page.inner_text("nav"), page.url)
                shot("AC07", "Smart-card login as viewer1 (read-only role)")
                check("AC07", "Viewer cannot open Circulation (403)", go("/circulation/") == 403)
                shot("AC07", "Role enforcement: viewer denied circulation")
                check("AC07", "Viewer cannot open System (403)", go("/system/") == 403)
                check("AC07", "Viewer can open Reports", go("/reports/") == 200)
                logout()
                go("/login/smartcard/")
                page.fill("#uid", "04AA000003")
                page.click("text=Log in with card")
                check("AC07", "Circulation role can open desk but not reports", go("/circulation/") == 200 and go("/reports/") == 403)
                shot("AC07", "Circulation role: reports denied")
                logout()
                login("admin")

            def s_reports():  # AC08
                go("/")
                shot("AC08", "Dashboard statistics after activity")
                for t, title in (("tagged_items", "tagged items"), ("members", "members"), ("circulation", "circulation"), ("operators", "operator activity"),
                                 ("rfid_clients", "RFID client activity"), ("gate_events", "gate events"), ("fines", "fines")):
                    st = go(f"/reports/?type={t}")
                    check("AC08", f"Report '{title}' renders", st == 200, st)
                    shot("AC08", f"Report: {title}")
                go("/reports/?type=circulation&operator=admin&from=2020-01-01")
                shot("AC08", "Circulation report filtered by operator and date")

            def s_misc():
                for path, ac, cap in (("/catalog/shelves/", "FR02", "Virtual bookshelf"), ("/opac/?q=clean", "FR01", "Public search (OPAC)"),
                                      ("/catalog/label/1/", "FR01", "Barcode and spine labels"), ("/members/", "FR04", "Members: blocked and fines"),
                                      ("/system/", "FR11", "System page: health, versions, configuration, audit log"), ("/admin/", "FR11", "Administration site")):
                    check(ac, f"{cap} renders", go(path) == 200, path)
                    shot(ac, cap)

            for fn in (s_login, s_catalog_tag, s_circulation, s_rfid, s_roles, s_reports, s_misc):
                step(fn)
            ctx.close()
            vids = list(vdir.glob("*.webm"))
            if vids:
                shutil.move(str(vids[0]), str(OUT / "demo_recording.webm"))
            shutil.rmtree(vdir, ignore_errors=True)
            browser.close()
        return True, ""

    if args.no_screenshots:
        ok, why = False, "skipped by --no-screenshots"
    else:
        ok, why = screenshots()
    if not ok:
        # fallback: save rendered HTML of key pages so there is still visual evidence
        snap = OUT / "html_snapshots"
        snap.mkdir(exist_ok=True)
        cj = CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        try:
            page = op.open(BASE + "/login/").read().decode()
            tok = re.search(r'csrfmiddlewaretoken" value="([^"]+)', page).group(1)
            op.open(urllib.request.Request(BASE + "/login/", urllib.parse.urlencode({"username": "admin", "password": "Demo#12345", "csrfmiddlewaretoken": tok}).encode(), headers={"Referer": BASE + "/login/"}))
            for path in ("/", "/catalog/", "/circulation/", "/members/", "/rfid/", "/reports/?type=circulation", "/reports/?type=gate_events", "/system/"):
                (snap / (re.sub(r"[^a-z0-9]+", "_", path.lower()).strip("_") or "home") + ".html").write_text(op.open(BASE + path).read().decode(), encoding="utf-8")
        except Exception as exc:
            why += f" (html fallback failed: {exc})"
    STEPS.append({"title": "Browser screenshots + demo video", "req": "D6/D9", "status": "PASS" if ok else "WARN", "secs": 0, "log": "logs/server.log"})
    SCREENSHOT_NOTE = "" if ok else f"Screenshots were not captured: {why}. Install with: pip install -r requirements-evidence.txt (uses installed Chrome/Edge), then re-run."
finally:
    server.terminate()
    try:
        server.wait(timeout=10)
    except Exception:
        server.kill()
    srv_log.close()

manage("backup_db", "--label", "evidence", title="Backup written and verified", req="NFR01")
if "SCREENSHOT_NOTE" not in globals():
    SCREENSHOT_NOTE = "Server did not start; no UI evidence."

# ------------------------------------------------------------------ 8. defect log + report
defect = ROOT / "docs" / "defect_log.csv"
if not defect.exists():
    with open(defect, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["ID", "Severity", "Summary", "Steps to reproduce", "Owner", "Status", "Fix version", "Retest evidence"])
        w.writerow(["DEF-001", "Medium", "Admin 'Add user' page crashes on Python 3.14", "Run on Python 3.14 with Django 5.1.4; open /admin/auth/user/add/",
                    "candidate", "Closed", "1.0.1 (Django 5.2.17)", "Page loads after upgrading Django; see evidence run"])
        w.writerow(["DEF-002", "High", "rollback_update could reuse an already rolled-back snapshot and restore an old/empty database",
                    "Run tests then evidence run sharing one data folder; call rollback_update after a completed rollback",
                    "candidate", "Closed", "1.0.2", "Regression test test_rollback_ignores_already_rolled_back_snapshots passes"])
fails = [c for c in CHECKS if not c["ok"]] + [s for s in STEPS if s["status"] == "FAIL"]
AC_TEXT = {"AC01": "Spreadsheet import, validation, duplicates, reconciliation", "AC02": "Item + mock tag relationship", "AC03": "Check-out/renew/check-in via NCIP/SIP2 with history",
           "AC04": "Blocks: reference item, blocked member, fine limit", "AC05": "Handheld inventory: missing/misplaced + confirmations", "AC06": "Gate event, accession, CCTV, email",
           "AC07": "Smart-card login and role permissions", "AC08": "Dashboard and filterable reports", "AC09": "Offline install, update and rollback", "AC10": "Restore after failed migration"}
ac_rows = []
for ac, text in AC_TEXT.items():
    cs = [c for c in CHECKS if c["ac"] == ac]
    ac_rows.append((ac, text, "PASS" if cs and all(c["ok"] for c in cs) else ("NO EVIDENCE" if not cs else "FAIL"), len([c for c in cs if c["ok"]]), len(cs)))
with open(OUT / "traceability_results.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["Acceptance scenario", "Description", "Result", "Checks passed", "Checks total"])
    w.writerows(ac_rows)
    w.writerow([])
    w.writerow(["Check group", "Check", "Result", "Detail"])
    for c in CHECKS:
        w.writerow([c["ac"], c["text"], "PASS" if c["ok"] else "FAIL", c["detail"]])
all_pass = not fails and all(r[2] == "PASS" for r in ac_rows)
(OUT / "status.txt").write_text("ALL PASS\n" if all_pass else f"ATTENTION: {len(fails)} failing item(s), see EVIDENCE_REPORT.html\n", encoding="utf-8")
esc = html.escape
badge = lambda s: f'<span class="b {s.split()[0].lower()}">{esc(s)}</span>'
rep = ["<!doctype html><meta charset=utf-8><title>AISYS evidence report</title><style>body{font:15px Segoe UI,Arial;margin:2rem;max-width:1200px}table{border-collapse:collapse;width:100%;margin:.5rem 0 1.5rem}"
       "td,th{border:1px solid #ccd;padding:.35rem .5rem;text-align:left;vertical-align:top}th{background:#eef}.b{padding:0 .5rem;border-radius:3px;color:#fff}.pass{background:#1b6e3f}"
       ".fail,.no{background:#a8261d}.warn{background:#a86b00}img{max-width:100%;border:1px solid #bbb}figure{margin:1rem 0}figcaption{font-weight:600}</style>",
       f"<h1>AISYS RFID Library - automated evidence report</h1><p>Generated {datetime.now():%Y-%m-%d %H:%M:%S} in {round(time.time() - T0)} s. Python {sys.version.split()[0]}, Django {esc(django_ver)}. "
       f"Overall: {badge('PASS' if all_pass else 'FAIL')} (all data synthetic; isolated database in evidence/run_data)</p>",
       "<h2>Acceptance scenarios</h2><table><tr><th>ID</th><th>Scenario</th><th>Result</th><th>Checks</th></tr>"]
rep += [f"<tr><td>{a}</td><td>{esc(t)}</td><td>{badge(r)}</td><td>{p}/{n}</td></tr>" for a, t, r, p, n in ac_rows]
rep += ["</table><h2>Pipeline steps</h2><table><tr><th>Step</th><th>Requirement</th><th>Result</th><th>Seconds</th><th>Log</th></tr>"]
rep += [f"<tr><td>{esc(s['title'])}</td><td>{esc(s['req'])}</td><td>{badge(s['status'])}</td><td>{s['secs']}</td><td><a href='{s['log']}'>open</a></td></tr>" for s in STEPS]
rep += ["</table><h2>Individual checks</h2><table><tr><th>Group</th><th>Check</th><th>Result</th><th>Detail</th></tr>"]
rep += [f"<tr><td>{c['ac']}</td><td>{esc(c['text'])}</td><td>{badge('PASS' if c['ok'] else 'FAIL')}</td><td>{esc(c['detail'])}</td></tr>" for c in CHECKS]
rep += ["</table><h2>Performance (this machine)</h2><table><tr><th>Measurement</th><th>Result</th></tr>"]
rep += [f"<tr><td>{esc(k)}</td><td>{esc(str(v))}{' s' if isinstance(v, float) else ''}</td></tr>" for k, v in PERF]
rep += ["</table><h2>Screenshots</h2>", f"<p>{esc(SCREENSHOT_NOTE)}</p>"]
if (OUT / "demo_recording.webm").exists():
    rep.append("<p>Recorded walkthrough: <a href='demo_recording.webm'>demo_recording.webm</a> (open in Chrome/Edge).</p>")
rep += [f"<figure><figcaption>{s['ac']} - {esc(s['caption'])}</figcaption><img src='{s['file']}' alt='{esc(s['caption'])}'></figure>" for s in SHOT_LIST]
(OUT / "EVIDENCE_REPORT.html").write_text("\n".join(rep), encoding="utf-8")
(OUT / "performance_results.md").write_text("| Measurement | Result |\n|---|---|\n" + "\n".join(f"| {k} | {v} |" for k, v in PERF) + "\n", encoding="utf-8")
(OUT / "DEMO_SCRIPT.md").write_text("# Demo script (follow the screenshots in order)\n" + "\n".join(f"{i}. **{s['ac']}** - {s['caption']}" for i, s in enumerate(SHOT_LIST, 1)) + "\n", encoding="utf-8")
with zipfile.ZipFile(ROOT / "evidence_pack.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for p in list(OUT.rglob("*")) + [ROOT / "docs" / "RTM.csv", defect, ROOT / "docs" / "sbom.json"]:
        if p.is_file() and "run_data" not in p.parts and "offline_venv" not in p.parts:
            z.write(p, p.relative_to(ROOT))
print("\n" + "=" * 60)
for a, t, r, p, n in ac_rows:
    print(f"{a}: {r} ({p}/{n})  {t}")
print(f"\nReport : {OUT / 'EVIDENCE_REPORT.html'}\nPack   : {ROOT / 'evidence_pack.zip'}\nStatus : {(OUT / 'status.txt').read_text().strip()}")
sys.exit(0 if all_pass else 1)
