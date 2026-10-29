"""src/fo4sf/planet/probe_log.py and make_planet_probe.py log on a synthetic FO4SFPlanetProbe.0.log written in the
probe script's line format (scripts/planet/FO4SF_PlanetProbeQuest.psc) as Starfield prints it: bools "true" / "false"
(verified on the 14 Oct bridge log and the 28 Oct new game log); no game."""
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "planet"))
from fo4sf.planet import probe_log  # noqa: E402
import make_planet_probe  # noqa: E402

IDX = 0x84                                   # the probe's load index: Papyrus prints its ids negative
OUR = 0x83


def sid(fid):
    """A form id as Papyrus prints it (signed decimal)."""
    return str(fid - (1 << 32) if fid & 0x80000000 else fid)


def b(v):
    """A bool as Starfield's Papyrus prints it."""
    return "true" if v else "false"


PROBE_WORLD, PROBE_LOC, PLANET = (IDX << 24) | 0x809, (IDX << 24) | 0x808, (OUR << 24) | 0x805
SURFACE, PLANET_LOC = (OUR << 24) | 0x804, (OUR << 24) | 0x802
RUNTIME = 0xFF00C482
MARS, LC172 = 0x03F59A, 0x02DF8C
SOL_LOC, UNIVERSE = 0x00018000, 0x0001A53A
PLAN = {"refs": [{"tag": "T1", "pos": [60.0, 50.0, 10.0]}, {"tag": "T3", "pos": [60.0, 64.0, 10.0]}],
        "merge": {"local": [40.4, 57.2, 7.6]}, "lc172_coc": {"local": [37.4, 57.2, 7.6]}, "system": "sol",
        "known_ids": {"Mars": f"{MARS:08X}", "LC172World (Mars)": f"{LC172:08X}",
                      "SSol system location": f"{SOL_LOC:08X}"}}
PROBE_UP = f"{sid(SURFACE)},{sid(PLANET_LOC)},{sid(SOL_LOC)},{sid(UNIVERSE)}"   # every ancestor, nearest first
SURFACE_UP, PLANET_UP = f"{sid(PLANET_LOC)},{sid(SOL_LOC)},{sid(UNIVERSE)}", f"{sid(SOL_LOC)},{sid(UNIVERSE)}"
CHAIN = (f"chain surface_has_probe=true planet_has_surface=true probe_parents={PROBE_UP} probe_planet={sid(PLANET)} "
         f"surface_parents={SURFACE_UP} surface_planet={sid(PLANET)} planet_parents={PLANET_UP} "
         f"planet_location={sid(PLANET_LOC)} gravity=0.63 day=24.0 temp=22.0")
CHAIN_V1 = (f"chain probe_child_of_surface=false surface_child_of_planet=false probe_planet={sid(PLANET)} "
            f"surface_planet={sid(PLANET)} planet_location={sid(PLANET_LOC)} gravity=0.63 day=24.0 temp=22.0")
FLT_MAX = "340282346638528859811704183484516925440.000000"           # as probe run 1's log printed it


def ref(n, at, tag, world, x, y, same, found=True, local=0x800, plugin="FO4SFPlanetProbe.esm", rid=None):
    head = f"ref n={n} at={at} tag={tag} local={local} plugin={plugin}"
    if not found:
        return head + " found=False"                       # literal text in the script
    return (head + f" found=True id={sid(rid or (IDX << 24) | local)} world={sid(world)} cell=none loc=none "
            f"editorloc={sid(PROBE_LOC)} x={x} y={y} z=10.0 loaded={b(same)} disabled=false "
            f"dist={'12.5' if same else FLT_MAX} sameworld={b(same)} actor=false")


