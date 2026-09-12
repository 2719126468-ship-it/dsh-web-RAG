# apply-fix-linxin-bundles.ps1
# Edit profile/package.json, inject 3 @linxin666/* deps, do not re-order existing fields.

param(
  [Parameter(Mandatory=$true)][string]$ProfileDir
)

$pkgPath = Join-Path $ProfileDir 'package.json'
$content = Get-Content -Raw -LiteralPath $pkgPath -Encoding UTF8
$json = $content | ConvertFrom-Json

# Ensure dependencies object exists
if (-not $json.dependencies) {
  $json | Add-Member -NotePropertyName 'dependencies' -NotePropertyValue ([pscustomobject]@{})
}

$toAdd = [ordered]@{
  '@linxin666/dsh-web-ui-all'             = '^0.3.6'
  '@linxin666/dsh-client-ui-task-board'   = '^0.3.6'
  '@linxin666/dsh-remote-web-ui'          = '^0.3.6'
}

$changed = $false
foreach ($k in $toAdd.Keys) {
  $cur = $json.dependencies.PSObject.Properties[$k]
  if ($null -eq $cur) {
    Add-Member -InputObject $json.dependencies -NotePropertyName $k -NotePropertyValue $toAdd[$k]
    Write-Host ("[apply] + {0} @ {1}" -f $k, $toAdd[$k])
    $changed = $true
  } else {
    Write-Host ("[apply] = {0} already present @ {1}, keep existing" -f $k, $cur.Value)
  }
}

if (-not $changed) {
  Write-Host '[apply] package.json already up to date, no change.'
  exit 0
}

# Preserve key order: serialize then write UTF-8 no BOM
$new = $json | ConvertTo-Json -Depth 100
if (-not $new.EndsWith("`n")) { $new += "`n" }
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($pkgPath, $new, $utf8NoBom)
Write-Host ("[apply] wrote {0}" -f $pkgPath)
exit 0
