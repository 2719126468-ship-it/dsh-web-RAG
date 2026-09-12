param(
  [string]$ProfileDir = 'C:\Users\HWZ\.dsh\profiles\web',
  [string]$Snap       = 'C:\Users\HWZ\.dsh\profiles\web\.dsh-snapshots\linxin-bundles-fix.snapshot.zip'
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path $Snap)) { Write-Host "[rollback][ps1] no snapshot, nothing to do: $Snap"; exit 0 }
Expand-Archive -Path $Snap -DestinationPath $ProfileDir -Force
Write-Host "[rollback][ps1] restored from: $Snap"
