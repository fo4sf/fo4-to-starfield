"""scripts/bridge/presence.py: the actor / named-reference readout (synthetic plugins and bridge logs)."""
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
sys.path.insert(0, os.path.join(ROOT, "tests"))
import presence  # noqa: E402
import test_door_rounds as tdr  # noqa: E402

OWN = tdr.OWN


def achr(local, pos):
    return tdr.rec(b"ACHR", OWN | local, [(b"NAME", struct.pack("<I", OWN | 0x800)),
                                         (b"DATA", struct.pack("<6f", *pos, 0, 0, 0))])


def mission(d):
    p = os.path.join(d, "FO4SFMission.esm")
    tdr.plugin(p, 0x800, 0x803, "FO4SF_Persist", [achr(0x810, [100.0, 200.0, 10.0]), achr(0x811, [150.0, 260.0, 11.0]),
                                                  achr(0x812, [900.0, 900.0, 5.0])], exterior=True, base_sig=b"NPC_")
    return p


def res(local, index, pos, disabled="false", world="-16707575"):
    return (f"FO4SF resolve plugin=FO4SFMission.esm id={local} form={(index << 24) | local} ref=true "
            f"pos={pos[0]} {pos[1]} {pos[2]} ang=0 cell=-5 cellname= world={world} worldname= disabled={disabled} loaded=true")


class PresenceTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.core, _port, _ = tdr.build(self.d)
        self.esm = mission(self.d)
        self.out = os.path.join(self.d, "out")
        with redirect_stdout(io.StringIO()):
            presence.main(["stage", "--plugin", self.esm, "--index", "05", "--core", self.core, "--out", self.out,
                           "--extra", "FO4TerrainCore.esm:0A7759:02"])
        with open(os.path.join(self.out, "plan.json")) as f:
            self.plan = json.load(f)
        with open(os.path.join(self.out, "presence.json")) as f:
            self.info = json.load(f)

    def test_actors_are_grouped_by_place_and_resolved_where_they_stand(self):
        self.assertEqual(len(self.plan), 3)                        # the extras, then two places
        self.assertEqual(self.plan[0]["console_post"], ['cgf "FO4SF_Probe.Ack" "presence-extra"',
                                                        'cgf "FO4SF_Probe.Resolve" "FO4TerrainCore.esm" 685913'])
        self.assertEqual(self.plan[1]["points"][1], {"label": "group", "x": 104.0, "y": 200.0, "expect": 10.0})
        self.assertEqual(self.plan[1]["console_post"][1:], ['cgf "FO4SF_Probe.Resolve" "FO4SFMission.esm" 2064',
                                                            'cgf "FO4SF_Probe.Resolve" "FO4SFMission.esm" 2065'])
        a = self.info["tests"][1]["refs"][0]
        self.assertEqual((a["index"], a["local"], a["merged"]), ("05", [100.0, 200.0, 10.0], [-1100.0, -2500.0, 10.0]))
        with self.assertRaises(SystemExit):                        # a new folder only
            presence.main(["stage", "--plugin", self.esm, "--index", "05", "--core", self.core, "--out", self.out])

    def test_states(self):
        ref = self.info["tests"][1]["refs"][0]
        ev = lambda *ls: [e for e in (tdr.dr.bridge_log.parse_event(s) for s in ls) if e is not None]  # noqa: E731
        self.assertEqual(presence.read_ref(ev(res(2064, 5, [-1101, -2501, 10])), ref)["state"], "NEAR_MERGED")
        self.assertEqual(presence.read_ref(ev(res(2064, 5, [101, 199, 10])), ref)["state"], "AT_LOCAL")
        self.assertEqual(presence.read_ref(ev(res(2064, 5, [5000, 0, 0])), ref)["state"], "ELSEWHERE")
        self.assertEqual(presence.read_ref(ev(res(2064, 5, [101, 199, 10], disabled="true")), ref)["state"], "DISABLED")
        self.assertEqual(presence.read_ref(ev(res(2064, 3, [101, 199, 10])), ref)["state"], "INDEX")
        self.assertEqual(presence.read_ref([], ref)["state"], "MISSING")
        self.assertEqual(presence.read_ref(ev(res(2065, 5, [1, 1, 1]).replace("id=2065", "id=2064")), ref)["state"],
                         "CONFLICT")                                 # the reply names another form
        self.assertEqual(presence.read_ref(ev(res(2064, 5, [-1101, -2501, 10]),
                                              "FO4SF resolve plugin=FO4SFMission.esm id=2064 form=none"), ref)["state"],
                         "MISSING")                                  # the last reply decides, refusals included
        self.assertEqual(presence.read_ref(ev("FO4SF resolve plugin=FO4SFMission.esm id=2064 form=none"), ref)["state"],
                         "MISSING")

    def test_judge_needs_the_ack_and_counts_script_lines(self):
        q = {"experiment": self.out, "tests": [{"id": f"{i:04d}_terrain_x"} for i in range(3)]}
        with open(os.path.join(self.d, "queue.json"), "w") as f:
            json.dump(q, f)
        a = os.path.join(self.d, "tests", "0001_terrain_x", "a1")
        os.makedirs(a)
        with open(os.path.join(a, "bridge.log"), "w") as f:
            f.write("FO4SF ack presence-1\n" + res(2064, 5, [-1101, -2501, 10]) + "\n")
        with open(os.path.join(a, "papyrus.log"), "w") as f:
            f.write("FO4SF_Min00 relocated 6 actors\nother\nPreston moved\n")
        b = os.path.join(self.d, "tests", "0000_terrain_x", "a1")
        os.makedirs(b)
        with open(os.path.join(b, "bridge.log"), "w") as f:
            f.write("no ack here\n")
        with redirect_stdout(io.StringIO()):
            rows = presence.judge(presence.argparse.Namespace(queue=self.d, presence=""))
        got = [(r["test"], r["id"], r["state"]) for r in rows]
        self.assertEqual(got, [(0, 0x0A7759, "NO_ACK"), (1, 0x810, "NEAR_MERGED"), (1, 0x811, "MISSING"),
                               (2, 0x812, "NOT_RUN")])
        self.assertEqual(rows[1]["papyrus_moved_lines"], 2)


if __name__ == "__main__":
    unittest.main()
