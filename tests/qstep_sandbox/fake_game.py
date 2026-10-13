"""SANDBOX ONLY: a simulated Starfield console for tests/test_qstep_sandbox.py. No game, no keys, no windows.
State lives in the JSON file named by $FAKE_STATE.
usage: fake_game.py type <input.ps1 sequence, or - for $FAKE_SEQ> | screen | readpos [ref]

The defaults model what the runner saw in game (N0_base in QASmoke, 2026-10-11):
  - ClearConsole does not clear the console: its echo goes below the older lines (clear_fails, default true);
  - opening the console selects the ref under the crosshair, the floor static 0024A824 (crosshair; statics hold its
    position);
  - an actor placed while the console is open (the game paused) is only ready once the console closes
    (spawn_deferred): before that PickLastRef names its id but the selection stays where it was, so GetIsID reads 0.00
    and GetSelf names the static, as the N0_base spawn session read;
  - placeatme prints three "GetInFaction >> 0.00" lines of the game's own (faction_lines);
  - replies "PickLastRef: (FF000800)", "GetIsID >> 1.00", "GetSelf >> (ff000800)", "GetDisabled >> 1";
  - OCR quirks in what "screen" returns (ocr_quirks): l for I ("GetlsID", "GetlslD", "GetlnFaction"), "> >" for ">>",
    "Clear Console", "Get Disabled", "Get Po s"; about nine lines are visible.
Other knobs: speed (m/s, 0 = the actor never moves), isid_ok (GetIsID answers 1 for the right base), self_fmt
(paren | hex | none), plr_selects (false: plr names the last ref but never selects it), prid_fails (prid never selects),
lose_selection (without a crosshair ref: every console open clears the selection), spawn_fails, accepts (the one walk
command that works), anchor_id / anchor_pos, arrival, fall ({"height", "speed"}: after coc the player falls from
arrival z + height at speed m/s until the arrival z), layout ("inline" | "column": labels first, then values; echo
arguments drift into the value column, a lone "y" is lost).
"typed" keeps every command the console received; "clock" is the game time, which runs only while the console is
closed.
Time of day: local_time (default 22.0, night) changes on "SetLocalTime <h>" (method slt), "SetLocalTime <h> 1"
(slt_galaxy) or 'cgf "Game.SetLocalTime" <h>' (cgf) when that method is in time_works (default ["slt"]; [] = no command
has an effect); "fw <id> [1]" sets weather, and weather_sky {id: brightness} overrides the sky. "shot <png>" writes a
screenshot whose top 200 rows have the sky's brightness (110 by day, 6..18 h, else 12) and whose lower rows are ground.
slt_error: the console command SetLocalTime prints "SetLocalTime only works on a planet." and changes nothing (cgf
still works when listed in time_works); time_lag_shots: after a time change the next N screenshots still show the old
sky (a slow change); drift_per_open: every console open moves the local time on by that many hours (game time passing
between console sessions, e.g. during the probes); land_z: a player.setpos z lands at that height at once.
INI settings (ini, default INI below, made-up values): GetINI "<name:Section>" prints "INISetting <name:Section> >> <v>"
(%i / %.4f) or ">> NOT FOUND"; SetINI on a known setting prints nothing, on an unknown one 'INI setting "<name:Section>"
does not exist' (the reply formats in Starfield.exe 1.16.244).
Load doors (door_trip): doors [{"cell", "pos", "auto", "works", "dest_cell", "dest_pos", "ref", "ref_pos"}]: readpos
<ref> of a door's "ref" prints its "ref_pos" (default its pos: what getpos reports); an automatic door ("auto")
loads when the player comes within auto_dist (3 m, Starfield.esm fAutoDoorActivateDistance) while the game runs (a walk
step, or the console closing after a setpos); a door without "auto" loads on E within 2.5 m, where prompt_visible.py
says yes. A load moves the player to dest_pos in dest_cell and hides the HUD for load_secs (hud_visible.py says no).
"player.setangle z <deg>" sets the heading; "hold:w,<ms>" walks walk_speed m/s along it (walk_blocked: not at all).
"player.GetInCell <cell>" prints "GetInCell >> 1.00" / "0.00". "save <name>" writes <name>.sfs (player, cell) into
$FO4SF_SAVES_DIR (save_fails: nothing written); "load <name>" restores it (reload_shift added to the position), closes
the console and hides the HUD for load_secs; a load of a missing save prints "Save not found" and the console stays
open."""
import json
import math
import os
import re
import struct
import sys
import time
import zlib

P = os.environ["FAKE_STATE"]
STATIC = "0024A824"
INI = {"bBorderRegionsEnabled:General": 1, "fPlayableAreaX:General": 3200.0, "uPlayableSpaceOverlayCellBuffer:Planet": 2}


