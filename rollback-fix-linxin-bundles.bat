@echo off
setlocal EnableExtensions

rem ============================================================
rem  rollback-fix-linxin-bundles.bat
rem  Restore package.json + pnpm-lock.yaml + cordis.yml + cordis.patch.yml
rem  from snapshot, then re-run pnpm install.
rem  - Idempotent: safe to run multiple times (no-op without snapshot)
rem ============================================================

set "PROFILE=C:\Users\HWZ\.dsh\profiles\web"
set "SNAP_DIR=%PROFILE%\.dsh-snapshots"
set "SNAP=%SNAP_DIR%\linxin-bundles-fix.snapshot.zip"

echo [rollback] profile: %PROFILE%

if not exist "%SNAP%" (
  echo [rollback] no snapshot, nothing to do: %SNAP%
  exit /b 0
)

echo [rollback] restoring from snapshot: %SNAP%
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0rollback-restore.ps1" -ProfileDir "%PROFILE%" -Snap "%SNAP%"
if errorlevel 1 (
  echo [rollback][error] extract failed
  exit /b 1
)

echo [rollback] re-running pnpm install to sync lockfile
pushd "%PROFILE%"
call pnpm install
set "RC=%ERRORLEVEL%"
popd
if not "%RC%"=="0" (
  echo [rollback][error] pnpm install failed rc=%RC%
  exit /b %RC%
)

echo.
echo [rollback] DONE. State is restored to before apply.
endlocal
