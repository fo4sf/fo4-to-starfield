# Read text from a screenshot region with the built-in Windows OCR engine (Windows.Media.Ocr).
# usage: ocr.ps1 -Image shot.png [-X 0 -Y 0 -W 0 -H 0] [-Lines]   (region in image pixels; 0 = whole image).
# Prints one text row per screen row: the engine's words regrouped by their vertical position (centre within half a
# median word height), left to right. The engine's own lines (-Lines) split a console line where the HUD's compass dial
# crosses it: walk_core64c_1014 (2026-10-14) read "GetPos: X > >" in one line and "-2189.26" in another, so every
# session-scoped parser (parse_npc.py, parse_getpos.py --strict) saw labels without values and the walk never started.
param([string]$Image, [int]$X = 0, [int]$Y = 0, [int]$W = 0, [int]$H = 0, [int]$Scale = 2, [switch]$Lines)
Add-Type -AssemblyName System.Drawing, System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, [type]$t) { $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); $task.Wait() | Out-Null; $task.Result }

# crop + upscale + invert-friendly copy (the console is light text on dark; OCR likes larger glyphs)
$src = [System.Drawing.Bitmap]::FromFile((Resolve-Path $Image))
if ($W -le 0) { $W = $src.Width - $X }; if ($H -le 0) { $H = $src.Height - $Y }
$dst = New-Object System.Drawing.Bitmap ($W * $Scale), ($H * $Scale)
$g = [System.Drawing.Graphics]::FromImage($dst); $g.InterpolationMode = 'HighQualityBicubic'
$g.DrawImage($src, (New-Object System.Drawing.Rectangle 0, 0, ($W * $Scale), ($H * $Scale)), (New-Object System.Drawing.Rectangle $X, $Y, $W, $H), 'Pixel')
$tmp = [IO.Path]::Combine([IO.Path]::GetTempPath(), "ocr_" + [guid]::NewGuid().ToString('N') + ".png")
$dst.Save($tmp, [System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $dst.Dispose(); $src.Dispose()

$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($tmp)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
$stream.Dispose(); Remove-Item $tmp -ErrorAction SilentlyContinue
if ($Lines) { $result.Lines | ForEach-Object { $_.Text }; exit 0 }

# rows from word boxes: cluster the words by vertical centre (greedy, top to bottom), each row sorted left to right
$words = @()
foreach ($ln in $result.Lines) {
  foreach ($wd in $ln.Words) {
    $r = $wd.BoundingRect
    $words += [pscustomobject]@{ t = $wd.Text; x = [double]$r.X; h = [double]$r.Height; cy = [double]$r.Y + [double]$r.Height / 2 }
  }
}
if ($words.Count -eq 0) { exit 0 }
$hs = @($words | ForEach-Object { $_.h } | Sort-Object)
$tol = [Math]::Max(2.0, $hs[[int]($hs.Count / 2)] * 0.5)
$rows = New-Object System.Collections.Generic.List[object]
foreach ($wd in ($words | Sort-Object cy, x)) {
  $row = $null
  foreach ($cand in $rows) { if ([Math]::Abs($cand.cy - $wd.cy) -le $tol) { $row = $cand; break } }
  if ($null -eq $row) {
    $row = @{ cy = $wd.cy; ws = (New-Object System.Collections.Generic.List[object]) }; $rows.Add($row)
  }
  $row.ws.Add($wd)
  $row.cy = ($row.ws | ForEach-Object { $_.cy } | Measure-Object -Average).Average
}
$rows | Sort-Object { $_.cy } | ForEach-Object { (@($_.ws | Sort-Object x | ForEach-Object { $_.t })) -join ' ' }
