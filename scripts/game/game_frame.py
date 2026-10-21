"""Where Starfield's 16:9 picture sits in a screenshot, so readers written for shot.ps1's 1280x720 output also read a
letterboxed or pillarboxed frame.

On a display that is not 16:9 Starfield draws its 16:9 picture centred between black bars: the v6e doors retry
(2026-10-21) ran on a 2560x1600 (16:10) desktop, and shot.ps1 saved 1280x800 frames with 40 px black bars top and
bottom, so every 1280x720 box (the main menu text, hud_visible.py's oxygen ring and health bar) was read 40 px too high
and scaled by 800/720, and no screen check matched. shot.ps1 and shot_region.ps1 crop to the same rectangle
(game_rect.ps1); this module lets the Python readers accept either kind of frame.
"""

DARK = 12            # a letterbox bar is black; a game drawn over the whole screen has HUD or scene pixels there
TOLERANCE = 0.01     # aspect ratios within 1 % of 16:9 are the whole image


def picture(im):
    """(left, top, width, height) of the 16:9 game picture in a PIL image: the centred 16:9 rectangle when the parts
    outside it are black bars, else the whole image (a 16:9 frame, or a game drawn over a whole non-16:9 screen)."""
    w, h = im.size
    if abs(w * 9 - h * 16) <= w * 9 * TOLERANCE:
        return 0, 0, w, h
    if w * 9 < h * 16:                                   # taller than 16:9: bars above and below
        ch = int(round(w * 9 / 16.0))
        top = (h - ch) // 2
        rect, bars = (0, top, w, ch), [(0, 0, w, top), (0, top + ch, w, h)]
    else:                                                # wider than 16:9: bars left and right
        cw = int(round(h * 16 / 9.0))
        left = (w - cw) // 2
        rect, bars = (left, 0, cw, h), [(0, 0, left, h), (left + cw, 0, w, h)]
    grey = im.convert("L")
    for box in bars:
        if box[2] <= box[0] or box[3] <= box[1] or grey.crop(box).getextrema()[1] > DARK:
            return 0, 0, w, h
    return rect


def mapper(im):
    """f(x0, y0, x1, y1) -> the same box, given in shot.ps1's 1280x720 coordinates, in this image's pixels."""
    left, top, pw, ph = picture(im)
    sx, sy = pw / 1280.0, ph / 720.0
    return lambda x0, y0, x1, y1: (int(left + x0 * sx), int(top + y0 * sy), int(left + x1 * sx), int(top + y1 * sy))
