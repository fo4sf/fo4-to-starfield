"""Time of day and weather for queued game tests: the commands qstep.ps1 may type, and the light of its screenshots.

usage (qstep.ps1):  python sky_light.py measure <png> [--before <sky>] [--hour <local hour>]
  prints one JSON line {"sky": <0..255>, "corners": <0..255>, "class": "daylight" | "night" | "unclear",
  "corner_class": ..., "done": <bool>}

Two measures, both the ones of the ground-texture verifier (scripts/terrain/ground_textures.py lighting, PR #70):
  sky      the mean RGB value (0..255) of the top SKY_ROWS rows: the arrival camera's sky (spawn.png / arrival.png and
           the shots right after each time command);
  corners  the mean of the top fifth's outer quarters (ground away from the helmet lamp's circle): every terrain probe
           shot (pt<k>.png), whose median decides the run when there are probes.
Readings of 2026-10-11 (C:\\Modding\\testqueue, 31 Mars arrivals from the runner's save; docs/ai/test-queue.md "Time of
day and weather"): the arrival sky alone is not reliable (a daylight arrival in a pit read 7.3, another 49.9; core64's
night arrivals read up to 44.3), the probe-corner median separated every attempt (night 6.7..37.0, daylight
47.5..154.4). The thresholds sit between those groups: a heuristic, not a calibration.

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
import statistics

SKY_ROWS = 200
NIGHT_SKY_MAX, DAY_SKY_MIN = 30.0, 60.0          # the arrival camera's top rows
NIGHT_CORNER_MAX, DAY_CORNER_MIN = 40.0, 45.0    # the median of the probe shots' top corners (#70's thresholds)
EFFECT_MIN = 15.0          # a rise or fall of the sky this large counts as "the command changed the sky"
DAY_HOURS = (7.0, 17.0)    # a requested local hour in this range should read as daylight
NIGHT_HOURS = (5.0, 19.0)  # before the first or after the second: should read as night (in between: twilight)
# the only time-of-day commands qstep.ps1 types ({h}: the validated local hour); the default ladder tries them in order
# and stops at the first that makes the sky read as the requested hour
TIME_METHODS = {"slt": "SetLocalTime {h}", "slt_galaxy": "SetLocalTime {h} 1", "cgf": 'cgf "Game.SetLocalTime" {h}'}
DEFAULT_LADDER = ("slt", "slt_galaxy", "cgf")
LIGHT_KEYS = ("time_of_day", "time_methods", "time_repin", "weather", "weather_lock", "light_wait_ms", "need_daylight")


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


def repins(test):
    """True when qstep.ps1 types the time command that worked again before every terrain probe (time_repin, default
    on): game time runs during the probes (exp2b2 took 18.6 min for 14 probes), so noon would not last."""
    return test.get("kind") == "terrain" and test.get("time_of_day") is not None and test.get("time_repin", True)


def light_fields(w, fail):
    """Validated time-of-day / weather fields of a plan.json entry (or of the plan-* command line); `fail(msg)` raises
    or exits. Nothing else from these fields reaches the console."""
    out = {}
    if w.get("time_of_day") is not None:
        v = w["time_of_day"]
        if isinstance(v, bool):                        # JSON true is not hour 1
            fail(f"bad time_of_day (a local hour 0..24): {v!r}")
        try:
            h = float(v)
        except (TypeError, ValueError):
            fail(f"bad time_of_day (a local hour 0..24): {v!r}")
        if math.isfinite(h):
            h = round(h, 2)                            # what is typed: 23.996 would become 24, which qstep refuses
        if not (math.isfinite(h) and 0.0 <= h < 24.0):
            fail(f"time_of_day must be a local hour within 0..23.99 (12 = noon): {v!r}")
        out["time_of_day"] = h
        methods = w.get("time_methods")
        if methods is not None:
            if not isinstance(methods, list) or not methods or any(m not in TIME_METHODS for m in methods) \
                    or len(set(methods)) != len(methods):
                fail(f"time_methods must be a list of distinct methods among {sorted(TIME_METHODS)}: {methods!r}")
            out["time_methods"] = list(methods)
        if w.get("time_repin") is not None:
            if not isinstance(w["time_repin"], bool):
                fail(f"time_repin must be true or false: {w['time_repin']!r}")
            if not w["time_repin"]:
                out["time_repin"] = False
    elif w.get("time_methods") is not None or w.get("time_repin") is not None:
        fail("time_methods / time_repin without time_of_day")
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
        v = w["light_wait_ms"]
        try:
            if isinstance(v, bool):
                raise TypeError
            ms = int(v)
        except (TypeError, ValueError):
            fail(f"bad light_wait_ms: {v!r}")
        if not 0 <= ms <= 30000:
            fail(f"light_wait_ms must be within 0..30000: {ms}")
        out["light_wait_ms"] = ms
    if w.get("need_daylight"):
        if out.get("time_of_day") is None and not out.get("weather"):
            fail("need_daylight without time_of_day or weather: nothing would make it daylight")
        out["need_daylight"] = True
    return out


def classify(sky, night_max=NIGHT_SKY_MAX, day_min=DAY_SKY_MIN):
    if sky is None:
        return "unread"
    if sky >= day_min:
        return "daylight"
    if sky <= night_max:
        return "night"
    return "unclear"


def classify_corners(v):
    return classify(v, NIGHT_CORNER_MAX, DAY_CORNER_MIN)


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


def measures(png, rows=SKY_ROWS):
    """(sky, corners) of one screenshot: the mean of its top rows and of its top fifth's outer quarters."""
    from PIL import Image          # numpy and Pillow: the runner's venv; imported here so the judge does not need them
    import numpy as np
    im = np.asarray(Image.open(png).convert("RGB"), np.float64)
    h, w = im.shape[:2]
    q = max(1, w // 4)
    corners = np.concatenate([im[:max(1, h // 5), :q].ravel(), im[:max(1, h // 5), w - q:].ravel()])
    return float(im[:rows].mean()), float(corners.mean())


def brightness(png, rows=SKY_ROWS):
    return measures(png, rows)[0]


def reading(x):
    """A try's last sky reading: its second shot (taken after another light_wait_ms when the first did not read as
    asked) or else its first."""
    for k in ("sky_late", "sky"):
        if isinstance(x.get(k), (int, float)) and not isinstance(x.get(k), bool):
            return float(x[k])
    return None


def probe_light(probes):
    """{"n", "corners", "class", "night": [labels], "unclear": [labels]} over the probe shots that were measured, or
    None. The median decides; single probes vary (a shot into a slope or a shadow)."""
    pr = [(str(p.get("label") or f"pt{k}"), float(p["corners"])) for k, p in enumerate(probes or [])
          if isinstance(p, dict) and isinstance(p.get("corners"), (int, float)) and not isinstance(p["corners"], bool)]
    if not pr:
        return None
    med = round(float(statistics.median(c for _, c in pr)), 1)
    return {"n": len(pr), "corners": med, "class": classify_corners(med),
            "night": [lab for lab, c in pr if classify_corners(c) == "night"],
            "unclear": [lab for lab, c in pr if classify_corners(c) == "unclear"]}


def verdict(test, light, probes=None):
    """None when `test` asked for no time of day and no weather. Else a dict:
      light     daylight | night | unclear | unread: the run's light. With probe shots measured (terrain) their corner
                median decides, else the arrival camera's last reading after the commands;
      tested    False when the arrival already read as the requested hour (the commands were not tested), True when
                it did not, None when there was no reading before;
      credited  the time command after which the arrival camera's sky first read as asked ("late": on its second shot),
                None when none did; effect: the sky changed by EFFECT_MIN or more (None: a reading is missing);
      replies   console errors read after the commands ("SetLocalTime only works on a planet.");
      sky       [before, after] at the arrival camera; probes: probe_light; detail: one line for the judge."""
    hour = test.get("time_of_day")
    if hour is None and not test.get("weather"):
        return None
    if not isinstance(light, dict):
        return {"light": "unread", "effect": None, "tested": None, "credited": None, "late": False, "replies": [],
                "sky": [None, None], "probes": probe_light(probes),
                "detail": "no light observations (the step ended before the time of day was set)"}
    before = (light.get("before") or {}).get("sky")
    tries = [x for x in light.get("tries") or [] if isinstance(x, dict)]
    after = next((reading(x) for x in reversed(tries) if reading(x) is not None), None)
    want = expected(hour)
    effect = None if after is None or before is None else abs(after - before) >= EFFECT_MIN
    if before is None:
        tested = None
    else:
        tested = want is None or classify(before) != want
    timed = [x for x in tries if x.get("method") != "weather"]
    credit = next((x for x in timed if done(before, reading(x), hour)), None) if hour is not None else None
    late = bool(credit) and reading(credit) is not None and credit.get("sky_late") is not None
    import console_plan            # the judge only: qstep.ps1 runs `measure` from a folder that may not have it
    replies = []
    for x in tries:
        if isinstance(x.get("ocr"), str):
            r = console_plan.reply(str(x.get("cmd", "")), x["ocr"])
            if r["status"] == "error":
                replies.append(f"{x.get('cmd')}: {r['note']}")
    pl = probe_light(probes)
    cam = classify(after)
    cls = pl["class"] if pl else cam

    def fmt(v):
        return "-" if v is None else f"{v:.1f}"
    typed = "; ".join(str(x.get("cmd", "?")) for x in tries) or "nothing typed"
    what = f"local hour {hour_text(hour)}" if hour is not None else f"weather {test.get('weather')}"
    detail = f"{what}: sky {fmt(before)} -> {fmt(after)} after {typed}"
    if replies:
        detail += " (console: " + "; ".join(replies) + ")"
    if after is None:
        detail += "; no sky reading after the commands"
    elif tested is False:
        detail += f"; already {classify(before)} at the arrival: the time commands were not tested"
    elif credit is not None:
        detail += f"; {cam} after {credit.get('cmd')}" + (" (on its second shot)" if late else "")
        k = timed.index(credit)
        if k:
            detail += f" ({k} earlier command{'s' if k > 1 else ''} without a visible change, also on a second shot " \
                      f"after another wait)" if all(x.get("sky_late") is not None for x in timed[:k]) else \
                f" ({k} earlier command{'s' if k > 1 else ''} without a visible change within light_wait_ms)"
    elif effect is False:
        detail += f"; no effect: {cam}"
    else:
        detail += f"; {cam}" + (" (no reading before the commands)" if before is None else "")
    if pl:
        detail += f"; probes: {pl['n']} measured, corner median {pl['corners']:.1f} -> {pl['class']}"
        if pl["night"]:
            detail += f", night at {', '.join(pl['night'])}"
        if after is not None and cam != pl["class"]:
            detail += f" (the arrival camera read {cam}: the probes decide)"
    detail += f" => {cls}"
    if cls in ("daylight", "night") and want not in (None, cls):
        detail += f" (asked for {want})"
    if pl and credit is None and tested is not False and want is not None and pl["class"] == want and cam != want:
        detail += "; whether the commands acted is unknown (the arrival camera never read as asked)"
    return {"light": cls, "effect": effect, "tested": tested,
            "credited": credit.get("cmd") if credit else None,
            "late": late,
            "replies": replies, "sky": [before, after], "probes": pl, "detail": detail}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("measure")
    m.add_argument("png")
    m.add_argument("--before", type=float, default=None)
    m.add_argument("--hour", type=float, default=None)
    a = ap.parse_args(argv)
    try:
        sky, corners = (round(v, 1) for v in measures(a.png))
    except Exception as e:  # noqa: BLE001 - an unreadable shot is a missing observation, never a crash of the step
        print(json.dumps({"sky": None, "corners": None, "class": "unread", "corner_class": "unread", "done": False,
                          "error": str(e)[:120]}))
        return 1
    print(json.dumps({"sky": sky, "corners": corners, "class": classify(sky), "corner_class": classify_corners(corners),
                      "done": done(a.before, sky, a.hour)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
