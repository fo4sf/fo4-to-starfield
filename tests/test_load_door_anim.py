"""Load doors that open before the trip (docs/spikes/load-door-animations.md): the converter switch, the twin planner,
the animated VMAD and the batch flag. Synthetic fixtures only; every switch is off by default."""
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "terrain"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_sliding_doors  # noqa: E402
from test_door_two_panels import door_nif, two_leaves  # noqa: E402
from fo4sf import load_door_anim, nif  # noqa: E402
import vmad_patch  # noqa: E402


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, *rel.split("/")))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


convert_batch = _load("convert_batch_lda", "scripts/convert_batch.py")
cli = _load("load_door_anim_cli", "scripts/door_bridge/load_door_anim.py")

LOAD = "meshes\\SetDressing\\Doors\\SynthDoorLoad01.nif"
BOUNDS = [[-1.0, -0.1, 0.0], [1.0, 0.1, 2.2]]


def item(edid, source, **extra):
    return dict({"editor_id": edid, "model": "fo4port\\" + edid.lower() + ".nif", "source": source}, **extra)


def rigged(offset=(0.5, 0.0, 0.0), rig=None):
    lo, hi = BOUNDS
    d = {"origin_offset": list(offset), "anim_graph": "SimpleOpenClose01.agx", "skeleton": "t\\skeleton.rig",
         "animations": "t\\animations",
         "bounds": [[lo[a] - offset[a] for a in range(3)], [hi[a] - offset[a] for a in range(3)]]}
    if rig:
        d["rig"] = rig
    return d


class ConverterSwitchTests(unittest.TestCase):
    convert = test_sliding_doors.NonHingedRoutingTests.convert

    def test_off_by_default_a_load_door_is_not_rigged(self):
        with tempfile.TemporaryDirectory() as staging:
            result, single, multi, static = self.convert(staging, LOAD, two_leaves()[:1], None)
        self.assertIn("load_door", result)
        self.assertNotIn("anim", result["load_door"])
        self.assertNotIn("door", result)
        single.assert_not_called()
        static.assert_called_once()

    def test_on_an_animated_load_door_gets_its_rig_in_the_load_door_entry(self):
        with tempfile.TemporaryDirectory() as staging:
            result, single, multi, static = self.convert(staging, LOAD, two_leaves()[:1], None, rig_load_doors=True)
        single.assert_called_once()
        static.assert_not_called()
        self.assertNotIn("door", result)                       # never a second, non-load opening door
        anim = result["load_door"]["anim"]
        self.assertEqual(anim["anim_graph"], "AnimTextData\\Tables\\Graphs\\SimpleOpenClose01.agx")
        self.assertIn("bounds", result["load_door"])
        self.assertGreater(anim["open_seconds"], 0)

    def test_on_a_teleporting_hatch_without_a_door_name_takes_the_own_rig_route(self):
        hatch = "meshes\\SetDressing\\Synthetic\\RoofHatch01.nif"
        with tempfile.TemporaryDirectory() as staging:
            result, single, multi, static = self.convert(staging, hatch, two_leaves()[:1], "calumi.dll",
                                                         load_door_models={hatch.lower()}, rig_load_doors=True)
        multi.assert_called_once()
        self.assertEqual(result["load_door"]["anim"]["rig"], "native")

    def test_on_a_load_door_that_does_not_animate_stays_static(self):
        with tempfile.TemporaryDirectory() as staging:
            result, single, multi, static = self.convert(staging, LOAD, [], None, rig_load_doors=True)
        single.assert_not_called()
        multi.assert_not_called()
        self.assertNotIn("anim", result["load_door"])


class OpenTimingTests(unittest.TestCase):
    def test_reads_the_open_sequence(self):
        t = load_door_anim.open_timing(door_nif(two_leaves()))
        self.assertIsNotNone(t)
        self.assertAlmostEqual(t["seconds"], 1.0, places=3)
        self.assertEqual(t["events"], [])

    def test_none_without_an_open_sequence(self):
        f = door_nif(two_leaves())
        f.strings = [b"Idle" if x == b"Open" else x for x in f.strings]     # the sequence is there, but not "Open"
        self.assertIsNone(load_door_anim.open_timing(f))


