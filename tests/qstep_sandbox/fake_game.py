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
(paren | hex | none | zero: "(00000000)"), plr_misses (that many plr name nothing), plr_selects (false: plr names the
last ref but never selects it), prid_fails (prid never selects),
lose_selection (without a crosshair ref: every console open clears the selection), spawn_fails, accepts (the one walk
command that works), anchor_id / anchor_pos, arrival, fall ({"height", "speed"}: after coc the player falls from
arrival z + height at speed m/s until the arrival z), coc_same_cell_stays (a coc into the cell the player is in
leaves the player where they stand: the v6e stairs retest's miss, a supported hypothesis), layout ("inline" | "column": labels first, then values; echo
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
FO4SF_Probe.Resolve / MoveTo (cgf; the scripted door's Step 0): probe_refs {"<plugin-local decimal id>": [x, y, z]} are
the references GetFormFromFile finds; the replies go to the bridge log only; a MoveTo moves the player there plus the
offset and hides the HUD for load_secs.
Load doors (door_trip): doors [{"cell", "pos", "auto", "works", "dest_cell", "dest_pos", "ref", "ref_pos"}]: readpos
<ref> of a door's "ref" prints its "ref_pos" (default its pos: what getpos reports); an automatic door ("auto")
loads when the player comes within auto_dist (3 m, Starfield.esm fAutoDoorActivateDistance) while the game runs (a walk
step, or the console closing after a setpos); a door without "auto" loads on E within 2.5 m, where prompt_visible.py
says yes. A load moves the player to dest_pos in dest_cell and hides the HUD for load_secs (hud_visible.py says no).
"player.setangle z <deg>" sets the heading; "hold:w,<ms>" (and input.ps1's guarded "holdg:w,<ms>") walks walk_speed m/s
along it (walk_blocked: not at all; heading_bias degrees are added to the heading the player really walks).
"player.getpos x|y|z" prints "GetPos: X >> <v>" (the player's position; getpos_misread [n, ...]: the n-th x reply, from 1,
drops its minus sign as the OCR did; getpos_lost [n, ...]: the n-th z reply is not on screen at all). readpos_calls
counts the readpos.ps1 runs (the walk may use it for the arrival only).
Ground (walk): ground {"z0", "sx", "sy", "decks": [[x0, y0, x1, y1, z]], "holes": [[x0, y0, x1, y1]],
"walls": [[x0, y0, x1, y1]], "boundary": [[x0, y0, x1, y1]], "boundary_shift": [dx, dy, dz], "stop_box": [x0, y0, x1, y1]}
in the game's frame: a walking player stands on the plane z0 + sx * x + sy * y, or on a deck's z inside it; a wall stops
the walk; a hole drops the player 80 m (no ground); entering a boundary box shows the "BOUNDARY REACHED" box (popup: what
the centre OCR reads), moves the player by boundary_shift and stops the walk; entering stop_box creates the file
"stop_file" (the owner's STOP file appearing mid-hold: the sandbox input.ps1 then exits 5 as the real holdg does). A
player.setpos z lands on that ground at once.
"popup" prints the popup's text (the sandbox ocr.ps1 with a region), "" when none.
"player.GetInCell <cell>" prints "GetInCell >> 1.00" / "0.00" for a form id in cell_ids ({id: cell EditorID}), or for
an EditorID when incell_editor_ids is set; otherwise the console's refusal of the first live run (2026-10-13): "Item
'<arg>' not found for parameter Cell." and "Compiled script not saved!". "save <name>" writes <name>.sfs (player, cell,
heading) into $FO4SF_SAVES_DIR (save_fails: nothing written); "load <name>" restores it (reload_shift added to the
position), closes the console and hides the HUD for load_secs; a load of a missing save prints "Save not found" and the
console stays open. A door's dest_heading is the heading after its load (the XTEL rotation); "readpos [ref] --angle"
prints the heading as a fourth value. garble_after_walks N: the first player read after the N-th walk step prints the
first live run's garble (garble_count times): the previous read's z, this read's x and z, as "99.74 -2195.27 99.41"
for (-2195.27, -1593.51, 99.41); walk_dz: every walk step changes z by that much (the live walk went down the cave
mouth, so the garble's x and z differ and pass Read-Pos's x == z filter). The sandbox readpos types its nonce
(fo4sfr<8 hex>) first, as the real one: the console echoes it and replies not found (the reply's wording is a
supported hypothesis; readpos relies on the echo alone).
Movable items (movable, movable_control): item_bases {base: {"height", "mass", "fixed"}}: placeatme of such a base puts
an item (an "actors" entry with item true) at the player's feet on the floor (+ item_offset); an item can also be put in
"actors" directly (the build's own placed item, read with readpos <ref>). Walking within 0.35 m of an item at least
push_min_h tall (0.08 m) and not heavier than push_max_kg pushes it 0.5 m ahead; a thinner one is walked over.
"ApplyHavokImpulse x y z m" on a selected item moves it dv x 0.3 m along the axis when dv = m / mass >= impulse_dv_min
(1.0; impulse_works false or a fixed item: never); "SetRigidBodyMass <kg>" sets its mass (setmass_reply: the console
prints that text instead; setmass_noop: accepted without a word and nothing changes); 'cf "ObjectReference.GetMass"'
prints "GetMass >> <kg>" (a made-up reply format; getmass_reply: that text instead, e.g. the "No script named ... is
attached to the object" that cf "Actor.PathToReference" got in N0_cf).
Combat (npc_nav combat_reads): "hostile" [base ids] engage the player (combat state 1, target 00000014) once the game runs
after their spawn, holding their ground; "StartCombat player" does the same for the selected actor unless
startcombat_fails. GetCombatState / GetCombatTarget / "GetLineOfSight player" reply "GetCombatState >> 1.00",
"GetCombatTarget >> (00000014)" ("(00000000)" without a target), "GetLineOfSight >> 1.00" (knob los): HYPOTHESES of the
in-game format; combat_fmt "int" prints "GetCombatState >> 1" and a bare target id, "refused" answers all three with
"Script command not found".
OCR thresholds: the sandbox ocr_prep.py keeps the threshold of the last prepared capture as "ocr_th"; isid_lost_at
[th, ...]: an OCR at one of those thresholds does not read the "GetIsID >>" reply lines (core64g_accept_1016 test
0002: the reply on activate_sel.png was lost at 135, and read at 130 and 145)."""
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
    if d.get("dest_heading") is not None:
        s["heading"] = float(d["dest_heading"])
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


def inside(box, p):
    return box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]


POPUP = "BOUNDARY REACHED Open the map to explore another region, or return to your ship. FAST TRAVEL TO SHIP B CANCEL"


def ground_z(s, p):
    """The walk ground under p (module doc), or None when there is none (a hole)."""
    g = s["ground"]
    if any(inside(b, p) for b in g.get("holes", [])):
        return None
    for d in g.get("decks", []):
        if inside(d, p):
            return float(d[4])
    return float(g.get("z0", 0.0)) + float(g.get("sx", 0.0)) * p[0] + float(g.get("sy", 0.0)) * p[1]


def mass_of(a):
    return float(a.get("mass_set", a.get("mass", 1.0)))


def push_items(s, p, h):
    """Movable items the walking player touches (within 0.35 m): one at least push_min_h tall (default 0.08 m) and not
    heavier than push_max_kg is pushed 0.5 m ahead of the player; a thinner one is walked over and stays (the model the
    staged movable_control queue tests: supported hypothesis, docs/ai/test-queue.md)."""
    for a in s["actors"].values():
        if not a.get("item") or a.get("disabled") or a.get("pending") or a.get("fixed"):
            continue
        q = a["pos"]
        if math.hypot(q[0] - p[0], q[1] - p[1]) > 0.35:
            continue
        if a.get("height", 0.1) < float(s.get("push_min_h", 0.08)) or mass_of(a) > float(s.get("push_max_kg", 1e9)):
            continue
        a["pos"] = [p[0] + 0.5 * math.sin(h), p[1] + 0.5 * math.cos(h), q[2]]


def impulse(s, a, w):
    """ApplyHavokImpulse <x> <y> <z> <magnitude> on a selected item: a speed change of magnitude / mass (kg m/s, the
    supported hypothesis) of at least impulse_dv_min (default 1.0) moves it dv x 0.3 m along the axis' horizontal part
    (impulse_works false, or a fixed item: nothing moves)."""
    ax, ay, mag = float(w[1]), float(w[2]), float(w[4])
    if a.get("fixed") or not s.get("impulse_works", True) or mag / mass_of(a) < float(s.get("impulse_dv_min", 1.0)):
        return
    n = math.hypot(ax, ay) or 1.0
    d = mag / mass_of(a) * 0.3
    q = a["pos"]
    a["pos"] = [q[0] + ax / n * d, q[1] + ay / n * d, q[2]]


def walk(s, ms):
    """hold:w: walk along the heading in 5 cm steps, an automatic door in range loads at once."""
    if s.get("walk_blocked") or s.get("popup"):
        return
    h = math.radians(float(s.get("heading", 0.0)) + float(s.get("heading_bias", 0.0)))
    dist = float(s.get("walk_speed", 3.0)) * ms / 1000.0
    s["walks"] = s.get("walks", 0) + 1
    p = player_pos(s)
    s["falling"] = None
    g = s.get("ground")
    dz = float(s.get("walk_dz", 0.0)) / max(1, int(dist / 0.05))
    for _ in range(int(dist / 0.05)):
        q = [p[0] + 0.05 * math.sin(h), p[1] + 0.05 * math.cos(h), p[2] + dz]
        if g is not None:
            if any(inside(b, q) for b in g.get("walls", [])):
                return                                     # blocked: the player stays where it was
            if any(inside(b, q) for b in g.get("boundary", [])):
                shift = g.get("boundary_shift") or [0.0, 0.0, 0.0]
                s["player"] = [q[k] + shift[k] for k in range(3)]
                s["popup"] = POPUP
                return
            if g.get("stop_box") and s.get("stop_file") and inside(g["stop_box"], q):
                open(s["stop_file"], "a").close()            # the owner's STOP file appears while W is held
            z = ground_z(s, q)
            if z is None:
                s["player"] = [q[0], q[1], q[2] - 80.0]      # fell through: no ground there
                return
            q[2] = z
        p = q
        s["player"] = p
        push_items(s, p, h)
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
    s.setdefault("events", []).append(cmd)                 # "events": the commands with the console's opens and closes
    if low == "clearconsole" and not s.get("clear_fails", True):
        s["log"] = []
        return
    s["log"].append(cmd)                                   # the console echoes what was typed
    w = cmd.split()
    kind, a = selected(s)
    if re.fullmatch(r"fo4sfr[0-9a-f]{8}", low):            # readpos's nonce: an unknown command, echoed and refused
        s["log"].append(f'Script command "{cmd}" not found.')
    elif low.startswith("player.setpos "):
        s["player"] = player_pos(s)
        s["falling"] = None
        s["player"]["xyz".index(w[1])] = float(w[2])
        if w[1] == "z" and s.get("land_z") is not None:    # the player lands at once on ground at land_z
            s["player"][2] = float(s["land_z"])
        if w[1] == "z" and s.get("ground") is not None:    # ... or on the walk ground
            z = ground_z(s, s["player"])
            if z is not None:
                s["player"][2] = z
    elif low.startswith("player.getpos "):
        ax = w[1].upper()
        v = player_pos(s)["XYZ".index(ax)]
        if ax == "X":
            s["getpos_x"] = s.get("getpos_x", 0) + 1
            if s["getpos_x"] in s.get("getpos_misread", []):
                v = abs(v)                                   # the OCR dropped the minus sign
        if ax == "Z":
            s["getpos_z"] = s.get("getpos_z", 0) + 1
            if s["getpos_z"] in s.get("getpos_lost", []):
                return                                       # the reply is not on screen (the OCR lost the line)
        s["log"].append(f"GetPos: {ax} >> {v:.2f}")
    elif low.startswith("player.setangle z "):
        s["heading"] = float(w[2])
    elif low.startswith("player.getincell "):
        ids = {k.upper(): v for k, v in (s.get("cell_ids") or {}).items()}
        cell = ids.get(w[1].upper()) or (w[1] if s.get("incell_editor_ids") else None)
        if cell is None:
            s["log"] += [f"Item '{w[1]}' not found for parameter Cell.", "Compiled script not saved!"]
        else:
            s["log"].append(f"GetInCell >> {'1.00' if (s.get('cell') or '').lower() == cell.lower() else '0.00'}")
    elif low.startswith("save "):
        if not s.get("save_fails"):
            d = os.environ.get("FO4SF_SAVES_DIR") or os.path.dirname(P)
            with open(os.path.join(d, w[1] + ".sfs"), "w") as f:
                json.dump({"player": player_pos(s), "cell": s.get("cell"), "heading": s.get("heading", 0.0)}, f)
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
        s["heading"] = sv.get("heading", s.get("heading", 0.0))
        s["clock"] = {"game": game_time(s), "since": time.time()}
        s["loading_until"] = time.time() + float(s.get("load_secs", 2.0))
    elif low.startswith("coc "):
        if s.get("coc_same_cell_stays") and s.get("cell") == w[1]:
            return                                         # coc_same_cell_stays: a coc into the player's cell
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
        item = (s.get("item_bases") or {}).get(w[1].upper())
        if item is not None:                               # a movable item: at the player's feet (+ item_offset)
            off = s.get("item_offset") or [0.0, 0.0, 0.0]
            s["actors"][rid] = dict(item, base=w[1].upper(), item=True, pos=[p[0] + off[0], p[1] + off[1], 0.0],
                                    pending=bool(s.get("console")) and s.get("spawn_deferred", True))
        else:
            s["actors"][rid] = {"base": w[1].upper(), "pos": [p[0] + 0.8, p[1], p[2]],
                                "pending": bool(s.get("console")) and s.get("spawn_deferred", True)}
        s["last"] = rid
        if s.get("faction_lines", True):
            s["log"] += ["GetInFaction >> 0.00"] * 3
    elif low == "plr":
        if s.get("plr_misses", 0) > 0:                    # the first plr(s) name nothing (the converted items, 2026-10-18)
            s["plr_misses"] -= 1
            return
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
        if kind is not None and fmt == "zero":           # GetSelf >> (00000000) (the vanilla items, 2026-10-18)
            s["log"].append("GetSelf >> (00000000)")
        elif kind is not None and fmt != "none":
            s["log"].append(f"GetSelf >> {s['sel']}" if fmt == "hex" else f"GetSelf >> ({s['sel'].lower()})")
    elif low.startswith('cgf "fo4sf_probe.pos" '):
        # SANDBOX bridge: FO4SF_Probe.Pos replies in the bridge log (the real game: FO4SF_Probe.psc), nothing on the
        # console; the id is a Papyrus int (negative for load index FF..); an unknown id answers "none"
        try:
            dec = int(w[-1])
        except ValueError:
            dec = None
        rid = f"{dec & 0xFFFFFFFF:08X}" if dec is not None else ""
        if rid and rid == s.get("anchor_id"):
            rp = s["anchor_pos"]
        elif rid in s["actors"]:
            rp = actor_pos(s, s["actors"][rid])
        elif rid in statics(s):
            rp = statics(s)[rid]["pos"]
        else:                                              # a door's ref: its ref_pos, as the fake readpos prints it
            doors = [d for d in s.get("doors", []) if str(d.get("ref", "")).upper() == rid]
            rp = (doors[0].get("ref_pos") or doors[0]["pos"]) if doors else None
        bridge_ref_line(s, dec, rp)
    elif low.startswith(('cgf "fo4sf_probe.resolve" ', 'cgf "fo4sf_probe.moveto" ')):
        bridge_probe_lines(s, cmd)
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
    elif low.startswith("applyhavokimpulse "):
        s.setdefault("impulses", []).append({"sel": s.get("sel"), "cmd": cmd})
        if kind == "actor" and a.get("item"):
            impulse(s, a, w)
        elif kind is None:
            s["log"].append("Missing reference")
    elif low.startswith("setrigidbodymass "):
        if s.get("setmass_reply"):                         # the console refuses it (made-up text: the real one is unseen)
            s["log"].append(s["setmass_reply"])
        elif kind == "actor" and a.get("item") and not s.get("setmass_noop"):
            a["mass_set"] = float(w[1])
    elif low == 'cf "objectreference.getmass"':
        if s.get("getmass_reply"):
            s["log"].append(s["getmass_reply"])
        elif kind == "actor" and a.get("item"):
            s["log"].append(f"GetMass >> {mass_of(a):.2f}")
    elif low == "startcombat player":
        # the combat manager takes the actor (combat state 1, target the player 00000014) unless startcombat_fails
        # (N0b_combat 2026-10-13: StartCombat froze the calm citizen); it holds its ground either way
        if kind == "actor" and not s.get("startcombat_fails"):
            a["combat"] = "00000014"
    elif low in ("getcombatstate", "getcombattarget", "getlineofsight player"):
        # the combat reads (npc_nav combat_reads). Reply formats are a HYPOTHESIS (unverified in game): a condition
        # function's decimal like GetIsID's, the target a parenthesised id like GetSelf's; combat_fmt "int" prints the
        # state as an integer and the target bare; combat_fmt "refused": "Script command not found" for all three
        if kind is None:
            s["log"].append("Missing reference")
        elif s.get("combat_fmt") == "refused":
            s["log"].append("Script command not found")
        else:
            tgt = a.get("combat") if kind == "actor" else None
            as_int = s.get("combat_fmt") == "int"
            if low == "getcombatstate":
                st = 1 if tgt else 0
                s["log"].append(f"GetCombatState >> {st}" if as_int else f"GetCombatState >> {st:.2f}")
            elif low == "getcombattarget":
                rid = (tgt or "00000000")
                s["log"].append(f"GetCombatTarget >> {rid}" if as_int else f"GetCombatTarget >> ({rid.lower()})")
            else:
                s["log"].append(f"GetLineOfSight >> {float(s.get('los', 1)):.2f}")
    elif low == "disable" and kind is not None:
        if kind == "actor":
            a["pos"], a["target"], a["combat"] = actor_pos(s, a), False, None
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
                 ("GetInCell", "GetlnCell"), ("GetCombatState", "Get Combat State"), ("GetLineOfSight", "GetLlneOfSight"),
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
                s.setdefault("events", []).append("<open>" if s["console"] else "<close>")
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
                        # a hostile base (knob "hostile": [base ids]) engages the player on its own once the game runs,
                        # and holds its ground (the Spacer of 2026-10-13 did not walk up to the player)
                        if a["base"] in [b.upper() for b in s.get("hostile", [])] and not a.get("disabled"):
                            a["combat"] = "00000014"
                    auto_doors(s)                          # a setpos left the player in an automatic door's range
            elif k in ("hold", "holdg") and v.startswith("w,") and not s.get("console"):
                walk(s, int(v[2:]))
                s.setdefault("holds", []).append(int(v[2:]))
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
    elif sys.argv[1] == "popup":
        print(s.get("popup") or "")
        return
    elif sys.argv[1] == "screen":
        lines = s["log"][-9:]                              # the console shows about nine lines
        if s.get("ocr_th") in (s.get("isid_lost_at") or []):   # this threshold's OCR loses the reply line
            lines = [ln for ln in lines if not ln.startswith("GetIsID >>")]
        if s.get("layout") == "column":
            lines = column(lines)
        if s.get("ocr_quirks", True):
            lines = [quirks(ln) for ln in lines]
        print("\n".join(lines))
        return
    elif sys.argv[1] == "readpos":
        args = sys.argv[2:]
        angle = "--angle" in args
        ref = next((x.upper() for x in args if x and x != "--angle"), "")
        s["readpos_calls"] = s.get("readpos_calls", 0) + 1   # the walk must not use readpos.ps1 after the arrival
        if not ref:
            p = player_pos(s)
            g = s.get("garble_after_walks")
            if g is not None and s.get("walks", 0) >= g and s.get("garbled", 0) < s.get("garble_count", 1) \
                    and s.get("last_read"):
                s["garbled"] = s.get("garbled", 0) + 1
                print(f"{s['last_read'][2]:.2f} {p[0]:.2f} {p[2]:.2f}")
            else:
                s["last_read"] = p
                print(" ".join(f"{v:.2f}" for v in p) + (f" {float(s.get('heading', 0.0)) % 360:.2f}" if angle else ""))
        elif ref == s.get("anchor_id"):
            s["sel"] = ref                                 # readpos -Ref selects with prid
            print(" ".join(f"{v:.2f}" for v in s["anchor_pos"]))
        elif ref in s["actors"] and not s["actors"][ref].get("pending"):
            s["sel"] = ref                                 # a placed item or actor (movable: the build's own item)
            print(" ".join(f"{v:.2f}" for v in actor_pos(s, s["actors"][ref])))
        else:
            d = next((d for d in s.get("doors", []) if (d.get("ref") or "").upper() == ref), None)
            if d is None:
                print("fail")
            else:                                          # a door's getpos: ref_pos (e.g. its unmerged local position)
                s["sel"] = ref
                print(" ".join(f"{v:.2f}" for v in d.get("ref_pos") or d["pos"]))
    with open(P, "w") as f:
        json.dump(s, f, indent=1)


def bridge_ref_line(s, dec, rp):
    """A FO4SF_Probe.Pos reply in the bridge log, as the real script writes it (no reply without a bridge log)."""
    log = os.environ.get("FO4SF_BRIDGE_LOG")
    if not log or dec is None:
        return
    if rp is None:
        line = f"[{time.strftime('%H:%M:%S')}] FO4SF ref={dec} none"
    else:
        cell = 50331649 + sum(ord(c) for c in str(s.get("cell") or "")) % 1000
        line = (f"[{time.strftime('%H:%M:%S')}] FO4SF ref={dec} pos={rp[0]:.6f} {rp[1]:.6f} {rp[2]:.6f} ang=0.000000 "
                f"cell={cell} disabled=false loaded=true")
    with open(log, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def bridge_probe_lines(s, cmd):
    """SANDBOX bridge: FO4SF_Probe.Resolve / MoveTo (scripts/bridge/FO4SF_Probe.psc) answer in the bridge log only, in the
    script's format. probe_refs {"<plugin-local decimal id>": [x, y, z]} are what GetFormFromFile finds (any other id:
    form=none); MoveTo puts the player there plus the offset and hides the HUD for load_secs (a cell load)."""
    m = re.fullmatch(r'cgf "FO4SF_Probe\.(Resolve|MoveTo)" "([^"]+)" (\d+)((?: -?\d+(?:\.\d+)?){3})?', cmd)
    if not m:
        return
    fn, plugin, local, offs = m.groups()
    rp = (s.get("probe_refs") or {}).get(local)
    where = "ang=0.000000 cell=33557935 cellname= world=-16707575 worldname="
    head = f"FO4SF {'resolve' if fn == 'Resolve' else 'target'} plugin={plugin} id={local}"
    lines = [head + (" form=none" if rp is None else f" form={0x02000000 | int(local)} ref=true pos={rp[0]:.6f} "
                     f"{rp[1]:.6f} {rp[2]:.6f} {where} disabled=false loaded=true")]
    if fn == "MoveTo":
        d = [float(v) for v in offs.split()]
        tag = f"FO4SF moveto plugin={plugin} id={local} offset={d[0]:.6f} {d[1]:.6f} {d[2]:.6f}"
        if rp is None:
            lines.append(tag + " phase=refused")
        else:
            s["player"], s["falling"] = [rp[k] + d[k] for k in range(3)], None
            s["loading_until"] = time.time() + float(s.get("load_secs", 2.0))
            p = s["player"]
            lines.append(tag + f" phase=after pos={p[0]:.6f} {p[1]:.6f} {p[2]:.6f} {where} loaded=true")
    log = os.environ.get("FO4SF_BRIDGE_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as f:
            f.write("".join(f"[{time.strftime('%H:%M:%S')}] {ln}\n" for ln in lines))


def bridge_line():
    """SANDBOX bridge (docs/ai/test-queue.md "Bridge"): after every fake-game call, one line to $FO4SF_BRIDGE_LOG as
    the game's FO4SF_Bridge.psc writes them (the clock prefix, six decimals, "true", a decimal cell id, "none" for the
    worldspace), so qstep.ps1's Bridge-Read reads the simulated player without a console session."""
    log = os.environ.get("FO4SF_BRIDGE_LOG")
    if not log:
        return
    with open(P) as f:
        s = json.load(f)
    s["bridge_n"] = s.get("bridge_n", 0) + 1
    p = player_pos(s)
    cell = 50331649 + sum(ord(c) for c in str(s.get("cell") or "")) % 1000
    line = (f"[{time.strftime('%H:%M:%S')}] FO4SF rt={time.time() % 100000:.6f} pos={p[0]:.6f} {p[1]:.6f} {p[2]:.6f} "
            f"ang={float(s.get('heading', 0.0)) % 360:.6f} cell={cell} world=none loaded=true n={s['bridge_n']}")
    with open(log, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    with open(P, "w") as f:
        json.dump(s, f, indent=1)


main()
bridge_line()
