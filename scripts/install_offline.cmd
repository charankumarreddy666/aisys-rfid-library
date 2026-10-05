@echo off
REM Install with NO internet, using the local wheels folder.
cd /d "%~dp0.."
if not exist wheels (echo wheels folder missing - run scripts\download_wheels.cmd on an online PC first & exit /b 1)
if not exist venv python -m venv venv || exit /b 1
call venv\Scripts\activate || exit /b 1
pip install --no-index --find-links=wheels -r requirements.txt || exit /b 1
if not exist .env copy .env.example .env >nul
python manage.py migrate || exit /b 1
python manage.py seed_demo
python manage.py check
echo Offline install complete. Start with scripts\run.cmd
