"""Which option of Starfield's "different Creations Load Order" dialog is highlighted? Prints 'save', 'current' or 'none'.

usage: python loadorder_row.py shot.png
The dialog (2026-10-13 launch frames) lists "Save" over "Current"; in shot.ps1's 1280x720 output the rows span about
y 338..358 and y 366..386, x 405..757. The highlighted row is a grey bar (mean grey about 102 right of its label), the
other row is the dialog's ground (about 49). Only the empty right part of each row is measured, so the labels do not count.
Whether the dialog is shown at all is an OCR check (loadorder.ps1); this only reads the highlight.
"""
import os
import sys

from PIL import Image, ImageStat

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import game_frame  # noqa: E402

MARGIN = 25          # the highlighted row is this much brighter than the other one (measured gap: 53)


def row(path):
    im = Image.open(path).convert("L")
    at = game_frame.centred(im)
    mean = lambda y0, y1: ImageStat.Stat(im.crop(at(520, y0, 750, y1))).mean[0]
    save, current = mean(340, 356), mean(368, 384)
    if save - current > MARGIN:
        return "save"
    if current - save > MARGIN:
        return "current"
    return "none"


if __name__ == "__main__":
    print(row(sys.argv[1]))