def game_time(s):
    """Seconds of game time: the clock runs only while the console is closed (the console pauses the game, the
    supported hypothesis qstep.ps1's t_game rests on). Actors walk on it; the arrival fall uses the wall clock."""
    c = s.setdefault("clock", {"game": 0.0, "since": time.time()})
    return c["game"] + (time.time() - c["since"] if c["since"] is not None else 0.0)


def actor_pos(s, a):
    if a.get("target") and s["speed"] > 0 and not a.get("disabled"):
        sx, sy, sz = a["start"]
        tx, ty, _ = s["player"]
        d = math.hypot(tx - sx, ty - sy)
        go = min(s["speed"] * (game_time(s) - a["cmd_at"]), max(d - 1.2, 0))
        if d > 0:
            return [sx + (tx - sx) / d * go, sy + (ty - sy) / d * go, sz]
    return list(a["pos"])


def player_pos(s):
    p = list(s["player"])
    f = s.get("falling")
    if f:
        p[2] = max(f["ground"], f["top"] - f["speed"] * (time.time() - f["t"]))
    return p


def statics(s):
    return s.setdefault("statics", {STATIC: {"pos": [0.0, 0.0, -0.1]}})


def door_load(s, d):
    """The player goes through door d: its destination, a loading screen for load_secs."""
    s["cell"], s["player"], s["falling"] = d["dest_cell"], list(d["dest_pos"]), None
    s["loading_until"] = time.time() + float(s.get("load_secs", 2.0))
    s.setdefault("loads", []).append(d.get("name", d["dest_cell"]))


def auto_doors(s):
    """An automatic load door within auto_dist of the player (same cell, the game running) loads: True if one did."""
    p = player_pos(s)
    for d in s.get("doors", []):
        if d.get("auto") and d.get("works", True) and (d.get("cell") or "").lower() == (s.get("cell") or "").lower() \
                and math.dist(p, d["pos"]) <= float(s.get("auto_dist", 3.0)):
            door_load(s, d)
            return True
    return False


def walk(s, ms):
    """hold:w: walk along the heading in 5 cm steps, an automatic door in range loads at once."""
    if s.get("walk_blocked"):
        return
    h = math.radians(float(s.get("heading", 0.0)))
    dist = float(s.get("walk_speed", 3.0)) * ms / 1000.0
    p = player_pos(s)
    s["falling"] = None
    for _ in range(int(dist / 0.05)):
        p = [p[0] + 0.05 * math.sin(h), p[1] + 0.05 * math.cos(h), p[2]]
        s["player"] = p
        if auto_doors(s):
            return


def selected(s):
    """('actor', a) | ('static', st) | (None, None) for the console's selection."""
    sel = s.get("sel") or ""
    a = s["actors"].get(sel)
    if a is not None and not a.get("pending"):
        return "actor", a
    if sel in statics(s):
        return "static", statics(s)[sel]
    return None, None


def select(s, rid):
    """A ref that is not ready (placed while the console was open) cannot be selected yet."""
    a = s["actors"].get(rid)
    if (a is not None and not a.get("pending")) or rid in statics(s) or rid == s.get("anchor_id"):
        s["sel"] = rid


