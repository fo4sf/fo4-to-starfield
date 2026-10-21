"""Is Starfield's activation prompt on screen? Prints 'yes' or 'no'.

usage: python prompt_visible.py shot.png
The prompt is a solid white title bar (e.g. "DOOR") right of the crosshair; in shot.ps1's 1280x720 output it spans about
x 780..1060, y 174..191. Checks that most pixels of an inner strip of that bar are near white.
"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import game_frame  # noqa: E402


def visible(path):
    im = Image.open(path).convert("L")
    box = game_frame.mapper(im)(800, 176, 1040, 189)
    hist = im.crop(box).histogram()
    return sum(hist[216:]) / max(sum(hist), 1) > 0.6


if __name__ == "__main__":
    print("yes" if visible(sys.argv[1]) else "no")
