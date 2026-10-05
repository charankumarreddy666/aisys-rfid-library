@echo off
REM ============================================================================
REM  ONE-CLICK AUTOMATION for the AISYS SOP:
REM    setup -> lint -> tests -> migration -> AC01..AC10 checks -> screenshots + video
REM    -> evidence report + evidence_pack.zip -> git repository, branches, commits, tag
REM  Usage:  scripts\run_all.cmd [--no-screenshots] [--skip-offline-install] [--no-git]
REM  Your real data\ folder is NOT touched (evidence runs in evidence\run_data).
REM ============================================================================
setlocal
cd /d "%~dp0.."
set NOGIT=0
set ARGS=
:parse
if "%~1"=="" goto parsed
if /i "%~1"=="--no-git" (set NOGIT=1) else (set ARGS=%ARGS% %1)
shift
goto parse
:parsed

echo.
echo [1/5] Checking Python ...
where python >nul 2>nul || (echo ERROR: Python not found. Install Python 3.10-3.14 and tick "Add to PATH". & exit /b 1)
python --version

echo [2/5] Preparing virtual environment and packages ...
if not exist venv (python -m venv venv || exit /b 1)
call venv\Scripts\activate || exit /b 1
python -m pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt || (echo ERROR: could not install requirements & exit /b 1)
pip install --quiet -r requirements-dev.txt || echo WARNING: dev tools (ruff/pip-audit) not installed - those steps will show WARN
pip install --quiet -r requirements-evidence.txt || echo WARNING: Playwright not installed - screenshots will be skipped
if not exist .env copy .env.example .env >nul

echo [3/5] Running automated evidence suite (about 3-6 minutes) ...
python scripts\evidence.py %ARGS%
set RC=%ERRORLEVEL%

echo [4/5] Git repository, branches, commits and release tag ...
if "%NOGIT%"=="1" (echo Skipped by --no-git) else (call scripts\git_flow.cmd)

echo [5/5] Opening the report ...
if exist evidence\EVIDENCE_REPORT.html start "" evidence\EVIDENCE_REPORT.html
echo.
type evidence\status.txt
echo Evidence pack for submission: evidence_pack.zip
exit /b %RC%
