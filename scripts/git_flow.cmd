@echo off
REM Stage 1 / engineering controls: repository, branch strategy, meaningful commits, final tag.
REM Safe to run repeatedly. Merge "requests" are performed as --no-ff merges (a human reviewer should still review on your Git host).
cd /d "%~dp0.."
where git >nul 2>nul || (echo git is not installed - skipping git steps & exit /b 0)
if not exist .git (git init -b main >nul || exit /b 1)
git config user.name >nul 2>nul || git config user.name "AISYS Candidate"
git config user.email >nul 2>nul || git config user.email "candidate@example.com"

git rev-parse --verify HEAD >nul 2>nul
if errorlevel 1 (
  git add README.md .gitignore .env.example requirements.txt requirements-dev.txt requirements-evidence.txt requirements.lock VERSION ruff.toml manage.py
  git commit -q -m "chore: project scaffold, pinned dependencies and sample configuration"
  git add libsys core catalog members circulation rfid interop notifications migration_tool reports templates static
  git commit -q -m "feat: application layers, RFID middleware, NCIP/SIP2 boundaries, migration tool and offline update"
  git add tests
  git commit -q -m "test: automated tests mapped to requirements"
  git add docs scripts update_payload_1.0.1 .github
  git commit -q -m "docs: requirements, architecture, guides and automation scripts"
)
git show-ref --verify --quiet refs/heads/main || git branch -M main
git show-ref --verify --quiet refs/heads/develop || git branch develop

git checkout -q -B feature/evidence-run develop || exit /b 1
git add -A
git commit -q -m "test: automated evidence run, defect log and traceability results"
git checkout -q develop
git merge -q --no-ff feature/evidence-run -m "Merge feature/evidence-run into develop"
git checkout -q main
git merge -q --no-ff develop -m "Release: evaluation build"

findstr /c:"ALL PASS" evidence\status.txt >nul 2>nul
if not errorlevel 1 (
  git tag -f -a v1.0.0-eval -m "Final evaluation release (all acceptance scenarios passed)" >nul
  echo Tagged v1.0.0-eval
) else (
  echo Evidence run had failures - release tag NOT created.
)
echo Branches:
git branch
echo Recent history:
git log --oneline -n 8
exit /b 0
