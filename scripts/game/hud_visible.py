"""Is the plain in-game HUD showing (no console, no menu)? Prints 'yes' or 'no'.

usage: python hud_visible.py shot.png
In normal play the oxygen ring (bottom left) and the health bar (bottom right) are bright: in shot.ps1's 1280x720 output
about 12% of the ring box and 57% of the bar box are above 215 / 200. The console overlay dims both to ~0, and menus
(Skills, Status) hide them. route_run / readpos check "yes" before pressing the console key and "no" right after, so a
console toggle that the game dropped can never send typed commands into the game or a menu ("p" opens Skills there).
"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import game_frame  # noqa: E402


def frac(im, box, threshold, at):
    hist = im.crop(at(*box)).histogram()
    return sum(hist[threshold:]) / max(sum(hist), 1)


def visible(path):
    im = Image.open(path).convert("L")
    at = game_frame.mapper(im)          # a letterboxed frame (a 16:10 desktop) too: game_frame.py
    return frac(im, (55, 535, 200, 685), 216, at) > 0.04 and frac(im, (1020, 628, 1210, 638), 200, at) > 0.25


if __name__ == "__main__":
    print("yes" if visible(sys.argv[1]) else "no")