def run(s, cmd):
    low = cmd.lower()
    s.setdefault("typed", []).append(cmd)
    if low == "clearconsole" and not s.get("clear_fails", True):
        s["log"] = []
        return
    s["log"].append(cmd)                                   # the console echoes what was typed
    w = cmd.split()
    kind, a = selected(s)
    if low.startswith("player.setpos "):
        s["player"] = player_pos(s)
        s["falling"] = None
        s["player"]["xyz".index(w[1])] = float(w[2])
        if w[1] == "z" and s.get("land_z") is not None:    # the player lands at once on ground at land_z
            s["player"][2] = float(s["land_z"])
    elif low.startswith("player.setangle z "):
        s["heading"] = float(w[2])
    elif low.startswith("player.getincell "):
        s["log"].append(f"GetInCell >> {'1.00' if (s.get('cell') or '').lower() == w[1].lower() else '0.00'}")
    elif low.startswith("save "):
        if not s.get("save_fails"):
            d = os.environ.get("FO4SF_SAVES_DIR") or os.path.dirname(P)
            with open(os.path.join(d, w[1] + ".sfs"), "w") as f:
                json.dump({"player": player_pos(s), "cell": s.get("cell")}, f)
    elif low.startswith("load "):
        f = os.path.join(os.environ.get("FO4SF_SAVES_DIR") or os.path.dirname(P), w[1] + ".sfs")
        if not os.path.exists(f):
            s["log"].append("Save not found")
            return
        with open(f) as fh:
            sv = json.load(fh)
        shift = s.get("reload_shift") or [0.0, 0.0, 0.0]
        s["player"] = [sv["player"][k] + shift[k] for k in range(3)]
        s["cell"], s["falling"], s["console"] = sv["cell"], None, False      # the load closes the console
        s["clock"] = {"game": game_time(s), "since": time.time()}
        s["loading_until"] = time.time() + float(s.get("load_secs", 2.0))
    elif low.startswith("coc "):
        s["cell"], s["player"] = w[1], list(s["arrival"])
        if s.get("fall"):
            s["falling"] = {"ground": s["arrival"][2], "top": s["arrival"][2] + s["fall"]["height"],
                            "speed": s["fall"]["speed"], "t": time.time()}
    elif low.startswith("player.placeatme "):
        if s.get("spawn_fails"):
            s["log"].append("Item not found")
            return
        rid = f"FF{0x800 + len(s['actors']):06X}"
        p = player_pos(s)
        s["actors"][rid] = {"base": w[1].upper(), "pos": [p[0] + 0.8, p[1], p[2]],
                            "pending": bool(s.get("console")) and s.get("spawn_deferred", True)}
        s["last"] = rid
        if s.get("faction_lines", True):
            s["log"] += ["GetInFaction >> 0.00"] * 3
    elif low == "plr":
        if s.get("last"):
            s["log"].append(f"PickLastRef: ({s['last']})")
            if s.get("plr_selects", True):
                select(s, s["last"])
    elif low.startswith("prid "):
        rid = w[1].upper()
        if s.get("prid_fails"):
            return
        if rid in s["actors"] or rid in statics(s) or rid == s.get("anchor_id"):
            select(s, rid)
        else:
            s["log"].append("Reference not found")
    elif low.startswith("getisid "):
        if kind is None:
            s["log"].append("Missing reference")
        else:
            ok = kind == "actor" and a["base"] == w[1].upper() and s.get("isid_ok", True)
            s["log"].append(f"GetIsID >> {'1.00' if ok else '0.00'}")
    elif low == "getself":
        fmt = s.get("self_fmt", "paren")
        if kind is not None and fmt != "none":
            s["log"].append(f"GetSelf >> {s['sel']}" if fmt == "hex" else f"GetSelf >> ({s['sel'].lower()})")
    elif low.startswith("getpos "):
        sel = s.get("sel")
        if sel is not None and sel == s.get("anchor_id"):
            p = s["anchor_pos"]
        elif kind == "actor":
            p = actor_pos(s, a)
        elif kind == "static":
            p = a["pos"]
        else:
            s["log"].append("Missing reference")
            return
        ax = w[1].upper()
        s["log"].append(f"GetPos: {ax} >> {p['XYZ'.index(ax)]:.2f}")
    elif low in ("pathtoref player", 'cf "actor.pathtoreference" player 1.0', "setplayerteammate 1"):
        if kind == "actor" and s.get("accepts", "pathtoref player") == low:
            a["start"], a["target"], a["cmd_at"] = actor_pos(s, a), True, game_time(s)
        elif kind is not None:
            s["log"].append("Script command not found")
    elif low == "disable" and kind is not None:
        if kind == "actor":
            a["pos"], a["target"] = actor_pos(s, a), False
        a["disabled"] = True                               # a static too: the tests check that never happens
    elif low == "markfordelete" and kind is not None:
        a["deleted"] = True
    elif low == "getdisabled":
        s["log"].append(f"GetDisabled >> {1 if a and a.get('disabled') else 0}")
    elif low.startswith(("setlocaltime ", 'cgf "game.setlocaltime" ')):
        method = "cgf" if low.startswith("cgf") else ("slt_galaxy" if w[-1] == "1" and len(w) == 3 else "slt")
        if method != "cgf" and s.get("slt_error"):
            s["log"].append("SetLocalTime only works on a planet.")
        elif method in s.get("time_works", ["slt"]):
            old = sky(s)
            s["local_time"] = float(w[2] if method == "cgf" else w[1])
            if s.get("time_lag_shots"):
                s["lag"] = {"left": int(s["time_lag_shots"]), "sky": old}
    elif low.startswith("fw "):
        s["weather"] = w[1].upper()
    elif low.startswith(("getini ", "setini ")):
        m = re.fullmatch(r'(getini|setini) "([^"]+)"(?: (\S+))?', cmd, re.I)
        ini = s.setdefault("ini", dict(INI))
        key = m.group(2) if m else ""
        if low.startswith("getini"):
            v = ini.get(key)
            s["log"].append(f"INISetting {key} >> " + ("NOT FOUND" if v is None else
                                                      f"{v:.4f}" if isinstance(v, float) else f"{v}"))
        elif key in ini and m.group(3) is not None:
            ini[key] = type(ini[key])(float(m.group(3)))
        else:
            s["log"].append(f'INI setting "{key}" does not exist')


