@echo off
setlocal EnableExtensions

rem ============================================================
rem  apply-fix-linxin-lockfile.bat
rem  Add 3 @linxin666/* packages to package.json dependencies,
rem  then run `pnpm install --lockfile-only` to register them in
rem  pnpm-lock.yaml WITHOUT touching node_modules (already present).
rem
rem  Idempotent: snapshot only on first run, reapply skips snapshot.
rem  Safe against EPERM: does not extract any tarballs.
rem ============================================================

set "PROFILE=C:\Users\HWZ\.dsh\profiles\web"
set "SNAP_DIR=%PROFILE%\.dsh-snapshots"
set "SNAP=%SNAP_DIR%\linxin-bundles-fix.snapshot.zip"

echo [apply] profile: %PROFILE%

if not exist "%PROFILE%\package.json" (
  echo [apply][error] package.json not found, abort.
  exit /b 2
)

rem --- 1. snapshot (only first time) ---
if not exist "%SNAP%" (
  echo [apply] first run: creating snapshot -^> %SNAP%
  if not exist "%SNAP_DIR%" mkdir "%SNAP_DIR%"
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0apply-snapshot.ps1" -ProfileDir "%PROFILE%" -Snap "%SNAP%"
  if errorlevel 1 (
    echo [apply][error] snapshot create failed
    exit /b 1
  )
) else (
  echo [apply] snapshot already exists, skip: %SNAP%
  echo [apply] to re-run, execute rollback-fix-linxin-bundles.bat first
)

rem --- 2. patch package.json (add 3 linxin deps) ---
echo [apply] patching package.json to add 3 linxin dependencies
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0apply-fix-linxin-bundles.ps1" -ProfileDir "%PROFILE%"
if errorlevel 1 (
  echo [apply][error] patch package.json failed, rolling back...
  call "%~dp0rollback-fix-linxin-bundles.bat"
  exit /b 1
)

rem --- 3. pnpm install --lockfile-only (NO tarball extraction) ---
echo [apply] running pnpm install --lockfile-only (no node_modules write)
pushd "%PROFILE%"
call pnpm install --lockfile-only
set "RC=%ERRORLEVEL%"
popd
if not "%RC%"=="0" (
  echo [apply][error] pnpm install --lockfile-only failed rc=%RC%, rolling back...
  call "%~dp0rollback-fix-linxin-bundles.bat"
  exit /b %RC%
)

echo.
echo [apply] DONE. Please paste stdout/stderr back to Agent.
echo [apply] to undo: run rollback-fix-linxin-bundles.bat
endlocal
