"""Time of day and weather for queued game tests: the commands qstep.ps1 may type, and the sky brightness of screenshots.

usage (qstep.ps1):  python sky_light.py measure <png> [--before <sky>] [--hour <local hour>]
  prints one JSON line {"sky": <0..255>, "class": "daylight" | "night" | "unclear", "done": <bool>}

Sky brightness: the mean RGB value (0..255) of the top SKY_ROWS rows of a screenshot, the measure the ground-texture
verifier uses (scripts/terrain/ground_textures.py lighting, PR #70). Its thresholds come from fifteen terrain attempts of
2026-10-11 on Mars, at the arrival's own camera: night 6.4..19.9, daylight 103..131 (a heuristic between those groups,
not a calibration; an arrival in a pit read 7.3 in daylight). docs/ai/test-queue.md, "Time of day and weather".

The commands (Starfield.exe 1.16.244 command table and the Creation Kit's Papyrus sources, research in the doc):
  SetLocalTime <hour> [1]   console command (short name slt): "Sets the local time on the current planet, optionally
                            updating the galaxy sim"; Game.SetLocalTime: "Rotates the current planet such that the local
                            time will match the specified time" (12 = noon on every planet, whatever its day length)
  cgf "Game.SetLocalTime" <hour>   the same native through CallGlobalFunction (MQ101 calls it on arrival)
  fw <weather> [1]          ForceWeather: "Forces the active weather to the specified type, without transition"; 1 keeps
                            it until ReleaseWeatherOverride
"""
import argparse
import json
import math
import re

SKY_ROWS = 200
NIGHT_SKY_MAX, DAY_SKY_MIN = 30.0, 60.0
EFFECT_MIN = 15.0          # a rise or fall of the sky this large counts as "the command changed the sky"
DAY_HOURS = (7.0, 17.0)    # a requested local hour in this range should read as daylight
NIGHT_HOURS = (5.0, 19.0)  # before the first or after the second: should read as night (in between: twilight)
# the only time-of-day commands qstep.ps1 types ({h}: the validated local hour); the default ladder tries them in order
# and stops at the first that makes the sky read as the requested hour
TIME_METHODS = {"slt": "SetLocalTime {h}", "slt_galaxy": "SetLocalTime {h} 1", "cgf": 'cgf "Game.SetLocalTime" {h}'}
DEFAULT_LADDER = ("slt", "slt_galaxy", "cgf")
LIGHT_KEYS = ("time_of_day", "time_methods", "weather", "weather_lock", "light_wait_ms", "need_daylight")


def hour_text(h):
    """The hour as qstep.ps1 types it (two decimals at most, no exponent, invariant culture)."""
    return f"{h:.2f}".rstrip("0").rstrip(".")


def commands(test):
    """Every console line the light step of `test` may type, in order (weather first, then the time ladder)."""
    out = []
    if test.get("weather"):
        out.append(f"fw {test['weather']}" + (" 1" if test.get("weather_lock") else ""))
    if test.get("time_of_day") is not None:
        h = hour_text(float(test["time_of_day"]))
        out += [TIME_METHODS[m].format(h=h) for m in test.get("time_methods") or DEFAULT_LADDER]
    return out


def light_fields(w, fail):
    """Validated time-of-day / weather fields of a plan.json entry (or of the plan-* command line); `fail(msg)` raises
    or exits. Nothing else from these fields reaches the console."""
    out = {}
    if w.get("time_of_day") is not None:
        try:
            h = float(w["time_of_day"])
        except (TypeError, ValueError):
            fail(f"bad time_of_day (a local hour 0..24): {w['time_of_day']!r}")
        if not (math.isfinite(h) and 0.0 <= h < 24.0):
            fail(f"time_of_day must be a local hour within 0..24 (12 = noon): {h}")
        out["time_of_day"] = round(h, 2)
        methods = w.get("time_methods")
        if methods is not None:
            if not isinstance(methods, list) or not methods or any(m not in TIME_METHODS for m in methods) \
                    or len(set(methods)) != len(methods):
                fail(f"time_methods must be a list of distinct methods among {sorted(TIME_METHODS)}: {methods!r}")
            out["time_methods"] = list(methods)
    elif w.get("time_methods") is not None:
        fail("time_methods without time_of_day")
    if w.get("weather"):
        wx = str(w["weather"])
        if not re.fullmatch(r"[0-9A-Fa-f]{8}", wx):
            fail(f"bad weather form id (8 hex digits): {wx!r}")
        out["weather"] = wx.upper()
        if w.get("weather_lock"):
            out["weather_lock"] = True
    elif w.get("weather_lock"):
        fail("weather_lock without weather")
    if out and w.get("light_wait_ms") is not None:
        try:
            ms = int(w["light_wait_ms"])
        except (TypeError, ValueError):
            fail(f"bad light_wait_ms: {w['light_wait_ms']!r}")
        if not 0 <= ms <= 30000:
            fail(f"light_wait_ms must be within 0..30000: {ms}")
        out["light_wait_ms"] = ms
    if w.get("need_daylight"):
        if out.get("time_of_day") is None and not out.get("weather"):
            fail("need_daylight without time_of_day or weather: nothing would make it daylight")
        out["need_daylight"] = True
    return out