def log_lines(planet_readings=(2, 10, 30, 60), chain=CHAIN, version=2):
    rt = [0.0]

    def line(msg):
        rt[0] += 0.5
        return f"[10/29/2026 - 03:00:00AM] FO4SFPP rt={rt[0]:.6f} {msg}"
    out = [line(f"init version={version} quest={sid((IDX << 24) | 0x814)} world={sid(PROBE_WORLD)} "
                f"loc={sid(PROBE_LOC)} planet={sid(PLANET)} surface={sid(SURFACE)} planetloc={sid(PLANET_LOC)} "
                "merge=true"),
           line(chain),
           "some other papyrus line", "FO4SFPP rt=1.0 unknown x=1",
           line(f"arrive n=1 world={sid(RUNTIME)} cell=none x=-462.6 y=-2242.8 z=7.6 probeworld=false")]
    for at in (2, 10, 30, 60):
        out.append(line(f"player n=1 at={at} world={sid(RUNTIME)} cell=none loc=none planet={MARS} x=-462.6 y=-2242.8 "
                        "z=7.6 ourplanet=false probeloc=false probeworld=false"))
        out.append(line(ref(1, at, "MERGE", RUNTIME, -459.6, -2242.8, True, local=0x800, plugin="FO4SFMergeProbe.esm",
                            rid=0x85000800)))
        out.append(line(ref(1, at, "LC172COC", RUNTIME, -462.6, -2242.8, True, local=0x10238E, plugin="Starfield.esm",
                            rid=0x0010238E)))
        out.append(line(ref(1, at, "T1", PROBE_WORLD, 60.0, 50.0, False)))
    out.append(line(f"arrive n=2 world={sid(RUNTIME + 1)} cell=none x=60.0 y=50.0 z=11.0 probeworld=false"))
    for at in planet_readings:
        out.append(line(f"player n=2 at={at} world={sid(RUNTIME + 1)} cell=none loc={sid(PROBE_LOC)} planet={sid(PLANET)} "
                        "x=60.0 y=50.0 z=11.0 ourplanet=true probeloc=true probeworld=false"))
        out.append(line(f"planet n=2 at={at} id={sid(PLANET)} gravity=0.63 day=24.0 temp=22.0 pressure=1.0 type=1414 "
                        f"atmos=none loc={sid((OUR << 24) | 0x802)}"))
        out.append(line(ref(2, at, "T1", PROBE_WORLD, 60.0, 50.0, False)))
        out.append(line(ref(2, at, "T3", RUNTIME + 1, 60.0, 64.0, True, local=0x802)))
        out.append(line(ref(2, at, "T5", 0, 0, 0, False, found=False, local=0x804)))
        out.append(line(f"ref n=2 at={at} tag=MERGE local=2048 plugin=FO4SFMergeProbe.esm installed=False"))
        out.append(line(f"location n=2 at={at} tag=probe id={sid(PROBE_LOC)} loaded=true actors=1"))
    return out


def fo4_style(lines):
    """The same log with Fallout 4's spelling of a bool (True / False)."""
    return [re.sub(r"=(true|false)\b", lambda m: "=" + m.group(1).capitalize(), x) for x in lines]


def drifted(lines):
    """The same log with literal text in other cases, as Starfield's one-spelling-per-string cache can print it."""
    swaps = [("FO4SFPP", "fo4sfpp"), (" arrive ", " Arrive "), (" player ", " PLAYER "), ("tag=T1", "tag=t1"),
             ("tag=MERGE", "tag=Merge"), ("=none", "=None"), ("FO4SFPlanetProbe.esm", "fo4sfplanetprobe.esm"),
             ("sameworld=", "SameWorld="), ("found=True", "found=true"), ("installed=False", "installed=false"),
             ("=true", "=TRUE")]
    out = []
    for x in lines:
        for a, c in swaps:
            x = x.replace(a, c)
        out.append(x)
    return out


