"""scripts/bridge/door_rounds.py: door round trips planned against the installed plugins and judged from the bridge's
log (synthetic core and port plugins, synthetic logs)."""
import hashlib
import io
import json
import os
import re
import struct
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "bridge"))
import door_rounds as dr  # noqa: E402
import vmad_patch as vp  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import console_plan  # noqa: E402

OWN = 0x01000000
MERGE = (-1200.0, -2700.0, 0.0)


def rec(sig, fid, fields):
    return vp.record_bytes(sig, fid, 0, fields)


def refr(fid, base, pos, vmad=None):
    fs = [(b"NAME", struct.pack("<I", base))]
    if vmad is not None:
        fs.insert(0, (b"VMAD", vmad))
    return rec(b"REFR", fid, fs + [(b"DATA", struct.pack("<6f", *pos, 0, 0, 0))])


def plugin(path, door_base, cell_id, cell_edid, refs, exterior, base_sig=b"DOOR"):
    """A one-master plugin: a DOOR base, one cell (exterior: in a WRLD-less block; enough for the group path) whose
    temporary group holds `refs`."""
    door = rec(base_sig, OWN | door_base, [(b"EDID", b"Door\0")])
    cell = rec(b"CELL", OWN | cell_id, [(b"EDID", cell_edid.encode() + b"\0"), (b"DATA", struct.pack("<I", 0 if exterior else 1))])
    temp = vp.Group(struct.pack("<I", OWN | cell_id), vp.GROUP_TEMPORARY, bytes(8), refs)
    children = vp.Group(struct.pack("<I", OWN | cell_id), vp.GROUP_CELL_CHILDREN, bytes(8), [temp])
    top = vp.Group(b"CELL", 0, bytes(8), [vp.Group(struct.pack("<I", 0), 2, bytes(8), [
        vp.Group(struct.pack("<I", 0), 3, bytes(8), [cell, children])])])
    hedr = struct.pack("<fII", 0.96, 3 + len(refs), 0xFFFF)
    tes4 = vp.record_bytes(b"TES4", 0, 0x1, [(b"HEDR", hedr), (b"MAST", b"Starfield.esm\0")])
    with open(path, "wb") as f:
        f.write(tes4.serialize() + vp.Group(base_sig, 0, bytes(8), [door]).serialize() + top.serialize())


def build(d, port_marker_target=0x900, ext_base=0x700, back=None):
    """core dir (objects / formids / plan / overlays_params + FO4TerrainCore.esm) and port dir (FO4Port.esm)."""
    core, port = os.path.join(d, "core"), os.path.join(d, "port")
    os.makedirs(core)
    os.makedirs(port)
    out_arrival = [-469.444, 636.074, 42.356]
    back = back or vp.merged(out_arrival, MERGE)
    plugin(os.path.join(core, "FO4TerrainCore.esm"), 0x700, 0x7FF, "FO4Core_Cell", [
        refr(OWN | 0x701, OWN | ext_base, [-470.0, 650.0, 42.0], vp.load_door_vmad("FO4Port.esm", port_marker_target)),
        refr(OWN | 0x702, 0x000034, out_arrival)], exterior=True, base_sig=b"ACTI")
    plugin(os.path.join(port, "FO4Port.esm"), 0x800, 0x801, "FO4Port_SuperDuperMart01", [
        refr(OWN | 0x802, OWN | 0x800, [6.4, 17.37, -3.66], vp.load_door_vmad("FO4TerrainCore.esm", 0x702, back)),
        refr(OWN | 0x900, 0x000034, [5.449, 17.291, -3.654])], exterior=False)
    entry = {"src": "0EE661:Fallout4.esm", "destination": {"plugin": "FO4Port.esm", "id": 0x900, "ref": "000802",
                                                           "cell": "000801", "arrival": {"pos": [5.449, 17.291, -3.654]}},
             "arrival": {"pos": out_arrival}, "ids": {"base": "000700", "ref": "000701", "arrival": "000702"}}
    with open(os.path.join(core, "objects.json"), "w") as f:
        json.dump({"world": "FO4Core_Commonwealth", "doors": [entry]}, f)
    with open(os.path.join(core, "formids.json"), "w") as f:
        json.dump({"plugin": "FO4TerrainCore.esm", "world": "FO4Core_Commonwealth", "doors": {entry["src"]: entry["ids"]}}, f)
    with open(os.path.join(core, "overlays_params.json"), "w") as f:
        json.dump({"overlays": [{"world": "FO4Core_Commonwealth", "planet_target_cell": [-12, -27]}]}, f)
    with open(os.path.join(core, "plan.json"), "w") as f:
        json.dump([{"coc": "FO4Core_RedRocketSpawn", "spawn_local": [-989.2571, 1146.5143, 105.2609], "drop_z": 175.0,
                    "points": [{"label": "zref_ground", "x": -985.2571, "y": 1138.5143, "expect": 105.0253}]}], f)
    return core, port, back