def classify(sky):
    if sky is None:
        return "unread"
    if sky >= DAY_SKY_MIN:
        return "daylight"
    if sky <= NIGHT_SKY_MAX:
        return "night"
    return "unclear"


def expected(hour):
    """What the sky should read after setting this local hour: daylight, night, or None (twilight: any clear change)."""
    if hour is None:
        return None
    if DAY_HOURS[0] <= hour <= DAY_HOURS[1]:
        return "daylight"
    if hour < NIGHT_HOURS[0] or hour > NIGHT_HOURS[1]:
        return "night"
    return None


def done(before, after, hour):
    """True when the ladder can stop: the sky reads as the requested hour (twilight hours: it changed clearly)."""
    if after is None:
        return False
    want = expected(hour)
    if want is not None:
        return classify(after) == want
    return before is not None and abs(after - before) >= EFFECT_MIN


def brightness(png, rows=SKY_ROWS):
    from PIL import Image          # numpy and Pillow: the runner's venv; imported here so the judge does not need them
    import numpy as np
    im = np.asarray(Image.open(png).convert("RGB"), np.float64)
    return float(im[:rows].mean())


def verdict(test, light):
    """None when `test` asked for no time of day and no weather. Else {"light": daylight | night | unclear | unread,
    "effect": True | False | None, "sky": [before, after], "detail"}: night with "no effect" when the commands left a
    dark sky as it was (the run was at night whatever was typed)."""
    hour = test.get("time_of_day")
    if hour is None and not test.get("weather"):
        return None
    if not isinstance(light, dict):
        return {"light": "unread", "effect": None, "sky": [None, None],
                "detail": "no light observations (the step ended before the time of day was set)"}
    before = (light.get("before") or {}).get("sky")
    tries = [x for x in light.get("tries") or [] if isinstance(x, dict)]
    after = next((x.get("sky") for x in reversed(tries) if x.get("sky") is not None), None)
    cls = classify(after)                       # no reading after the commands: unread, whatever the arrival showed
    effect = None if after is None or before is None else abs(after - before) >= EFFECT_MIN
    typed = "; ".join(str(x.get("cmd", "?")) for x in tries) or "nothing typed"

    def fmt(v):
        return "-" if v is None else f"{v:.1f}"
    want = f"local hour {hour_text(hour)}" if hour is not None else f"weather {test.get('weather')}"
    detail = f"{want}: sky {fmt(before)} -> {fmt(after)} after {typed}; "
    if after is None:
        detail += "unread (no sky reading after the commands)"
    elif effect is False and cls != "daylight":
        detail += f"no effect: {cls}"
    else:
        detail += cls + (" (no reading before the commands)" if before is None else "")
    if cls in ("daylight", "night") and expected(hour) not in (None, cls):
        detail += f" (asked for {expected(hour)})"
    return {"light": cls, "effect": effect, "sky": [before, after], "detail": detail}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("measure")
    m.add_argument("png")
    m.add_argument("--before", type=float, default=None)
    m.add_argument("--hour", type=float, default=None)
    a = ap.parse_args(argv)
    try:
        sky = round(brightness(a.png), 1)
    except Exception as e:  # noqa: BLE001 - an unreadable shot is a missing observation, never a crash of the step
        print(json.dumps({"sky": None, "class": "unread", "done": False, "error": str(e)[:120]}))
        return 1
    print(json.dumps({"sky": sky, "class": classify(sky), "done": done(a.before, sky, a.hour)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