class ParseTests(unittest.TestCase):
    def test_values_and_signed_ids(self):
        p = probe_log.parse_line(f"x FO4SFPP rt=1.5 arrive n=3 world={sid(RUNTIME)} cell=none x=1.5 y=-2 z=0 probeworld=true")
        self.assertEqual(p, {"rt": 1.5, "event": "arrive", "n": 3, "world": RUNTIME, "cell": None, "x": 1.5, "y": -2.0,
                             "z": 0.0, "probeworld": True})
        self.assertIsNone(probe_log.parse_line("FO4SFPP rt=1 unknown a=b"))
        self.assertIsNone(probe_log.parse_line("nothing here"))

    def test_bools_none_events_keys_and_tags_in_any_case(self):
        for text in ("probeworld=true", "probeworld=True", "PROBEWORLD=TRUE"):
            self.assertIs(probe_log.parse_line(f"FO4SFPP rt=2 arrive n=1 cell=none {text}")["probeworld"], True)
        for text in ("probeworld=false", "probeworld=False"):
            self.assertIs(probe_log.parse_line(f"FO4SFPP rt=2 arrive n=1 {text}")["probeworld"], False)
        p = probe_log.parse_line("fo4sfpp rt=2 REF n=1 at=2 tag=t1 local=2048 World=None found=true")
        self.assertEqual((p["event"], p["tag"], p["world"], p["found"]), ("ref", "T1", None, True))

    def test_a_string_is_never_read_as_a_true_flag(self):
        r = probe_log.parse_line("FO4SFPP rt=2 ref n=1 at=2 tag=T1 found=True world=5 sameworld=yes")
        self.assertEqual(probe_log.ref_verdict(r), "unknown")
        cut = probe_log.parse_line("FO4SFPP rt=2 ref n=1 at=2 tag=T1 local=2048 plugin=FO4SFPlanetProbe.esm found=True")
        self.assertEqual(probe_log.ref_verdict(cut), "unknown")
        both_inside = probe_log.parse_line("FO4SFPP rt=2 ref n=1 at=2 tag=T1 found=True world=none sameworld=true")
        self.assertEqual(probe_log.ref_verdict(both_inside), "unknown")

    def test_a_cut_ref_line_without_a_tag_is_skipped(self):
        lines = log_lines() + ["FO4SFPP rt=99 ref n=2 at=60"]
        s = probe_log.summarize(lines, PLAN)
        self.assertNotIn(None, s["arrivals"][1]["refs"])
        self.assertTrue(probe_log.verdict_table(s))

    def test_runs_split_at_init(self):
        lines = log_lines() + log_lines()
        self.assertEqual(len(probe_log.runs(lines)), 2)
        self.assertEqual(probe_log.runs(["FO4SFPP rt=1 arrive n=1"])[0][0]["event"], "arrive")


