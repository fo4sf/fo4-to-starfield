"""src/fo4sf/planet/probe_log.py and make_planet_probe.py log on a synthetic FO4SFPlanetProbe.0.log written in the
probe script's line format (scripts/planet/FO4SF_PlanetProbeQuest.psc); no game."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

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


PROBE_WORLD, PROBE_LOC, PLANET = (IDX << 24) | 0x809, (IDX << 24) | 0x808, (OUR << 24) | 0x805
RUNTIME = 0xFF00C482
MARS, LC172 = 0x03F59A, 0x02DF8C
PLAN = {"refs": [{"tag": "T1", "pos": [60.0, 50.0, 10.0]}, {"tag": "T3", "pos": [60.0, 64.0, 10.0]}],
        "merge": {"local": [40.4, 57.2, 7.6]}, "lc172_coc": {"local": [37.4, 57.2, 7.6]},
        "known_ids": {"Mars": f"{MARS:08X}", "LC172World (Mars)": f"{LC172:08X}"}}


def ref(n, at, tag, world, x, y, same, found=True, local=0x800, plugin="FO4SFPlanetProbe.esm", rid=None):
    head = f"ref n={n} at={at} tag={tag} local={local} plugin={plugin}"
    if not found:
        return head + " found=False"
    return (head + f" found=True id={sid(rid or (IDX << 24) | local)} world={sid(world)} cell=none loc=none "
            f"editorloc={sid(PROBE_LOC)} x={x} y={y} z=10.0 loaded={same} disabled=False dist=12.5 sameworld={same} "
            "actor=False")


def log_lines(planet_readings=(2, 10, 30, 60)):
    rt = [0.0]

    def line(msg):
        rt[0] += 0.5
        return f"[10/29/2026 - 03:00:00AM] FO4SFPP rt={rt[0]:.3f} {msg}"
    out = [line(f"init version=1 quest={sid((IDX << 24) | 0x814)} world={sid(PROBE_WORLD)} loc={sid(PROBE_LOC)} "
                f"planet={sid(PLANET)} surface={sid((OUR << 24) | 0x804)} planetloc={sid((OUR << 24) | 0x802)} merge=True"),
           line(f"chain probe_child_of_surface=True surface_child_of_planet=True probe_planet={sid(PLANET)} "
                f"surface_planet={sid(PLANET)} planet_location={sid((OUR << 24) | 0x802)} gravity=0.63 day=24.0 temp=22.0"),
           "some other papyrus line", "FO4SFPP rt=1.0 unknown x=1",
           line(f"arrive n=1 world={sid(RUNTIME)} cell=none x=-462.6 y=-2242.8 z=7.6 probeworld=False")]
    for at in (2, 10, 30, 60):
        out.append(line(f"player n=1 at={at} world={sid(RUNTIME)} cell=none loc=none planet={MARS} x=-462.6 y=-2242.8 "
                        "z=7.6 ourplanet=False probeloc=False probeworld=False"))
        out.append(line(ref(1, at, "MERGE", RUNTIME, -459.6, -2242.8, True, local=0x800, plugin="FO4SFMergeProbe.esm",
                            rid=0x85000800)))
        out.append(line(ref(1, at, "LC172COC", RUNTIME, -462.6, -2242.8, True, local=0x10238E, plugin="Starfield.esm",
                            rid=0x0010238E)))
        out.append(line(ref(1, at, "T1", PROBE_WORLD, 60.0, 50.0, False)))
    out.append(line(f"arrive n=2 world={sid(RUNTIME + 1)} cell=none x=60.0 y=50.0 z=11.0 probeworld=False"))
    for at in planet_readings:
        out.append(line(f"player n=2 at={at} world={sid(RUNTIME + 1)} cell=none loc={sid(PROBE_LOC)} planet={sid(PLANET)} "
                        "x=60.0 y=50.0 z=11.0 ourplanet=True probeloc=True probeworld=False"))
        out.append(line(f"planet n=2 at={at} id={sid(PLANET)} gravity=0.63 day=24.0 temp=22.0 pressure=1.0 type=1414 "
                        f"atmos=none loc={sid((OUR << 24) | 0x802)}"))
        out.append(line(ref(2, at, "T1", PROBE_WORLD, 60.0, 50.0, False)))
        out.append(line(ref(2, at, "T3", RUNTIME + 1, 60.0, 64.0, True, local=0x802)))
        out.append(line(ref(2, at, "T5", 0, 0, 0, False, found=False, local=0x804)))
        out.append(line(f"ref n=2 at={at} tag=MERGE local=2048 plugin=FO4SFMergeProbe.esm installed=False"))
        out.append(line(f"location n=2 at={at} tag=probe id={sid(PROBE_LOC)} loaded=True actors=1"))
    return out


class ParseTests(unittest.TestCase):
    def test_values_and_signed_ids(self):
        p = probe_log.parse_line(f"x FO4SFPP rt=1.5 arrive n=3 world={sid(RUNTIME)} cell=none x=1.5 y=-2 z=0 probeworld=True")
        self.assertEqual(p, {"rt": 1.5, "event": "arrive", "n": 3, "world": RUNTIME, "cell": None, "x": 1.5, "y": -2.0,
                             "z": 0.0, "probeworld": True})
        self.assertIsNone(probe_log.parse_line("FO4SFPP rt=1 unknown a=b"))
        self.assertIsNone(probe_log.parse_line("nothing here"))

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
        self.assertEqual((a2["kind"], a2["player"]["loc"], a2["planet"]["gravity"]), ("our planet", "probe location", 0.63))
        self.assertEqual({t: r["verdict"] for t, r in a2["refs"].items()},
                         {"T1": "left behind", "T3": "with player", "T5": "not loaded", "MERGE": "not installed"})
        self.assertEqual(a2["refs"]["T1"]["offset"], [0.0, 0.0])
        self.assertEqual(a2["location"], {"at": 60, "loaded": True, "actors": 1})
        table = probe_log.verdict_table(s)
        self.assertTrue(table[0].startswith("tag"))
        self.assertEqual([row.split()[0] for row in table[1:]], ["T1", "T3", "T5", "LC172COC", "MERGE"])
        self.assertIn("with player (-500, -2300)", table[-1])

    def test_problems(self):
        self.assertEqual(probe_log.summarize([])["problems"], ["no FO4SFPP line in the log"])
        lines = [x.replace("probe_child_of_surface=True", "probe_child_of_surface=False") for x in log_lines()]
        self.assertIn("chain: probe_child_of_surface is False", probe_log.summarize(lines)["problems"])
        mars_only = [x for x in log_lines() if " n=2 " not in x]
        self.assertIn("no arrival on our planet", probe_log.summarize(mars_only)["problems"])
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

    def test_incomplete_run_exits_1(self):
        code, text, _ = self.run_log(log_lines(planet_readings=(2, 10)))
        self.assertEqual(code, 1)
        self.assertIn("(incomplete)", text)


if __name__ == "__main__":
    unittest.main()
