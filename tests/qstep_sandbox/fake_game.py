"""SANDBOX ONLY: a simulated Starfield console for tests/test_qstep_sandbox.py. No game, no keys, no windows.
State lives in the JSON file named by $FAKE_STATE.
usage: fake_game.py type <input.ps1 sequence> | screen | readpos [ref]
Scenario knobs in the state: speed (m/s, 0 = the actor never moves), isid_ok (GetIsID answers 1 for the right base),
self_fmt (hex | paren | none), lose_selection (every console open clears the selection), spawn_fails, clear_fails
(ClearConsole leaves the log), accepts (the one walk command that works), anchor_id / anchor_pos, arrival."""
import json
import math
import os
import sys
import time

P = os.environ["FAKE_STATE"]


def actor_pos(s, a):
    if a.get("target") and s["speed"] > 0 and not a.get("disabled"):
        sx, sy, sz = a["start"]
        tx, ty, _ = s["player"]
        d = math.hypot(tx - sx, ty - sy)
        go = min(s["speed"] * (time.time() - a["cmd_at"]), max(d - 1.2, 0))
        if d > 0:
            return [sx + (tx - sx) / d * go, sy + (ty - sy) / d * go, sz]
    return list(a["pos"])


def selected(s):
    return s["actors"].get(s.get("sel") or "")


def run(s, cmd):
    low = cmd.lower()
    if low == "clearconsole" and not s.get("clear_fails"):
        s["log"] = []
        return
    s["log"].append(cmd)                                   # the console echoes what was typed
    w = cmd.split()
    a = selected(s)
    if low.startswith("player.setpos "):
        s["player"]["xyz".index(w[1])] = float(w[2])
    elif low.startswith("coc "):
        s["cell"], s["player"] = w[1], list(s["arrival"])
    elif low.startswith("player.placeatme "):
        if s.get("spawn_fails"):
            s["log"].append("Item not found")
            return
        rid = f"FF{0x800 + len(s['actors']):06X}"
        s["actors"][rid] = {"base": w[1].upper(), "pos": [s["player"][0] + 0.8, s["player"][1], s["player"][2]]}
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
            a["start"], a["target"], a["cmd_at"] = actor_pos(s, a), True, time.time()
        elif a is not None:
            s["log"].append("Script command not found")
    elif low == "disable" and a is not None:
        a["pos"], a["target"], a["disabled"] = actor_pos(s, a), False, True
    elif low == "markfordelete" and a is not None:
        a["deleted"] = True
    elif low == "getdisabled":
        s["log"].append(f"GetDisabled >> {'1.00' if a and a.get('disabled') else '0.00'}")


def main():
    with open(P) as f:
        s = json.load(f)
    if sys.argv[1] == "type":
        typed = ""
        for step in sys.argv[2].split("|"):
            k, _, v = step.partition(":")
            if k == "type":
                typed += v
            elif k == "key" and v == "enter":
                run(s, typed)
                typed = ""
            elif k == "key" and v == "grave":
                s["console"] = not s.get("console")
                if s["console"] and s.get("lose_selection"):
                    s["sel"] = None
    elif sys.argv[1] == "screen":
        print("\n".join(s["log"][-9:]))                    # the console shows about nine lines
        return
    elif sys.argv[1] == "readpos":
        ref = sys.argv[2].upper() if len(sys.argv) > 2 else ""
        if not ref:
            print(" ".join(f"{v:.2f}" for v in s["player"]))
        elif ref == s.get("anchor_id"):
            s["sel"] = ref                                 # readpos -Ref selects with prid
            print(" ".join(f"{v:.2f}" for v in s["anchor_pos"]))
        else:
            print("fail")
    with open(P, "w") as f:
        json.dump(s, f, indent=1)


main()
