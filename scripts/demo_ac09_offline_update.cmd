@echo off
REM AC 09: build a signed offline update package, apply it, then roll it back.
cd /d "%~dp0.."
call venv\Scripts\activate || exit /b 1
echo Current version:& type VERSION
python manage.py build_update --release 1.0.1 --payload update_payload_1.0.1 --out data\update_1.0.1.zip --notes "Sample patch"
python manage.py apply_update data\update_1.0.1.zip
echo Version after update:& type VERSION
echo (Restart the server to see the green banner.)  Now rolling back...
python manage.py rollback_update
echo Version after rollback:& type VERSION
