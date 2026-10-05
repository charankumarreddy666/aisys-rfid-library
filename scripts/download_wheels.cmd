@echo off
REM Run on an ONLINE machine to prepare the offline bundle (wheels folder).
cd /d "%~dp0.."
if not exist wheels mkdir wheels
python -m pip download -r requirements.txt -d wheels
echo Copy the whole project folder (including wheels) to the isolated site, then run scripts\install_offline.cmd
