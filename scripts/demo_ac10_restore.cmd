@echo off
REM AC 10: crash a migration half-way, restore from backup, prove original data is intact.
cd /d "%~dp0.."
call venv\Scripts\activate || exit /b 1
if not exist data\sample_20000.xlsx python scripts\gen_sample_data.py data\sample_20000.xlsx 20000
python manage.py demo_failed_migration data\sample_20000.xlsx
