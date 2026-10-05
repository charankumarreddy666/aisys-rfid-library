@echo off
REM AC 01: stage, reject invalid rows, find duplicates, migrate, reconcile (and AC 10-style rollback at the end)
cd /d "%~dp0.."
call venv\Scripts\activate || exit /b 1
if not exist data\sample_20000.xlsx python scripts\gen_sample_data.py data\sample_20000.xlsx 20000
echo ---- DRY RUN (nothing is written) ----
python manage.py import_spreadsheet data\sample_20000.xlsx
echo ---- COMMIT (a backup is taken first) ----
python manage.py import_spreadsheet data\sample_20000.xlsx --commit
echo Reports: data\reports\  (errors CSV + reconciliation text)
echo To undo the last batch run:  python manage.py rollback_batch ^<batch id^>
