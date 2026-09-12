param(
  [string]$ProfileDir = 'C:\Users\HWZ\.dsh\profiles\web',
  [string]$Snap       = 'C:\Users\HWZ\.dsh\profiles\web\.dsh-snapshots\linxin-bundles-fix.snapshot.zip'
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path $ProfileDir)) { throw "profile dir not found: $ProfileDir" }
$snapDir = Split-Path $Snap -Parent
if (-not (Test-Path $snapDir)) { New-Item -ItemType Directory -Path $snapDir -Force | Out-Null }
$files = @('package.json','pnpm-lock.yaml','cordis.yml','cordis.patch.yml')
$fullPaths = $files | ForEach-Object { Join-Path $ProfileDir $_ }
if (Test-Path $Snap) { Remove-Item $Snap -Force }
Compress-Archive -Path $fullPaths -DestinationPath $Snap -Force
Write-Host "[apply][ps1] snapshot created: $Snap"