def stage(core, port, out, *extra):
    with redirect_stdout(io.StringIO()):
        dr.main(["stage", "--core", core, "--port", port, "--core-index", "03", "--port-index", "02", "--out", out, *extra])
    with open(os.path.join(out, "rounds.json")) as f:
        rounds = json.load(f)
    with open(os.path.join(out, "plan.json")) as f:
        return rounds, json.load(f)


class StageTests(unittest.TestCase):
    def test_a_door_is_planned_both_ways_from_the_installed_plugins(self):
        d = tempfile.mkdtemp()
        core, port, back = build(d)
        rounds, plan = stage(core, port, os.path.join(d, "out"))
        self.assertEqual(rounds["skipped"], [])
        fwd, ret = plan
        self.assertEqual(fwd["activate"], {"ref": "03000701", "base": "03000700", "expect": []})
        self.assertEqual(fwd["points"][1], {"label": "door_front", "x": -469.444, "y": 636.074, "expect": 42.356})
        self.assertEqual(fwd["drop_z"], 175.0)
        self.assertEqual(fwd["console_post"], ['cgf "FO4SF_Probe.Ack" "door-fwd-0"', 'cgf "FO4SF_Probe.Resolve" "FO4Port.esm" 2304'])
        self.assertEqual((ret["coc"], ret["travel"]), ("FO4Port_SuperDuperMart01", "coc FO4Port_SuperDuperMart01"))
        self.assertEqual(ret["activate"], {"ref": "02000802", "base": "02000800", "expect": []})
        self.assertAlmostEqual(ret["drop_z"], -3.654 + 1.5, places=3)
        t0, t1 = rounds["tests"]
        self.assertEqual((t0["cell"], t0["pos"], t0["resolve"]["index"]), ("02000801", [5.449, 17.291, -3.654], "02"))
        self.assertEqual((t1["world"], t1["resolve"]["index"]), ("exterior", "03"))
        for got, want in zip(t1["pos"], back):
            self.assertAlmostEqual(got, want, places=3)
        self.assertEqual(t0["hops"], 3)                        # 728 m at 185 m a hop
        with open(os.path.join(d, "out", "plan.json"), "rb") as f:   # one rounds digest covers both files (Codex on #401)
            self.assertEqual(rounds["plan_sha256"], hashlib.sha256(f.read()).hexdigest())
        self.assertEqual(rounds["core_worlds"], [])           # the synthetic core has no WRLD record

    def test_out_legs_alone_and_the_border_switch(self):
        d = tempfile.mkdtemp()
        core, port, _back = build(d)
        both, both_plan = stage(core, port, os.path.join(d, "both"))
        rounds, plan = stage(core, port, os.path.join(d, "out"), "--legs", "out", "--border-off")
        with open(os.path.join(core, "plan.json")) as f:
            spawn = json.load(f)[0]
        self.assertEqual(len(plan), 2)                          # a Red Rocket prelude (Codex on #444), then the OUT leg
        self.assertEqual((plan[0]["coc"], plan[0]["spawn_local"], plan[0]["points"]),
                         (dr.SPAWN_COC, spawn["spawn_local"], spawn["points"][:1]))   # arrival only, no sweep
        self.assertEqual(plan[0]["beyond"], {"x": spawn["points"][0]["x"], "y": spawn["points"][0]["y"]})
        self.assertNotIn("activate", plan[0])
        self.assertEqual(plan[1]["coc"], "FO4Port_SuperDuperMart01")
        self.assertEqual(plan[1]["console_pre"], ['GetINI "bBorderRegionsEnabled:General"',
                                                  'SetINI "bBorderRegionsEnabled:General" 0',
                                                  'GetINI "bBorderRegionsEnabled:General"'])
        self.assertEqual(plan[1]["console_post"], both_plan[1]["console_post"] + ['GetINI "bBorderRegionsEnabled:General"'])
        self.assertEqual({k: v for k, v in plan[1].items() if k not in ("console_pre", "console_post")},
                         {k: v for k, v in both_plan[1].items() if k != "console_post"})
        origin = rounds["tests"][0].pop("origin")               # the prelude is judged by nobody; the OUT leg checks it
        self.assertEqual(rounds["tests"], [dict(both["tests"][1], test=1)])
        self.assertEqual(origin["tol_m"], dr.ORIGIN_TOL_M)
        for got, want in zip(origin["pos"], vp.merged([spawn["points"][0]["x"], spawn["points"][0]["y"]], rounds["merge"])):
            self.assertAlmostEqual(got, want, places=3)
        self.assertEqual((rounds["legs"], rounds["border_off"], both["legs"], both["border_off"]), ("out", True, "both", False))
        self.assertNotIn("console_pre", both_plan[0])
        with open(os.path.join(d, "out", "README.txt")) as f:   # a relaunch would land in Vault111Cryo, not Red Rocket
            self.assertIn("no --fresh", f.read())
        for line in plan[1]["console_pre"] + plan[1]["console_post"]:   # the runner types only whitelisted lines
            self.assertTrue(re.fullmatch(console_plan.PATTERN, line), line)

    def test_the_stage_records_the_cores_worldspaces(self):
        d = tempfile.mkdtemp()
        core, port, _ = build(d)
        p = os.path.join(core, "FO4TerrainCore.esm")
        with open(p, "ab") as f:                               # one WRLD top group after the cells
            f.write(vp.Group(b"WRLD", 0, bytes(8), [rec(b"WRLD", OWN | 0x803, [(b"EDID", b"FO4Core_Commonwealth\0")])]).serialize())
        self.assertEqual(dr.Installed(p).worlds(), ["000803"])
        rounds, _ = stage(core, port, os.path.join(d, "out"))
        self.assertEqual(rounds["core_worlds"], ["000803"])
        self.assertEqual(dr.core_world(rounds), {"index": "03", "world": "03000803"})

    def test_a_door_whose_installed_vmad_leads_elsewhere_is_skipped_with_why(self):
        d = tempfile.mkdtemp()
        core, port, _ = build(d, port_marker_target=0x901)
        with self.assertRaises(SystemExit) as cm:
            stage(core, port, os.path.join(d, "out"))
        self.assertIn("leads to FO4Port.esm:000901", str(cm.exception))
        self.assertFalse(os.path.exists(os.path.join(d, "out")))

    def test_a_vmad_return_position_off_the_marker_is_refused(self):
        d = tempfile.mkdtemp()                         # Codex #358: the VMAD under test is not the oracle
        core, port, _ = build(d, back=[12345.0, 23456.0, 34567.0])
        with self.assertRaises(SystemExit) as cm:
            stage(core, port, os.path.join(d, "out"))
        self.assertIn("is not its marker's merged position", str(cm.exception))

    def test_a_base_that_moved_is_refused(self):
        d = tempfile.mkdtemp()
        core, port, _ = build(d, ext_base=0x800)
        with self.assertRaises(SystemExit) as cm:
            stage(core, port, os.path.join(d, "out"))
        self.assertIn("has base 01000800", str(cm.exception))

    def test_an_existing_out_and_only_filters(self):
        d = tempfile.mkdtemp()
        core, port, _ = build(d)
        with self.assertRaises(SystemExit):
            stage(core, port, os.path.join(d, "out"), "--only", "FO4Port_Vault95")
        rounds, _plan = stage(core, port, os.path.join(d, "out"), "--only", "fo4port_superdupermart01")
        self.assertEqual(len(rounds["doors"]), 1)
        with self.assertRaises(SystemExit):
            stage(core, port, os.path.join(d, "out"))