class SummaryTests(unittest.TestCase):
    def test_verdicts_offsets_and_kinds(self):
        s = probe_log.summarize(log_lines(), PLAN)
        self.assertEqual((s["runs"], s["load_index"], s["problems"]), (1, IDX, []))
        a1, a2 = s["arrivals"]
        self.assertEqual((a1["kind"], a1["world"], a1["complete"]), ("Mars", f"runtime {RUNTIME:08X}", True))
        self.assertEqual(a1["refs"]["MERGE"]["verdict"], "with player")
        self.assertEqual(a1["refs"]["MERGE"]["offset"], [-500.0, -2300.0])
        self.assertEqual(a1["refs"]["LC172COC"]["offset"], [-500.0, -2300.0])
        self.assertEqual(a1["refs"]["T1"]["world"], "probe world")
        self.assertEqual(a1["refs"]["T1"]["verdict"], "left behind")
        self.assertEqual((a2["kind"], a2["player"]["loc"], a2["planet"]["gravity"]), ("our planet", "probe location", 0.63))
        self.assertEqual({t: r["verdict"] for t, r in a2["refs"].items()},
                         {"T1": "left behind", "T3": "with player", "T5": "not loaded", "MERGE": "not installed"})
        self.assertEqual(a2["refs"]["T1"]["offset"], [0.0, 0.0])
        self.assertEqual(a2["location"], {"at": 60, "loaded": True, "actors": 1})
        table = probe_log.verdict_table(s)
        self.assertTrue(table[0].startswith("tag"))
        self.assertEqual([row.split()[0] for row in table[1:]], ["T1", "T3", "T5", "LC172COC", "MERGE"])
        self.assertIn("with player (-500, -2300)", table[-1])

    def test_fallout4_spelling_and_case_drift_read_the_same(self):
        want = probe_log.summarize(log_lines(), PLAN)
        for lines in (fo4_style(log_lines()), drifted(log_lines())):
            got = probe_log.summarize(lines, PLAN)
            self.assertEqual(probe_log.verdict_table(got), probe_log.verdict_table(want))
            self.assertEqual([a["kind"] for a in got["arrivals"]], [a["kind"] for a in want["arrivals"]])
            self.assertEqual((got["problems"], got["load_index"]), (want["problems"], want["load_index"]))

    def test_the_chain_line(self):
        s = probe_log.summarize(log_lines(), PLAN)
        self.assertEqual(s["chain_reading"], {
            "links": {"surface_has_probe": True, "planet_has_surface": True},
            "parents": {"the probe location": ["our surface", "our planet location", "SSol system location",
                                               f"{UNIVERSE:08X}"],
                        "our surface": ["our planet location", "SSol system location", f"{UNIVERSE:08X}"],
                        "our planet location": ["SSol system location", f"{UNIVERSE:08X}"]},
            "holds": {"the probe location under our surface": True, "our surface under our planet location": True,
                      "our planet location under the system location": True},
            "ancestors": True})
        self.assertEqual((s["problems"], s["notes"]), ([], []))
        # Sol's location missing from our planet location's list: that link is the problem
        broken = (CHAIN.replace("planet_has_surface=true", "planet_has_surface=false")
                  .replace(f"planet_parents={PLANET_UP}", f"planet_parents={sid(UNIVERSE)}"))
        s = probe_log.summarize(log_lines(chain=broken), PLAN)
        self.assertEqual(s["problems"], ["chain: planet_has_surface is false",
                                         "chain: the system location is not among our planet location's parents"])
        # lists of the direct parent only: every link still holds, and the probe location's list stops there
        direct = (CHAIN.replace(f"probe_parents={PROBE_UP}", f"probe_parents={sid(SURFACE)}")
                  .replace(f"surface_parents={SURFACE_UP}", f"surface_parents={sid(PLANET_LOC)}")
                  .replace(f"planet_parents={PLANET_UP}", f"planet_parents={sid(SOL_LOC)}"))
        s = probe_log.summarize(log_lines(chain=direct), PLAN)
        self.assertEqual((s["problems"], s["chain_reading"]["ancestors"]), ([], False))
        self.assertEqual(set(s["chain_reading"]["holds"].values()), {True})
        # an empty list: that location's own parent is missing, the other links stand
        empty = CHAIN.replace(f"probe_parents={PROBE_UP}", "probe_parents=none")
        s = probe_log.summarize(log_lines(chain=empty), PLAN)
        self.assertEqual(s["chain_reading"]["parents"]["the probe location"], [])
        self.assertEqual(s["problems"], ["chain: our surface is not among the probe location's parents"])
        # no plan: the system location is not known, so it is not missed
        s = probe_log.summarize(log_lines(chain=broken.replace("planet_has_surface=false", "planet_has_surface=true")))
        self.assertEqual(s["chain_reading"]["holds"]["our planet location under the system location"], None)
        self.assertEqual(s["problems"], [])

    def test_a_version_1_chain_line_is_no_evidence(self):
        s = probe_log.summarize(log_lines(chain=CHAIN_V1, version=1), PLAN)
        self.assertEqual(s["problems"], [])
        self.assertEqual(len(s["notes"]), 1)
        self.assertIn("wrong way round", s["notes"][0])
        self.assertIn("probe_child_of_surface and surface_child_of_planet are no evidence", s["notes"][0])
        self.assertEqual(s["chain_reading"], {"links": {}})
        # a route A plan: our own system location, named from the init line's planet location
        names = probe_log.known_names({"refs": []}, probe_log.summarize(log_lines())["init"])
        self.assertEqual(names[(OUR << 24) | 0x801], "our system location")
        self.assertNotIn((OUR << 24) | 0x801, probe_log.known_names(None, probe_log.summarize(log_lines())["init"]))

    def test_the_table_leaves_out_another_worlds_distance_and_minus_zero(self):
        s = probe_log.summarize(log_lines(), PLAN)
        t1 = s["arrivals"][0]["refs"]["T1"]
        self.assertEqual((t1["verdict"], t1["dist"]), ("left behind", float(FLT_MAX)))
        table = probe_log.verdict_table(s)
        row = next(r for r in table if r.startswith("T1"))
        self.assertNotIn("3402823", row)
        self.assertIn("left behind (0, 0)  ", row + "  ")
        self.assertIn("with player (-500, -2300) 12 m", table[-1])
        moved = [x.replace("x=60.0 y=50.0 z=10.0", "x=59.999 y=49.999 z=10.0") for x in log_lines()]
        self.assertEqual(probe_log.summarize(moved, PLAN)["arrivals"][0]["refs"]["T1"]["offset"], [0.0, 0.0])
        self.assertNotIn("-0", next(r for r in probe_log.verdict_table(probe_log.summarize(moved, PLAN))
                                    if r.startswith("T1")))

    def test_problems(self):
        self.assertEqual(probe_log.summarize([])["problems"], ["no FO4SFPP line in the log"])
        mars_only = [x for x in log_lines() if " n=2 " not in x]
        s = probe_log.summarize(mars_only, PLAN)
        self.assertIn("no arrival on our planet", s["problems"])
        self.assertEqual(s["arrivals"][0]["kind"], "Mars")
        self.assertEqual(s["arrivals"][0]["refs"]["T1"]["verdict"], "left behind")
        self.assertEqual(probe_log.summarize(log_lines() + log_lines(), PLAN, run=0)["run"], 0)


