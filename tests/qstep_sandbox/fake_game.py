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
closed."""
import json
import math
import os
import sys
import time

P = os.environ["FAKE_STATE"]
STATIC = "0024A824"


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
                    if s.get("crosshair", STATIC):         # opening the console selects what the crosshair is on
                        s["sel"] = s.get("crosshair", STATIC)
                    elif s.get("lose_selection"):
                        s["sel"] = None
                else:                                      # the game runs again: placed actors become ready
                    for a in s["actors"].values():
                        a.pop("pending", None)
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
            print("fail")
    with open(P, "w") as f:
        json.dump(s, f, indent=1)


main()
