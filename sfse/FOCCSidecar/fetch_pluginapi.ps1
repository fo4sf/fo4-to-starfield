# FOCCSidecar probe plugin, PC step 1: fetch SFSE's sfse/PluginAPI.h (and the LICENSE file that covers it) at a pinned
# commit and verify both sha256s before placing them next to FOCCSidecar.cpp. The header is the only permissively
# licensed SFSE file (MIT: the repo's LICENSE says "This applies to sfse/PluginAPI.h ... The remainder of the files are
# currently not under a permissive license", read 2026-10-21); nothing else of SFSE is ever fetched by this project,
# and the fetched copies stay out of git (.gitignore: sfse/FOCCSidecar/PluginAPI.h, PluginAPI.LICENSE.txt).
# usage: powershell -File fetch_pluginapi.ps1 [-Commit <sha>] [-Sha256 <hex>] [-LicenseSha256 <hex>] [-Dest <dir>]
# The defaults pin ianpatt/sfse master as read on 2026-10-21; a hash mismatch leaves nothing behind and exits 1.
param([string]$Commit = '48535cc4306ab345252bf740c20a1c6194929b0e',
      [string]$Sha256 = '10b834f1490b12fcab965d9c7a49f87bac3a102ed0f25a71611d499bd506c442',
      [string]$LicenseSha256 = '4a4b6926786f261e0c19178af304190c645b1b820b7722a6973c9b2a64b8a860',
      [string]$Dest = $PSScriptRoot)
$ErrorActionPreference = 'Stop'
if ($Commit -notmatch '^[0-9a-f]{40}$') { "commit must be a full 40-hex sha, got $Commit"; exit 1 }
$base = "https://raw.githubusercontent.com/ianpatt/sfse/$Commit"
$items = @(
  @{ url = "$base/sfse/PluginAPI.h"; out = (Join-Path $Dest 'PluginAPI.h');          sha = $Sha256.ToLower() },
  @{ url = "$base/LICENSE";          out = (Join-Path $Dest 'PluginAPI.LICENSE.txt'); sha = $LicenseSha256.ToLower() })
$tmpDir = Join-Path $env:TEMP ("focc_pluginapi_" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmpDir | Out-Null
try {
  foreach ($it in $items) {
    $tmp = Join-Path $tmpDir (Split-Path -Leaf $it.out)
    Invoke-WebRequest -Uri $it.url -OutFile $tmp -UseBasicParsing
    $got = (Get-FileHash -Algorithm SHA256 $tmp).Hash.ToLower()
    if ($got -ne $it.sha) { "sha256 mismatch for $($it.url): got $got, want $($it.sha); nothing placed"; exit 1 }
  }
  foreach ($it in $items) {
    if (Test-Path $it.out) {
      $have = (Get-FileHash -Algorithm SHA256 $it.out).Hash.ToLower()
      if ($have -ne $it.sha) { "$($it.out) exists with a different hash ($have); remove it by hand first, nothing overwritten"; exit 1 }
      "unchanged: $($it.out)"
    } else {
      Move-Item (Join-Path $tmpDir (Split-Path -Leaf $it.out)) $it.out
      "placed: $($it.out) (sha256 $($it.sha), commit $Commit)"
    }
  }
} finally { Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue }
exit 0