class TwinTests(unittest.TestCase):
    def test_twin_names(self):
        self.assertEqual(load_door_anim.twin_names("meshes\\Doors\\UtilMetalDbDoorLoad01.nif"),
                         ["meshes\\Doors\\UtilMetalDbDoor01.nif"])
        self.assertEqual(load_door_anim.twin_names("meshes/Doors/Door_Load01.nif"), ["meshes\\Doors\\Door01.nif"])
        self.assertEqual(load_door_anim.twin_names("meshes\\Load\\RoofHatch01.nif"), [])

    def manifest(self, twin_door=None, twin_extra=None, load_extra=None):
        twin = item("SynthDoor", "meshes\\SetDressing\\Doors\\SynthDoor01.nif", **({"door": twin_door} if twin_door else {}),
                    **(twin_extra or {}))
        load = item("SynthDoorLoad", LOAD, load_door=dict({"bounds": BOUNDS}, **(load_extra or {})))
        return {"items": [twin, load]}

    def test_a_matching_twin_lends_its_rig_and_model(self):
        m = self.manifest(rigged())
        out, rows = load_door_anim.plan(m)
        anim = out["items"][1]["load_door"]["anim"]
        self.assertEqual(rows[0]["anim"], "twin")
        self.assertEqual(anim["model"], "fo4port\\synthdoor.nif")
        self.assertEqual(anim["origin_offset"], [0.5, 0.0, 0.0])
        self.assertAlmostEqual(anim["open_seconds"], load_door_anim.TEMPLATE_OPEN_SECONDS)
        self.assertNotIn("anim", m["items"][1]["load_door"])             # the input is never changed

    def test_refusals_keep_the_static_door(self):
        far = rigged()
        far["bounds"][1][2] += 0.2
        cases = {"twin bounds differ by more than 0.05 m": self.manifest(far),
                 "twin is not a rigged door (own rig: refused)": self.manifest(None, {"door_error": "own rig: refused"}),
                 "no non-load twin in this manifest": {"items": [item("X", LOAD, load_door={"bounds": BOUNDS})]},
                 "load door entry has no bounds (manifest older than 2026-10-10)":
                     {"items": [item("X", LOAD, load_door={"note": "static"})]}}
        for reason, m in cases.items():
            out, rows = load_door_anim.plan(m)
            self.assertEqual(rows[-1]["reason"], reason)
            self.assertIsNone(rows[-1]["anim"])
            self.assertNotIn("anim", out["items"][-1]["load_door"])

    def test_own_rig_is_kept_and_counted(self):
        m = self.manifest(rigged(), load_extra={"anim": rigged((0, 0, 0), "native")})
        out, rows = load_door_anim.plan(m)
        self.assertEqual(rows[0]["anim"], "own")
        self.assertEqual(out["items"][1]["load_door"]["anim"]["rig"], "native")
        self.assertEqual(load_door_anim.summary(rows), {"load_doors": 1, "own": 1, "twin": 0, "static": 0, "reasons": {}})

    def test_cli_writes_a_new_manifest_and_never_the_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "manifest.json")
            with open(src, "w") as f:
                json.dump(self.manifest(rigged()), f)
            def text(p):
                with open(p) as f:
                    return f.read()
            before = text(src)
            out = os.path.join(tmp, "new", "manifest.json")
            with redirect_stdout(io.StringIO()):
                cli.main(["plan", "--manifest", src, "--out", out])
                with self.assertRaises(SystemExit):
                    cli.main(["plan", "--manifest", src, "--out", out])        # an existing output is refused
                with self.assertRaises(SystemExit):
                    cli.main(["plan", "--manifest", src, "--out", src])
            self.assertEqual(text(src), before)
            self.assertIn("anim", json.loads(text(out))["items"][1]["load_door"])
            self.assertEqual(json.loads(text(out + ".load_doors.json"))["counts"]["twin"], 1)


class SurveyTests(unittest.TestCase):
    def test_own_open_twin_open_and_missing(self):
        animated = nif.serialize(door_nif(two_leaves()[:1]))
        f = door_nif(two_leaves()[:1])
        f.strings = [b"Idle" if x == b"Open" else x for x in f.strings]
        still = nif.serialize(f)
        files = {"meshes\\a\\OwnLoad.nif": animated, "meshes\\a\\TwinLoad.nif": still,
                 "meshes\\a\\Twin.nif": animated, "meshes\\a\\Broken.nif": b"not a nif"}
        rows = load_door_anim.survey(["meshes\\a\\OwnLoad.nif", "meshes\\a\\TwinLoad.nif", "meshes\\a\\Broken.nif",
                                      "meshes\\a\\Gone.nif"], files.get)
        own, twin, broken, gone = rows
        self.assertGreater(own["open_seconds"], 0)
        self.assertTrue(own["hinged"])
        self.assertEqual(own["twins"], [])
        self.assertIsNone(twin["open_seconds"])
        self.assertEqual([t["model"] for t in twin["twins"]], ["meshes\\a\\Twin.nif"])
        self.assertGreater(twin["twins"][0]["open_seconds"], 0)
        self.assertIn("error", broken)
        self.assertFalse(gone["found"])


