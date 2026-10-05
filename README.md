# AISYS RFID Library Solution (prototype)

Modular Django prototype covering the SOP: cataloguing/circulation/OPAC, RFID middleware with mock devices, NCIP 2.0 + SIP2 boundary (mocks), notifications, migration of ~20,000 spreadsheet rows, reports, offline update with rollback, backup/restore. **All data is synthetic.**

## Run it (Windows CMD)
```
cd aisys-rfid-library
scripts\setup.cmd      (once; creates venv, DB, demo data, 20,000-row sample file)
scripts\run.cmd        (open http://127.0.0.1:8000)
```
Login `admin` / `Demo#12345` (smart card 04AA000001 at /login/smartcard/). Public search: /opac/.

## Demonstrate the acceptance scenarios
See `docs/acceptance_map.csv`. Quick UI tour: Circulation (BC000001 + M0001 ok; BCR... reference; M0003 blocked; M0004 fines) -> RFID console (tag, gate event with tag E200000000000002, inventory) -> Reports -> System.
Scripts: `scripts\demo_ac01_migration.cmd`, `scripts\demo_ac09_offline_update.cmd`, `scripts\demo_ac10_restore.cmd`, tests `scripts\test.cmd`.

## Layout
`core` (auth, RBAC, audit, backup, update) | `catalog` | `members` | `circulation` | `rfid` (middleware + mock adapters) | `interop` (NCIP/SIP2) | `notifications` | `migration_tool` | `reports` | `docs` (RTM, architecture, guides) | `scripts` | `tests`.

## Controls
Feature branches + `scripts\git_init.cmd`; CI in `.github/workflows/ci.yml`; config in `.env` (never commit); pinned deps in `requirements.lock`; licence/SBOM in `docs/`.

## One-click automation (evidence for D6/D9)
```
scripts\run_all.cmd                       (everything)
scripts\run_all.cmd --no-screenshots      (skip browser screenshots/video)
scripts\run_all.cmd --skip-offline-install --no-git
```
It runs lint, dependency audit, SBOM, 29 automated tests, the 20,000-row migration, AC01-AC10 checks, a live server with API/role checks, browser screenshots and a recorded video (uses your installed Chrome/Edge), then builds `evidence\EVIDENCE_REPORT.html`, `evidence_pack.zip`, `docs\defect_log.csv`, and runs `scripts\git_flow.cmd` (repository, develop/feature branches, commits, merges, release tag when everything passed). Your real `data\` folder is not touched.