class LogCommandTests(unittest.TestCase):
    def run_log(self, lines, *extra):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "FO4SFPlanetProbe.0.log")
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            out = os.path.join(d, "summary.json")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = make_planet_probe.main(["log", "--file", path, "--out", out, *extra])
            with open(out, encoding="utf-8") as f:
                summary = json.load(f)
        return code, buf.getvalue(), summary

    def test_complete_run_exits_0(self):
        code, text, summary = self.run_log(log_lines())
        self.assertEqual(code, 0, text)
        self.assertIn("arrival 2 (our planet)", text)
        self.assertEqual(len(summary["arrivals"]), 2)
        self.assertIn(f"the probe location's parents: our surface, our planet location, {SOL_LOC:08X}, {UNIVERSE:08X}",
                      text)                                     # no stage given: Sol's location by its id
        self.assertIn(f"our planet location's parents: {SOL_LOC:08X}, {UNIVERSE:08X}", text)
        self.assertIn("the probe location under our surface: yes; our surface under our planet location: yes; "
                      "our planet location under the system location: not known", text)
        self.assertIn("the probe location's list goes past its own parent", text)

    def test_a_version_1_log_prints_its_note(self):
        code, text, _ = self.run_log(log_lines(chain=CHAIN_V1, version=1))
        self.assertEqual(code, 0, text)
        self.assertIn("NOTE  chain: this log's script (version 1) asked IsChild the wrong way round", text)
        self.assertNotIn("PROBLEM", text)

    def test_incomplete_run_exits_1(self):
        code, text, _ = self.run_log(log_lines(planet_readings=(2, 10)))
        self.assertEqual(code, 1)
        self.assertIn("(incomplete)", text)

    def test_a_mars_only_run_exits_1(self):
        code, text, _ = self.run_log([x for x in log_lines() if " n=2 " not in x])
        self.assertEqual(code, 1, text)
        self.assertIn(f"arrival 1 ({MARS:08X})", text)                  # no plan: Mars by its id
        self.assertNotIn("(our planet)", text)
        self.assertIn("PROBLEM  no arrival on our planet", text)

    def test_the_default_log_is_found_under_onedrive_or_documents(self):
        with tempfile.TemporaryDirectory() as home:
            name = make_planet_probe.probe.LOG_NAME + ".0.log"
            plain = os.path.join(home, "Documents", "My Games", "Starfield", "Logs", "Script", "User", name)
            synced = os.path.join(home, "OneDrive", "Documents", "My Games", "Starfield", "Logs", "Script", "User", name)
            with mock.patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}):
                self.assertEqual(make_planet_probe.user_logs(), [synced, plain])
                with self.assertRaises(SystemExit) as e:
                    make_planet_probe.main(["log"])
                self.assertIn("pass --file", str(e.exception))
                for path in (plain, synced):
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, "w", encoding="utf-8") as f:
                        f.write("\n".join(log_lines()) + "\n")
                    buf = io.StringIO()
                    with contextlib.redirect_stdout(buf):
                        code = make_planet_probe.main(["log"])
                    self.assertEqual(code, 0, buf.getvalue())
                    self.assertIn(f"log {path}", buf.getvalue())

    def test_a_missing_file_is_a_message_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit) as e:
                make_planet_probe.main(["log", "--file", os.path.join(d, "nope.log")])
        self.assertIn("nope.log", str(e.exception))


if __name__ == "__main__":
    unittest.main()
