param([string]$Out = (Join-Path $env:TEMP 'fo4sf_shot.png'))
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type @'
using System; using System.Runtime.InteropServices;
public class Dpi { [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }
'@
[Dpi]::SetProcessDPIAware() | Out-Null
$b = [System.Windows.Forms.SystemInformation]::VirtualScreen
$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.Left, $b.Top, 0, 0, $bmp.Size)
# the game's 16:9 picture without letterbox bars (game_rect.ps1), downscaled for viewing: 1280x720 on any display
. (Join-Path $PSScriptRoot 'game_rect.ps1')
$r = Get-GameRect $bmp
$w = 1280; $h = [int]($r.Height * $w / $r.Width)
$small = New-Object System.Drawing.Bitmap $w, $h
$g2 = [System.Drawing.Graphics]::FromImage($small); $g2.InterpolationMode = 'HighQualityBicubic'
$g2.DrawImage($bmp, (New-Object System.Drawing.Rectangle 0, 0, $w, $h), $r, 'Pixel')
$small.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
"saved $Out ($($b.Width)x$($b.Height), game $($r.Width)x$($r.Height) at $($r.X),$($r.Y) -> ${w}x${h})"
