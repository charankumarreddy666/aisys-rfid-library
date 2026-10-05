@echo off
cd /d "%~dp0.."
call venv\Scripts\activate || exit /b 1
if not exist test_evidence mkdir test_evidence
python manage.py test tests -v 2 > test_evidence\results.txt 2>&1
type test_evidence\results.txt | findstr /R /C:"^Ran " /C:"^OK" /C:"^FAILED"
echo Full log: test_evidence\results.txt
