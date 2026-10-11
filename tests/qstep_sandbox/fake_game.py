"""SANDBOX ONLY: a simulated Starfield console for tests/test_qstep_sandbox.py. No game, no keys, no windows.
State lives in the JSON file named by $FAKE_STATE.
usage: fake_game.py type <input.ps1 sequence, or - for $FAKE_SEQ> | screen | readpos [ref]
Scenario knobs in the state: speed (m/s, 0 = the actor never moves), isid_ok (GetIsID answers 1 for the right base),
self_fmt (hex | paren | none), lose_selection (every console open clears the selection), spawn_fails, clear_fails
(ClearConsole leaves the log), accepts (the one walk command that works), anchor_id / anchor_pos, arrival,
fall ({"height", "speed"}: after coc the player falls from arrival z + height at speed m/s until the arrival z),
layout ("inline" | "column": how the OCR lists the screen, modelled on real console OCR of 2026-10-11: labels first,
then values; echo arguments drift into the value column, a lone "y" is lost).
"typed" keeps every command the console received (ClearConsole does not clear it); "clock" is the game time, which
runs only while the console is closed."""
import json
import math
import os
import sys
import time

P = os.environ["FAKE_STATE"]


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


def selected(s):
    return s["actors"].get(s.get("sel") or "")


def run(s, cmd):
    low = cmd.lower()
    s.setdefault("typed", []).append(cmd)
    if low == "clearconsole" and not s.get("clear_fails"):
        s["log"] = []
        return
    s["log"].append(cmd)                                   # the console echoes what was typed
    w = cmd.split()
    a = selected(s)
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
        s["actors"][rid] = {"base": w[1].upper(), "pos": [p[0] + 0.8, p[1], p[2]]}
        s["last"] = rid
    elif low == "plr":
        s["sel"] = s.get("last")
    elif low.startswith("prid "):
        if w[1].upper() in s["actors"] or w[1].upper() == s.get("anchor_id"):
            s["sel"] = w[1].upper()
        else:
            s["log"].append("Reference not found")
    elif low.startswith("getisid "):
        if a is None:
            s["log"].append("Missing reference")
        else:
            ok = a["base"] == w[1].upper() and s.get("isid_ok", True)
            s["log"].append(f"GetIsID >> {'1.00' if ok else '0.00'}")
    elif low == "getself":
        fmt = s.get("self_fmt", "hex")
        if a is not None and fmt != "none":
            s["log"].append(f"GetSelf >> {s['sel']}" if fmt == "hex" else f"GetSelf >> ({s['sel']})")
    elif low.startswith("getpos "):
        sel = s.get("sel")
        if sel is not None and sel == s.get("anchor_id"):
            p = s["anchor_pos"]
        elif a is not None:
            p = actor_pos(s, a)
        else:
            s["log"].append("Missing reference")
            return
        ax = w[1].upper()
        s["log"].append(f"GetPos: {ax} >> {p['XYZ'.index(ax)]:.2f}")
    elif low in ("pathtoref player", 'cf "actor.pathtoreference" player 1.0', "setplayerteammate 1"):
        if a is not None and s.get("accepts", "pathtoref player") == low:
            a["start"], a["target"], a["cmd_at"] = actor_pos(s, a), True, game_time(s)
        elif a is not None:
            s["log"].append("Script command not found")
    elif low == "disable" and a is not None:
        a["pos"], a["target"], a["disabled"] = actor_pos(s, a), False, True
    elif low == "markfordelete" and a is not None:
        a["deleted"] = True
    elif low == "getdisabled":
        s["log"].append(f"GetDisabled >> {'1.00' if a and a.get('disabled') else '0.00'}")


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
                if s["console"] and s.get("lose_selection"):
                    s["sel"] = None
    elif sys.argv[1] == "screen":
        lines = s["log"][-9:]                              # the console shows about nine lines
        print("\n".join(column(lines) if s.get("layout") == "column" else lines))
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