class OrderTests(unittest.TestCase):
    def test_the_port_moves_to_the_end_and_the_bridge_last(self):
        lines = ["# comment", "*FO4Port.esm", "*FO4TerrainCore.esm", "*FO4TerrainCore_Mars.esm", "FO4Old.esm",
                 "*FO4SFMission.esm", "*FO4SFBridge.esm", "*SFBGS003.esm"]
        self.assertEqual(dr.order(lines), {"FO4TerrainCore.esm": 2, "FO4TerrainCore_Mars.esm": 3, "FO4SFMission.esm": 4,
                                           "FO4Port.esm": 5, "FO4SFBridge.esm": 6})


def log(*lines):
    return [e for e in (dr.bridge_log.parse_event(s) for s in lines) if e is not None]


EXP_IN = {"ack": "door-fwd-0", "pos": [5.449, 17.291, -3.654], "cell": "02000801", "world": None,
          "resolve": {"plugin": "FO4Port.esm", "id": 2304, "index": "02"}}
EXP_OUT = {"ack": "door-ret-0", "pos": [-1669.444, -2063.926, 42.356], "cell": None, "world": "exterior",
           "resolve": {"plugin": "FO4TerrainCore.esm", "id": 1794, "index": "03"}}
CELL, WORLD, ACT = str(0x02000801), "-16707575", {"activate": {"selected": True}}


