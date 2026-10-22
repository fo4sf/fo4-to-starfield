"""Is the plain in-game HUD showing (no console, no menu)? Prints 'yes' or 'no'.

usage: python hud_visible.py shot.png [--debug]   (--debug: each layout's two readings first)
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


RING, BAR = ((55, 535, 200, 685), 216, 0.04), ((1020, 628, 1210, 638), 200, 0.25)


def readings(path):
    """[(layout, ring fraction, bar fraction)] for each place the HUD may sit (game_frame.layouts)."""
    im = Image.open(path).convert("L")
    return [(name, frac(im, RING[0], RING[1], at), frac(im, BAR[0], BAR[1], at)) for name, at in game_frame.layouts(im)]


def visible(path):
    """Both the ring and the bar bright in one layout: a letterboxed frame or a full 16:10 screen too."""
    return any(r > RING[2] and b > BAR[2] for _, r, b in readings(path))


if __name__ == "__main__":
    if "--debug" in sys.argv[2:]:
        for name, r, b in readings(sys.argv[1]):
            print(f"{name}: ring {r:.3f} (needs > {RING[2]}), bar {b:.3f} (needs > {BAR[2]})")
    print("yes" if visible(sys.argv[1]) else "no")
