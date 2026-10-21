# Native-resolution capture of a screen region given as fractions of the screen (no downscaling, for OCR).
param([string]$Out, [double]$FX = 0.0, [double]$FY = 0.66, [double]$FW = 0.42, [double]$FH = 0.34)
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type @'
using System; using System.Runtime.InteropServices;
public class Dpi2 { [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }
'@
[Dpi2]::SetProcessDPIAware() | Out-Null
$b = [System.Windows.Forms.SystemInformation]::VirtualScreen
# the fractions are of the game's 16:9 picture, not of a letterboxed screen (game_rect.ps1)
$all = New-Object System.Drawing.Bitmap $b.Width, $b.Height
$ga = [System.Drawing.Graphics]::FromImage($all)
$ga.CopyFromScreen($b.Left, $b.Top, 0, 0, $all.Size)
. (Join-Path $PSScriptRoot 'game_rect.ps1')
$r = Get-GameRect $all
$x = $r.X + [int]($r.Width * $FX); $y = $r.Y + [int]($r.Height * $FY); $w = [int]($r.Width * $FW); $h = [int]($r.Height * $FH)
$w = [math]::Min($w, $all.Width - $x); $h = [math]::Min($h, $all.Height - $y)
$bmp = $all.Clone((New-Object System.Drawing.Rectangle $x, $y, $w, $h), $all.PixelFormat)
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
"saved $Out ${w}x${h} from screen $($b.Width)x$($b.Height), game $($r.Width)x$($r.Height) at $($r.X),$($r.Y)"
