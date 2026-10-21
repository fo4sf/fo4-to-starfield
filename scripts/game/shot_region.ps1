# Native-resolution capture of a screen region given as fractions of the screen (no downscaling, for OCR).
# Every caller reads the console, which is open only in gameplay, and gameplay fills the screen at any aspect (v6e
# frames on the owner's 2560x1600 display, #443). So the fractions are of the whole screen, never of game_rect.ps1's
# 16:9 picture: a dark interior with the console open and the HUD hidden has near-black bands top and bottom, read as
# a letterbox, and the crop then moved and shrank the console (v6e stairs 2026-10-21: every readpos in
# BostonPublicLibrary02 failed although the player stood there; supported, not seen in a capture).
param([string]$Out, [double]$FX = 0.0, [double]$FY = 0.66, [double]$FW = 0.42, [double]$FH = 0.34)
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type @'
using System; using System.Runtime.InteropServices;
public class Dpi2 { [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }
'@
[Dpi2]::SetProcessDPIAware() | Out-Null
$b = [System.Windows.Forms.SystemInformation]::VirtualScreen
$x = [int]($b.Width * $FX); $y = [int]($b.Height * $FY); $w = [int]($b.Width * $FW); $h = [int]($b.Height * $FH)
$bmp = New-Object System.Drawing.Bitmap $w, $h
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.Left + $x, $b.Top + $y, 0, 0, $bmp.Size)
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
"saved $Out ${w}x${h} from screen $($b.Width)x$($b.Height)"