class AnimatedVmadTests(unittest.TestCase):
    def test_round_trip_and_the_plain_reader_refuses_it(self):
        blob = vmad_patch.encode(vmad_patch.animated_load_door_scripts("FO4TerrainCore.esm", 0x81F, (1, 2, 3), 1.25))
        self.assertEqual(vmad_patch.animated_load_door_target(blob), ("FO4TerrainCore.esm", 0x81F, (1.0, 2.0, 3.0), 1.25))
        with self.assertRaisesRegex(ValueError, "script 'FO4SF_AnimatedLoadDoor'"):
            vmad_patch.load_door_target(blob)               # the port / check commands keep requiring FO4SF_LoadDoor
        plain = vmad_patch.load_door_vmad("FO4TerrainCore.esm", 0x81F, (1, 2, 3))
        with self.assertRaises(ValueError):
            vmad_patch.animated_load_door_target(plain)

    def test_open_seconds_must_be_sane(self):
        for bad in (-1, 31, float("nan"), "x"):
            with self.assertRaises(ValueError):
                vmad_patch.animated_load_door_scripts("FO4Port.esm", 1, None, bad)


sys.path.insert(0, os.path.join(ROOT, "scripts", "door_bridge"))
compile_anim = _load("compile_animated_load_door", "scripts/door_bridge/compile_animated_load_door.py")


class AnimatedScriptTests(unittest.TestCase):
    PSC = os.path.join(ROOT, "scripts", "door_bridge", "FO4SF_AnimatedLoadDoor.psc")

    def test_extends_the_load_door_and_declares_open_seconds(self):
        with open(self.PSC, encoding="utf-8") as f:
            text = f.read()
        self.assertTrue(text.startswith("Scriptname FO4SF_AnimatedLoadDoor extends FO4SF_LoadDoor"))
        self.assertIn(f"float Property {vmad_patch.PROP_OPEN_SECONDS} = 0.0 Auto", text)
        self.assertIn("Parent.OnActivate(akActionRef)", text)        # the travel itself stays FO4SF_LoadDoor's

    def compile(self, root, code=0, message="Compilation succeeded", outputs=("FO4SF_LoadDoor", "FO4SF_AnimatedLoadDoor")):
        compiler, resources, out = root / "c.exe", root / "r.zip", root / "out"
        compiler.write_bytes(b"c")
        resources.write_bytes(b"r")

        def extract(_resources, work):
            src = work / "Source"
            src.mkdir(parents=True)
            (src / "Game.psc").write_text("synthetic", encoding="utf-8")
            return src

        def run(cmd, **kwargs):
            stem = cmd[1][:-4]
            if stem in outputs:
                (out / "Data" / "Scripts" / f"{stem}.pex").write_bytes(b"pex " + stem.encode())
            return compile_anim.subprocess.CompletedProcess(cmd, code, message, "")
        with patch.object(compile_anim.base, "extract", extract), patch.object(compile_anim.subprocess, "run", run):
            return compile_anim.compile_animated(compiler, resources, out), out

    def test_both_scripts_are_compiled_and_pinned_never_installable(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            report, out = self.compile(Path(tmp))
            self.assertEqual(report["status"], "compiled")
            self.assertEqual(sorted(report["outputs"]), ["FO4SF_AnimatedLoadDoor.pex", "FO4SF_LoadDoor.pex"])
            self.assertFalse(report["installable"] or report["runtime_accepted"])

    def test_a_missing_child_pex_or_a_failed_run_fails(self):
        from pathlib import Path
        for kw in ({"outputs": ("FO4SF_LoadDoor",)}, {"code": 1}, {"message": "errors"}):
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError):
                    self.compile(Path(tmp), **kw)
                with open(Path(tmp) / "out" / "compile.json") as f:
                    self.assertEqual(json.load(f)["status"], "failed")


class BatchFlagTests(unittest.TestCase):
    def test_signature_names_the_switch_only_when_on(self):
        a = SimpleNamespace(fo4_data="", starfield_data="sf", texconv="t", content_resources="c", collision_template="x",
                            prefix="fo4port", static_items=False)
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(convert_batch.checkpoints, "digest", return_value="d"), \
                patch.object(convert_batch.checkpoints, "archive_identity", return_value={}):
            a.fo4_data = tmp
            self.assertNotIn("rig_load_doors", convert_batch.checkpoint_signature(a))
            a.rig_load_doors = True
            self.assertTrue(convert_batch.checkpoint_signature(a)["rig_load_doors"])


if __name__ == "__main__":
    unittest.main()
