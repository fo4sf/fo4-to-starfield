"""scripts/bridge/door_rounds.py: door round trips planned against the installed plugins and judged from the bridge's
log (synthetic core and port plugins, synthetic logs)."""
import io
import json
import os
import struct
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "bridge"))
import door_rounds as dr  # noqa: E402
import vmad_patch as vp  # noqa: E402

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


def build(d, port_marker_target=0x900, ext_base=0x700):
    """core dir (objects / formids / plan / overlays_params + FO4TerrainCore.esm) and port dir (FO4Port.esm)."""
    core, port = os.path.join(d, "core"), os.path.join(d, "port")
    os.makedirs(core)
    os.makedirs(port)
    out_arrival = [-469.444, 636.074, 42.356]
    back = vp.merged(out_arrival, MERGE)
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

    def test_a_door_whose_installed_vmad_leads_elsewhere_is_skipped_with_why(self):
        d = tempfile.mkdtemp()
        core, port, _ = build(d, port_marker_target=0x901)
        with self.assertRaises(SystemExit) as cm:
            stage(core, port, os.path.join(d, "out"))
        self.assertIn("leads to FO4Port.esm:000901", str(cm.exception))
        self.assertFalse(os.path.exists(os.path.join(d, "out")))

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
CELL = str(0x02000801)


class JudgeTests(unittest.TestCase):
    def test_in_passes_on_the_marker_in_the_interior_cell(self):
        ev = log(f"FO4SF rt=1.0 pos=-1660 -2060 42 ang=0 cell=-1 world=-16707575 loaded=true n=1",
                 "FO4SF ack door-fwd-0",
                 f"FO4SF resolve plugin=FO4Port.esm id=2304 form={0x02000900} ref=true pos=5.4 17.3 -3.6 ang=0 "
                 f"cell={CELL} cellname=x world=none worldname= disabled=false loaded=true",
                 f"FO4SF rt=9.0 pos=5.6 17.0 -3.6 ang=0 cell={CELL} world=none loaded=true n=9")
        self.assertEqual(dr.judge_test(ev, {"activate": {"selected": True}}, EXP_IN)[0], "PASS")

    def test_in_fails_when_the_player_stayed_outside(self):
        ev = log("FO4SF ack door-fwd-0", "FO4SF rt=9.0 pos=-1660 -2060 42 ang=0 cell=-5 world=-16707575 loaded=true n=9")
        v, why, _ = dr.judge_test(ev, {}, EXP_IN)
        self.assertEqual((v, why.split(":")[0]), ("FAIL", "STAYED"))

    def test_out_passes_near_the_merged_marker_and_fails_far(self):
        ok = log("FO4SF ack door-ret-0", "FO4SF rt=9.0 pos=-1668 -2062 42.5 ang=0 cell=-5 world=-16707575 loaded=true n=9")
        self.assertEqual(dr.judge_test(ok, {}, EXP_OUT)[0], "PASS")
        far = log("FO4SF ack door-ret-0", "FO4SF rt=9.0 pos=-469 636 42 ang=0 cell=-5 world=-16707575 loaded=true n=9")
        self.assertEqual(dr.judge_test(far, {}, EXP_OUT)[1].split(":")[0], "WRONG_PLACE")
        inside = log("FO4SF ack door-ret-0", f"FO4SF rt=9.0 pos=5 17 -3 ang=0 cell={CELL} world=none loaded=true n=9")
        self.assertEqual(dr.judge_test(inside, {}, EXP_OUT)[1].split(":")[0], "STAYED")

    def test_never_a_pass_without_activation_ack_position_or_the_planned_index(self):
        self.assertEqual(dr.judge_test([], {"activate": {"selected": False}}, EXP_IN)[1].split(":")[0], "NOT_ACTIVATED")
        self.assertEqual(dr.judge_test([], {}, EXP_IN)[1].split(":")[0], "NO_ACK")
        self.assertEqual(dr.judge_test(log("FO4SF ack door-fwd-0"), {}, EXP_IN)[1].split(":")[0], "NO_POSITION")
        wrong = log("FO4SF ack door-fwd-0",
                    f"FO4SF resolve plugin=FO4Port.esm id=2304 form={0x05000900} ref=true pos=5.4 17.3 -3.6 ang=0 "
                    f"cell={CELL} cellname=x world=none worldname= disabled=false loaded=true",
                    f"FO4SF rt=9.0 pos=5.6 17.0 -3.6 ang=0 cell={CELL} world=none loaded=true n=9")
        v, why, _ = dr.judge_test(wrong, {}, EXP_IN)
        self.assertEqual((v, why.split(":")[0]), ("INCONCLUSIVE", "INDEX"))

    def test_judge_reads_the_latest_attempt_of_each_test(self):
        d = tempfile.mkdtemp()
        q = {"experiment": d, "tests": [{"id": "0000_terrain_FO4Core_RedRocketSpawn"},
                                        {"id": "0001_terrain_FO4Port_SuperDuperMart01"}]}
        with open(os.path.join(d, "queue.json"), "w") as f:
            json.dump(q, f)
        with open(os.path.join(d, "rounds.json"), "w") as f:
            json.dump({"tol_m": 3.0, "tests": [dict(EXP_IN, test=0, leg="in", cell_edid="X"),
                                               dict(EXP_OUT, test=1, leg="out", cell_edid="X")]}, f)
        for a, line in (("a1", "FO4SF rt=1 pos=0 0 0 ang=0 cell=-5 world=-1 loaded=true n=1"),
                        ("a2", f"FO4SF rt=9 pos=5.5 17.2 -3.6 ang=0 cell={CELL} world=none loaded=true n=9")):
            p = os.path.join(d, "tests", q["tests"][0]["id"], a)
            os.makedirs(p)
            with open(os.path.join(p, "bridge.log"), "w") as f:
                f.write("FO4SF ack door-fwd-0\n" + line + "\n")
        with redirect_stdout(io.StringIO()):
            rows = dr.judge(dr.argparse.Namespace(queue=d, rounds=""))
        self.assertEqual([(r["verdict"], r.get("attempt")) for r in rows], [("PASS", "a2"), ("NOT_RUN", None)])
        self.assertTrue(os.path.exists(os.path.join(d, "door_rounds_judge.json")))


if __name__ == "__main__":
    unittest.main()