def pos(x, y, z, cell=CELL, world="none", loaded="true", rt=9.0):
    return f"FO4SF rt={rt} pos={x} {y} {z} ang=0 cell={cell} world={world} loaded={loaded} n=9"


def res(plugin, local, index, cell=CELL, world="none"):
    return (f"FO4SF resolve plugin={plugin} id={local} form={(index << 24) | local} ref=true pos=1 2 3 ang=0 "
            f"cell={cell} cellname=x world={world} worldname= disabled=false loaded=true")


IN_OK = ("FO4SF ack door-fwd-0", res("FO4Port.esm", 2304, 2), pos(5.6, 17.0, -3.6))
OUT_OK = ("FO4SF ack door-ret-0", res("FO4TerrainCore.esm", 1794, 3, cell="-5", world=WORLD),
          pos(-1668, -2062, 42.5, cell="-5", world=WORLD))


def verdict(lines, exp, obs=ACT):
    v, why, _ = dr.judge_test(log(*lines), obs, exp)
    return v, why.split(":")[0]


class JudgeTests(unittest.TestCase):
    def test_in_passes_on_the_marker_in_the_interior_cell(self):
        self.assertEqual(verdict(IN_OK, EXP_IN)[0], "PASS")

    def test_in_fails_when_the_player_stayed_outside(self):
        self.assertEqual(verdict(IN_OK[:2] + (pos(-1660, -2060, 42, cell="-5", world=WORLD),), EXP_IN), ("FAIL", "STAYED"))

    def test_out_passes_near_the_merged_marker_in_its_world_and_fails_far_or_inside(self):
        self.assertEqual(verdict(OUT_OK, EXP_OUT)[0], "PASS")
        self.assertEqual(verdict(OUT_OK[:2] + (pos(-469, 636, 42, cell="-5", world=WORLD),), EXP_OUT),
                         ("FAIL", "WRONG_PLACE"))
        self.assertEqual(verdict(OUT_OK[:2] + (pos(5, 17, -3),), EXP_OUT), ("FAIL", "STAYED"))

    def test_missing_proof_is_never_a_pass(self):
        self.assertEqual(verdict(IN_OK, EXP_IN, {"activate": {"selected": False}}), ("INCONCLUSIVE", "NOT_ACTIVATED"))
        for obs in ({}, {"activate": {}}, None):                         # Codex #358: absence is not success
            self.assertEqual(verdict(IN_OK, EXP_IN, obs), ("INCONCLUSIVE", "NOT_ACTIVATED"))
        self.assertEqual(verdict(IN_OK[1:], EXP_IN), ("INCONCLUSIVE", "NO_ACK"))
        self.assertEqual(verdict((IN_OK[0], IN_OK[2]), EXP_IN), ("INCONCLUSIVE", "NO_RESOLVE"))
        self.assertEqual(verdict((IN_OK[1], IN_OK[0], IN_OK[2]), EXP_IN), ("INCONCLUSIVE", "NO_RESOLVE"))  # before the ack
        self.assertEqual(verdict(IN_OK[:2], EXP_IN), ("INCONCLUSIVE", "NO_POSITION"))
        self.assertEqual(verdict((IN_OK[0], res("FO4Port.esm", 2304, 5), IN_OK[2]), EXP_IN), ("INCONCLUSIVE", "INDEX"))

    def test_unloaded_or_non_finite_readings_and_plans_are_inconclusive(self):
        self.assertEqual(verdict(IN_OK[:2] + (pos(5.6, 17.0, -3.6, loaded="false"),), EXP_IN), ("INCONCLUSIVE", "UNSETTLED"))
        self.assertEqual(verdict(IN_OK, dict(EXP_IN, pos=[float("nan"), 17.291, -3.654])), ("INCONCLUSIVE", "BAD_PLAN"))
        self.assertEqual(dr.judge_test(log(*IN_OK), ACT, EXP_IN, tol=float("nan"))[1].split(":")[0], "BAD_PLAN")

    def test_an_out_leg_alone_must_start_at_its_red_rocket_prelude(self):
        # Codex on #444: a crash between the prelude and the OUT leg relaunches into Vault111Cryo
        exp = dict(EXP_OUT, origin={"pos": [-2185.26, -1561.49], "tol_m": 100.0})
        start = pos(-2180, -1555, 105, cell="-7", world=WORLD)
        self.assertEqual(verdict((start, pos(5, 17, -3)) + OUT_OK, exp)[0], "PASS")
        # Codex on #444: the log is the whole session's, launch in Vault111Cryo first: the last exterior read counts
        self.assertEqual(verdict((pos(1, 2, 3), start, pos(5, 17, -3)) + OUT_OK, exp)[0], "PASS")
        far = pos(-1000, -1555, 105, cell="-7", world=WORLD)
        self.assertEqual(verdict((far, start) + OUT_OK, exp)[0], "PASS")                       # an earlier test's exit
        self.assertEqual(verdict((start, far) + OUT_OK, exp), ("INCONCLUSIVE", "ORIGIN"))     # left Red Rocket since
        self.assertEqual(verdict((start, pos(1, 2, 3, rt=2.0)) + OUT_OK, exp),
                         ("INCONCLUSIVE", "ORIGIN"))                                              # a relaunch since
        self.assertEqual(verdict((pos(-1000, -1555, 105, cell="-7", world=WORLD),) + OUT_OK, exp),
                         ("INCONCLUSIVE", "ORIGIN"))                                              # began elsewhere
        self.assertEqual(verdict(OUT_OK, exp), ("INCONCLUSIVE", "ORIGIN"))                        # no reading at all
        self.assertEqual(verdict(OUT_OK, EXP_OUT)[0], "PASS")                                     # two-leg stages: no gate

    def test_contradictory_targets_are_inconclusive(self):
        other = (OUT_OK[0], res("FO4TerrainCore.esm", 1794, 3, cell="-5", world=str(0xFF011009 - (1 << 32))),
                 pos(-1668, -2062, 42.5, cell="-5", world="42"))
        self.assertEqual(verdict(other, EXP_OUT), ("INCONCLUSIVE", "WORLD"))     # Codex #358: not mere truthiness
        self.assertEqual(verdict((OUT_OK[0], res("FO4TerrainCore.esm", 1794, 3, cell="-5"), OUT_OK[2]), EXP_OUT),
                         ("INCONCLUSIVE", "TARGET"))
        self.assertEqual(verdict((IN_OK[0], res("FO4Port.esm", 2304, 2, cell="7"), IN_OK[2]), EXP_IN),
                         ("INCONCLUSIVE", "TARGET"))

    def test_out_crosses_worlds_only_for_a_pinned_runtime_instance(self):
        # doors_out2 (2026-10-19): the player stood in FF00552F, the marker resolved in our WRLD 02000803, 0.0 to
        # 0.3 m off. Codex on #383: an FF prefix does not say which WRLD it instantiates, so only a pinned pair crosses
        runtime, base = str(0xFF00552F - (1 << 32)), str(0x02000803)
        out = (OUT_OK[0], res("FO4TerrainCore.esm", 1794, 3, cell="-5", world=base),
               pos(-1669.3, -2063.8, 42.4, cell="-6", world=runtime))
        pin = {"FF00552F": "02000803"}
        self.assertEqual(verdict(out, EXP_OUT), ("INCONCLUSIVE", "WORLD"))      # no pin: as before daff232

        def v(lines, pins=pin):
            r, why, _ = dr.judge_test(log(*lines), ACT, EXP_OUT, instances=pins)
            return r, why
        self.assertEqual(v(out)[0], "PASS")
        self.assertIn("taken as 02000803 by --world-instance", v(out)[1])
        far = out[:2] + (pos(-469, 636, 42, cell="-6", world=runtime),)
        self.assertEqual(v(far)[0], "FAIL")                                       # a pin never excuses distance
        other_rt = out[:2] + (pos(-1669.3, -2063.8, 42.4, cell="-6", world=str(0xFF123456 - (1 << 32))),)
        self.assertEqual(v(other_rt)[0], "INCONCLUSIVE")                          # an unpinned runtime world
        other_base = (out[0], res("FO4TerrainCore.esm", 1794, 3, cell="-5", world=str(0x04000803)), out[2])
        self.assertEqual(v(other_base)[0], "INCONCLUSIVE")                        # pinned to another WRLD
        self.assertIn("no --world-instance pins the pair", v(other_base)[1])
        self.assertEqual(v(out[:2] + (pos(-1669.3, -2063.8, 42.4),))[0], "FAIL")  # still inside: STAYED

    def test_out_crosses_worlds_when_the_players_cell_is_the_cores(self):
        # doors_out retry 4 (2026-10-21): the runtime world changed per launch (FF00552F, then FF005511) and needed a hand
        # pin each time; the player's cell is one of the core's own (JOURNAL 2026-10-16 (e): 0x02000DAF in the runtime
        # world), and a cell belongs to one WRLD
        runtime, base = str(0xFF005511 - (1 << 32)), str(0x03000803)
        core = {"index": "03", "world": "03000803"}
        tgt = res("FO4TerrainCore.esm", 1794, 3, cell="-5", world=base)

        def v(cell, pins=None, c=core, world=runtime, x=-1669.3):
            lines = (OUT_OK[0], tgt, pos(x, -2063.8, 42.4, cell=cell, world=world))
            r, why, _ = dr.judge_test(log(*lines), ACT, EXP_OUT, instances=pins, core=c)
            return r, why
        r, why = v(str(0x03000DAF))
        self.assertEqual(r, "PASS")
        self.assertIn("taken as 03000803 because the player's cell 03000DAF is the core's", why)
        self.assertEqual(v(str(0x03000DAF), x=-469)[0], "FAIL")                     # the tie never excuses distance
        self.assertEqual(v(str(0x04000DAF))[0], "INCONCLUSIVE")                     # another plugin's cell
        self.assertEqual(v(str(0x03000DAF), c=None)[0], "INCONCLUSIVE")             # no single core world recorded
        self.assertEqual(v(str(0x03000DAF), c={"index": "03", "world": "03000900"})[0], "INCONCLUSIVE")
        self.assertEqual(v(str(0x03000DAF), world=str(0x05000001))[0], "INCONCLUSIVE")   # not a runtime (FF) world
        other_pin = {"FF005511": "03000900"}                                        # the operator's pin decides
        self.assertEqual(v(str(0x03000DAF), pins=other_pin)[0], "INCONCLUSIVE")
        self.assertIn("by --world-instance", v(str(0x03000DAF), pins={"FF005511": "03000803"})[1])

    def test_the_core_world_needs_exactly_one_core_worldspace(self):
        self.assertEqual(dr.core_world({"core_index": "02", "core_worlds": ["000803"]}),
                         {"index": "02", "world": "02000803"})
        for info in ({"core_index": "02"}, {"core_index": "02", "core_worlds": []},
                     {"core_index": "02", "core_worlds": ["000803", "000900"]}, {"core_index": "2", "core_worlds": ["000803"]}):
            with self.subTest(info=info):
                self.assertIsNone(dr.core_world(info))

    def test_world_pins_are_checked(self):
        self.assertEqual(dr.world_pairs(["ff00552f=02000803", "FF00552F=02000803"]), {"FF00552F": "02000803"})
        for bad in (["FF00552F"], ["02000803=FF00552F"], ["FF00552F=FF000001"], ["FF00552F=02000803", "FF00552F=02000804"]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                dr.world_pairs(bad)

    def test_every_resolve_reply_must_name_the_planned_form_in_one_place(self):
        # Codex's correction review of #358: the full id, and no later contradiction, before a PASS
        wrong = (IN_OK[0], res("FO4Port.esm", 2304, 2).replace(f"form={(2 << 24) | 2304}", f"form={(2 << 24) | 2305}"),
                 IN_OK[2])
        self.assertEqual(verdict(wrong, EXP_IN), ("INCONCLUSIVE", "CONFLICT"))
        later_none = IN_OK + ("FO4SF resolve plugin=FO4Port.esm id=2304 form=none",)
        self.assertEqual(verdict(later_none, EXP_IN), ("INCONCLUSIVE", "CONFLICT"))
        other_world = OUT_OK + (res("FO4TerrainCore.esm", 1794, 3, cell="-5", world="-16708042"),)
        self.assertEqual(verdict(other_world, EXP_OUT), ("INCONCLUSIVE", "CONFLICT"))
        self.assertEqual(verdict(IN_OK + (IN_OK[1],), EXP_IN)[0], "PASS")          # a repeated agreeing reply is fine

    def test_the_judge_cli_keeps_a_contradicted_pass_inconclusive(self):
        d = tempfile.mkdtemp()
        q = {"experiment": d, "tests": [{"id": "0000_terrain_FO4Core_RedRocketSpawn"}]}
        with open(os.path.join(d, "queue.json"), "w") as f:
            json.dump(q, f)
        with open(os.path.join(d, "rounds.json"), "w") as f:
            json.dump({"tol_m": 3.0, "tests": [dict(EXP_IN, test=0, leg="in", cell_edid="X")]}, f)
        a = os.path.join(d, "tests", q["tests"][0]["id"], "a1")
        os.makedirs(a)
        with open(os.path.join(a, "bridge.log"), "w") as f:
            f.write("\n".join(IN_OK + ("FO4SF resolve plugin=FO4Port.esm id=2304 form=none",)) + "\n")
        with open(os.path.join(a, "obs.json"), "w") as f:
            json.dump(ACT, f)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(dr.main(["judge", "--queue", d]), 0)
        with open(os.path.join(d, "door_rounds_judge.json")) as f:
            row = json.load(f)["results"][0]
        self.assertEqual((row["verdict"], row["why"].split(":")[0]), ("INCONCLUSIVE", "CONFLICT"))

    def test_judge_reads_the_latest_attempt_of_each_test(self):
        d = tempfile.mkdtemp()
        q = {"experiment": d, "tests": [{"id": "0000_terrain_FO4Core_RedRocketSpawn"},
                                        {"id": "0001_terrain_FO4Port_SuperDuperMart01"}]}
        with open(os.path.join(d, "queue.json"), "w") as f:
            json.dump(q, f)
        with open(os.path.join(d, "rounds.json"), "w") as f:
            json.dump({"tol_m": 3.0, "tests": [dict(EXP_IN, test=0, leg="in", cell_edid="X"),
                                               dict(EXP_OUT, test=1, leg="out", cell_edid="X")]}, f)
        for a, last in (("a1", pos(0, 0, 0, cell="-5", world=WORLD)), ("a2", IN_OK[2])):
            p = os.path.join(d, "tests", q["tests"][0]["id"], a)
            os.makedirs(p)
            with open(os.path.join(p, "bridge.log"), "w") as f:
                f.write("\n".join(IN_OK[:2] + (last,)) + "\n")
            with open(os.path.join(p, "obs.json"), "w") as f:
                json.dump(ACT, f)
        with redirect_stdout(io.StringIO()):
            rows = dr.judge(dr.argparse.Namespace(queue=d, rounds=""))
        self.assertEqual([(r["verdict"], r.get("attempt")) for r in rows], [("PASS", "a2"), ("NOT_RUN", None)])
        with open(os.path.join(d, "door_rounds_judge.json")) as f:
            judged = json.load(f)
        with open(os.path.join(d, "rounds.json"), "rb") as f:          # the file it read, for regress (Codex on #401)
            self.assertEqual(judged["rounds_sha256"], hashlib.sha256(f.read()).hexdigest())


class OutLegsTests(unittest.TestCase):
    def setUp(self):
        import door_out_legs
        self.dol = door_out_legs
        self.d = tempfile.mkdtemp()
        core, port, _ = build(self.d)
        self.st = os.path.join(self.d, "st")
        with redirect_stdout(io.StringIO()):
            dr.main(["stage", "--core", core, "--port", port, "--core-index", "02", "--port-index", "06",
                     "--out", self.st])
        self.plan, self.rounds = (self.load(self.st, n) for n in ("plan.json", "rounds.json"))

    @staticmethod
    def load(d, name):
        with open(os.path.join(d, name)) as f:
            return json.load(f)

    def run_on(self, plan, rounds, min_m, name):
        src = os.path.join(self.d, name + "_src")
        os.makedirs(src)
        for n, v in (("plan.json", plan), ("rounds.json", rounds)):
            with open(os.path.join(src, n), "w") as f:
                json.dump(v, f)
        out = os.path.join(self.d, name)
        with redirect_stdout(io.StringIO()):
            self.dol.main([src, out, str(min_m)])
        return self.load(out, "plan.json"), self.load(out, "rounds.json")

    def test_keeps_the_far_out_legs_renumbered(self):
        kept, rounds = self.run_on(self.plan, self.rounds, 0, "near")
        self.assertEqual(kept, [self.plan[1]])                  # the OUT leg only
        self.assertEqual([(e["test"], e["leg"]) for e in rounds["tests"]], [(0, "out")])
        with open(os.path.join(self.d, "near", "plan.json"), "rb") as f:   # the renumbered plan's own digest
            self.assertEqual(rounds["plan_sha256"], hashlib.sha256(f.read()).hexdigest())
        self.assertEqual(self.run_on(self.plan, self.rounds, 99999, "far")[0], [])
        with self.assertRaises(FileExistsError), redirect_stdout(io.StringIO()):   # a new folder only
            self.dol.main([self.st, os.path.join(self.d, "near"), "0"])

    def test_a_border_off_stage_keeps_its_console_lines(self):
        core, port, _ = build(os.path.join(self.d, "b"))
        st = os.path.join(self.d, "st_border")
        with redirect_stdout(io.StringIO()):
            dr.main(["stage", "--core", core, "--port", port, "--core-index", "02", "--port-index", "06",
                     "--out", st, "--border-off"])
        plan, rounds = self.load(st, "plan.json"), self.load(st, "rounds.json")
        kept, out = self.run_on(plan, rounds, 0, "border")      # Codex on #444: the filter rebuilt it without them
        self.assertEqual(kept, [plan[1]])
        self.assertEqual(kept[0]["console_pre"][:3], dr.BORDER_OFF)
        self.assertEqual((out["legs"], out["border_off"]), ("out", True))
        rounds["border_off"] = False                            # a stage that lies about its lines is refused
        with self.assertRaises(SystemExit):
            self.run_on(plan, rounds, 0, "border_lie")

    def test_the_distance_comes_from_the_geometry_not_the_label(self):
        # Codex's review of #383: 728.53 m from the spawn; labels are display only
        plan = json.loads(json.dumps(self.plan))
        plan[0]["label"] = plan[0]["label"].replace("729 m", "99999 m")
        self.assertEqual(self.run_on(plan, self.rounds, 728.6, "label")[0], [])
        self.assertEqual(len(self.run_on(plan, self.rounds, 728.5, "exact")[0]), 1)

    def test_a_mismatched_stage_is_refused_before_anything_is_written(self):
        def bad(change):
            plan, rounds = json.loads(json.dumps(self.plan)), json.loads(json.dumps(self.rounds))
            change(plan, rounds)
            return plan, rounds
        cases = {
            "out_points_at_in": lambda p, r: r["tests"][1].update(test=0),
            "coc": lambda p, r: p[1].update(coc="FO4Core_RedRocketSpawn"),
            "activation": lambda p, r: p[1]["activate"].update(ref="02000701"),
            "ack": lambda p, r: p[1]["console_post"].__setitem__(0, dr.ack("door-fwd-0")),
            "spawn": lambda p, r: p[0].update(spawn_local=[float("nan"), 0.0, 0.0]),
            "in_leg": lambda p, r: p[0].update(coc="FO4Port_SuperDuperMart01"),
        }
        for name, change in cases.items():
            with self.subTest(name=name), self.assertRaises(SystemExit):
                self.run_on(*bad(change), 0, name)
            self.assertFalse(os.path.exists(os.path.join(self.d, name)))


if __name__ == "__main__":
    unittest.main()
