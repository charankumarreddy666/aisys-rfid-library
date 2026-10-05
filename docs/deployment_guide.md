# Deployment, administration and recovery (D7/D8)
## Environment checklist
Windows Server 2022+ (or Windows 11), Python 3.10-3.14 installed, Ethernet, a folder for `data\` with backups on a separate disk/USB, firewall open only for the chosen port.

## Online install
`scripts\setup.cmd` then `scripts\run.cmd`.

## Offline install (isolated site)
1. On an online PC: `scripts\download_wheels.cmd` (creates `wheels\`).
2. Copy the whole project folder to the site. 3. `scripts\install_offline.cmd`. 4. Edit `.env` (change SECRET_KEY, INTEROP_API_KEY, UPDATE_SIGNING_KEY, DEMO_PASSWORD) and set DEBUG=false with the site hostname in ALLOWED_HOSTS.
5. Run as a service with a production WSGI server (e.g. waitress, bundled in wheels) behind a TLS reverse proxy.

## Backup / restore
`python manage.py backup_db --label nightly` -> `data\backups\*.sqlite3` + `.json` manifest (SHA-256, counts).
Restore (stop the server first): `python manage.py restore_db data\backups\<file>.sqlite3`. A file whose checksum does not match is refused.

## Update / upgrade / patch / rollback
Build (vendor side): `python manage.py build_update --release 1.0.1 --payload update_payload_1.0.1 --out data\update_1.0.1.zip`
Apply (site): `python manage.py apply_update data\update_1.0.1.zip`, then restart. Rollback: `python manage.py rollback_update`.
Security: package must carry a valid HMAC signature (UPDATE_SIGNING_KEY identical on both sides); `data\`, `.env` are protected.

## Offline gate cache
`python manage.py export_gate_cache` (schedule every few minutes) or `GET /rfid/api/gate-cache`.

## Scheduled tasks (Windows Task Scheduler)
`manage.py process_notifications` (every minute), `manage.py send_overdue_notices` (daily), `manage.py backup_db` (nightly).