def sky(s):
    wx = s.get("weather_sky", {}).get(s.get("weather") or "")
    if wx is not None:
        return wx
    return 110 if 6.0 <= s.get("local_time", 22.0) <= 18.0 else 12


def write_png(path, value, w=8, h=300):
    """RGB PNG: the top 200 rows at the sky's brightness, the rest ground (40)."""
    rows = b"".join(b"\0" + bytes([value if y < 200 else 40] * 3 * w) for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def column(lines):
    """The OCR's column layout: the left column (command names, reply labels) first, then the right one (values and
    the arguments that drifted off their echo); a lone 'y' argument is lost."""
    left, right = [], []
    for ln in lines:
        if " >> " in ln:
            lab, val = ln.split(" >> ", 1)
            left.append(lab + " > >")
            right.append(val)
        elif " " in ln and not ln.startswith(("Missing", "Reference", "Script", "Item")):
            cmd, arg = ln.split(" ", 1)
            left.append(cmd)
            if arg != "y":
                right.append(arg)
        else:
            left.append(ln)
    return left + right


def quirks(ln):
    """OCR misreadings seen in the runner's console OCR (2026-10-11)."""
    for a, b in (("GetIsID >>", "GetlslD"), ("GetIsID", "GetlsID"), ("GetInFaction", "GetlnFaction"),
                 ("GetInCell", "GetlnCell"),
                 ("INISetting", "lNlSetting"), ("GetINI", "GetlNl"), ("Enabled", "EnabIed"),
                 ("ClearConsole", "Clear Console"), ("GetDisabled", "Get Disabled"), ("GetPos: X", "Get Po s: X"),
                 (">>", "> >")):
        ln = ln.replace(a, b)
    return ln


def main():
    with open(P) as f:
        s = json.load(f)
    if sys.argv[1] == "type":
        typed = ""
        seq = os.environ.get("FAKE_SEQ", "") if sys.argv[2] == "-" else sys.argv[2]   # '-': input.ps1's $Seq
        for step in seq.split("|"):
            k, _, v = step.partition(":")
            if k == "type":
                typed += v
            elif k == "key" and v == "enter":
                run(s, typed)
                typed = ""
            elif k == "key" and v == "grave":
                now = game_time(s)
                s["console"] = not s.get("console")
                s["clock"] = {"game": now, "since": None if s["console"] else time.time()}
                if s["console"]:
                    if s.get("drift_per_open"):            # game time passed since the last console session
                        s["local_time"] = (s.get("local_time", 22.0) + s["drift_per_open"]) % 24
                    if s.get("crosshair", STATIC):         # opening the console selects what the crosshair is on
                        s["sel"] = s.get("crosshair", STATIC)
                    elif s.get("lose_selection"):
                        s["sel"] = None
                else:                                      # the game runs again: placed actors become ready
                    for a in s["actors"].values():
                        a.pop("pending", None)
                    auto_doors(s)                          # a setpos left the player in an automatic door's range
            elif k == "hold" and v.startswith("w,") and not s.get("console"):
                walk(s, int(v[2:]))
            elif k == "key" and v == "e" and not s.get("console"):
                p = player_pos(s)
                for d in s.get("doors", []):
                    if not d.get("auto") and d.get("works", True) and math.dist(p, d["pos"]) <= 2.5 and \
                            (d.get("cell") or "").lower() == (s.get("cell") or "").lower():
                        door_load(s, d)
                        break
    elif sys.argv[1] == "shot":
        lag = s.get("lag") or {}
        if lag.get("left", 0) > 0:                         # the sky has not followed the new time yet
            write_png(sys.argv[2], lag["sky"])
            lag["left"] -= 1
        else:
            write_png(sys.argv[2], sky(s))
    elif sys.argv[1] == "screen":
        lines = s["log"][-9:]                              # the console shows about nine lines
        if s.get("layout") == "column":
            lines = column(lines)
        if s.get("ocr_quirks", True):
            lines = [quirks(ln) for ln in lines]
        print("\n".join(lines))
        return
    elif sys.argv[1] == "readpos":
        ref = sys.argv[2].upper() if len(sys.argv) > 2 else ""
        if not ref:
            print(" ".join(f"{v:.2f}" for v in player_pos(s)))
        elif ref == s.get("anchor_id"):
            s["sel"] = ref                                 # readpos -Ref selects with prid
            print(" ".join(f"{v:.2f}" for v in s["anchor_pos"]))
        else:
            d = next((d for d in s.get("doors", []) if (d.get("ref") or "").upper() == ref), None)
            if d is None:
                print("fail")
            else:                                          # a door's getpos: ref_pos (e.g. its unmerged local position)
                s["sel"] = ref
                print(" ".join(f"{v:.2f}" for v in d.get("ref_pos") or d["pos"]))
    with open(P, "w") as f:
        json.dump(s, f, indent=1)


main()
