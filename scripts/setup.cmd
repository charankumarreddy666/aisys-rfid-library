@echo off
REM One-time setup (needs internet once). Run from anywhere:  scripts\setup.cmd
cd /d "%~dp0.."
where python >nul 2>nul || (echo Python 3.10+ not found. Install from python.org and tick "Add to PATH". & exit /b 1)
if not exist venv python -m venv venv || exit /b 1
call venv\Scripts\activate || exit /b 1
python -m pip install --upgrade pip
pip install -r requirements.txt || exit /b 1
if not exist .env copy .env.example .env >nul
python manage.py migrate || exit /b 1
python manage.py seed_demo || exit /b 1
python scripts\gen_sample_data.py data\sample_20000.xlsx 20000
python manage.py check
echo.
echo Setup complete. Start the server with:  scripts\run.cmd
