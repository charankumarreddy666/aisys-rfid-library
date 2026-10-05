@echo off
cd /d "%~dp0.."
call venv\Scripts\activate || exit /b 1
echo Open http://127.0.0.1:8000  (login: admin / Demo#12345)
python manage.py runserver 127.0.0.1:8000
