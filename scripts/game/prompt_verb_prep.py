"""Prepare the activation prompt's verb ("OPEN" / "CLOSE") for OCR: crop, keep only near-white text, invert to black
on white, enlarge. The raw crop failed on bright backgrounds (Parsons wallpaper): OCR returned nothing for "OPEN".

usage: python prompt_verb_prep.py shot.png out.png
"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import game_frame  # noqa: E402

THRESHOLD = 150


def prep(src, dst):
    im = Image.open(src).convert("L")
    crop = im.crop(game_frame.mapper(im)(950, 203, 1036, 222))                     # verb left of the [E] key box
    big = crop.resize((crop.width * 5, crop.height * 5), Image.LANCZOS)             # smooth first: thin glyph strokes
    bw = big.point(lambda p: 0 if p > THRESHOLD else 255)                           # white text -> black on white
    canvas = Image.new("L", (bw.width + 40, bw.height + 40), 255)                   # margin helps the OCR engine
    canvas.paste(bw, (20, 20))
    canvas.save(dst)


if __name__ == "__main__":
    prep(sys.argv[1], sys.argv[2])
