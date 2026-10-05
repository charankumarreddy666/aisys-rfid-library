@echo off
REM Stage 1 / D0: create repository, branches and first commit.
cd /d "%~dp0.."
git init -b main || exit /b 1
git add .
git commit -m "chore: initial project scaffold, RTM and SOP stage-1 documents"
git branch develop
git checkout -b feature/foundation develop
echo Repository ready. Branch strategy: main (releases, tagged) <- develop <- feature/* via reviewed merge requests.
echo Tag the final release with:  git tag -a v1.0.0-eval -m "Final evaluation release"
