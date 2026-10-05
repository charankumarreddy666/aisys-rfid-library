# Administrator and user guide (D8)
## Roles
Admin (everything), Librarian (catalogue, tagging, inventory, reports, members), Circulation (desk + view), Viewer (search + reports). Manage users/groups at `/admin/`; settings (fine limit, loan days...) on the System page.
## Demo logins (synthetic) - password `Demo#12345`
admin, librarian1, circdesk1, viewer1 - smart cards 04AA000001..04AA000004.
## Daily tasks
Circulation: Circulation page (item = barcode, accession or tag UID). Members: block/unblock, record payment, print card. Catalogue: add titles (ISBN fetch), add copies, print labels. RFID console: tag items, simulate gate and handheld. Reports: filter, then Download CSV.
## Troubleshooting runbook
| Symptom | Check | Fix |
|---|---|---|
| Page 500 | `data\logs\app.log` (JSON lines) | Fix cause; if after update run `rollback_update` |
| /health shows degraded | DB file/permissions | Restore latest backup |
| Device API 401 | X-API-Key vs INTEROP_API_KEY | Correct key in device config |
| Gate alarms nothing offline | `data\gate_cache.json` missing/stale | Run `export_gate_cache` |
| Notifications stay QUEUED | Run `process_notifications`; see last_error in Admin | Fix provider, retries stop after 3 |
| Import rejects rows | `data\reports\batch_N_errors.csv` | Correct spreadsheet, re-run dry run |
## Training plan
Session 1 (1 h) circulation and members; Session 2 (1 h) cataloguing and labels; Session 3 (1 h) RFID tagging, inventory, gate; Session 4 (1 h) admin: backup, restore, update, rollback.
