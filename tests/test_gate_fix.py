"""scripts/newgame/make_gate_fix.py and dotnet/GateFix on synthetic files: a fixture FO4Port.esm (one STAT, one reference 001317), a
synthetic port archive holding a gate NIF whose bodies are on layer 55, and the staged result read back. No game, no Windows; the
dotnet tests skip without the .NET SDK. The walk in game is the PC's job (the stage's README names it). FAL-976."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for p in (HERE, ROOT / "scripts" / "newgame", ROOT / "scripts" / "game", ROOT / "scripts" / "planet", ROOT / "src"):
    sys.path.insert(0, str(p))
from ba2_fixture import general_archive  # noqa: E402
from fo4sf import nif, sfbodies  # noqa: E402
import make_gate_fix as mgf  # noqa: E402
from test_relayer import RelayerNifTests  # noqa: E402

MODEL = "Meshes/fo4port/interiors/vault/gate/v111gearroomgate01_xrgd_test.nif"


class PureTests(unittest.TestCase):
    def test_the_new_path_sits_beside_the_old_one_and_never_equals_it(self):
        full, below = mgf.new_model_path(MODEL)
        self.assertEqual(full, "Meshes/fo4port/interiors/vault/gate/v111gearroomgate01_xrgd_test_gf.nif")
        self.assertEqual(below, "fo4port\\interiors\\vault\\gate\\v111gearroomgate01_xrgd_test_gf.nif")
        self.assertNotEqual(full.lower(), MODEL.lower())

    def test_a_model_that_is_not_a_nif_is_refused(self):
        with self.assertRaises(SystemExit):
            mgf.new_model_path("Meshes/x/y.mesh")

    def test_a_model_without_layer_55_is_refused_not_staged(self):
        raw = RelayerNifTests().nif_with([0x1])
        with self.assertRaises(SystemExit) as c:
            mgf.relayer_model(raw)
        self.assertIn("nothing for this fix to change", str(c.exception))

    def test_info_output_is_parsed_and_an_empty_one_refused(self):
        self.assertEqual(mgf.parse_info("BASE_ID 0x00DEF8\nMODEL Meshes\\a\\b.nif\n"), {"base_id": "00DEF8", "model": "Meshes/a/b.nif"})
        with self.assertRaises(SystemExit):
            mgf.parse_info("BASE_ID 0x00DEF8\nMODEL \n")


class StageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet") or (str(Path.home() / ".dotnet" / "dotnet") if (Path.home() / ".dotnet" / "dotnet").exists() else None)
        if not cls.dotnet:
            raise unittest.SkipTest(".NET SDK needed for the actual tool test")
        proc = subprocess.run([cls.dotnet, "build", str(ROOT / "dotnet" / "GateFix"), "-c", "Release", "--nologo"], capture_output=True, text=True)
        if proc.returncode:
            raise AssertionError(proc.stdout + proc.stderr)
        cls.tool = ROOT / "dotnet/GateFix/bin/Release/net9.0/GateFix.dll"
        tmp = tempfile.TemporaryDirectory(prefix="fo4sf-gate-")
        cls.addClassCleanup(tmp.cleanup)
        cls.root = Path(tmp.name)
        cls.data = cls.root / "Data"
        r = cls.run_tool("fixture", cls.data)
        assert r.returncode == 0, r.stdout + r.stderr
        cls.raw = RelayerNifTests().nif_with([0x8037, 0x8037])
        (cls.data / "FO4Port - Main.ba2").write_bytes(general_archive({MODEL: cls.raw}))

    @classmethod
    def run_tool(cls, *argv):
        return subprocess.run([cls.dotnet, str(cls.tool), *map(str, argv)], capture_output=True, text=True)

    def args(self, out, **kw):
        d = dict(out=str(out), starfield_data=str(self.data), port_data="", ref="")
        d.update(kw)
        return argparse.Namespace(**d)

    def test_the_tool_names_the_base_the_reference_stands_on(self):
        info = self.run_tool("info", self.data / "FO4Port.esm", self.data / "Starfield.esm")
        self.assertEqual(info.returncode, 0, info.stderr)
        self.assertEqual(mgf.parse_info(info.stdout), {"base_id": "00DEF8", "model": MODEL})

    def test_a_reference_that_is_not_there_is_refused(self):
        proc = self.run_tool("info", self.data / "FO4Port.esm", self.data / "Starfield.esm", "--ref", "0099")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("0 placed references with local id 000099", proc.stderr)

    def test_stage_writes_the_relayered_model_on_a_new_path_and_the_override(self):
        out = self.root / "staged"
        self.assertEqual(mgf.stage(self.args(out)), 0)
        new = out / "Data" / "Meshes" / "fo4port" / "interiors" / "vault" / "gate" / "v111gearroomgate01_xrgd_test_gf.nif"
        self.assertTrue(new.is_file())
        self.assertEqual([b["layer"] for b in sfbodies.nif_bodies(new.read_bytes())], [1, 1])
        self.assertEqual([b["layer"] for b in sfbodies.nif_bodies(self.raw)], [55, 55])        # the source bytes are not touched
        self.assertEqual(len(new.read_bytes()), len(self.raw))
        m = json.loads((out / "gate_manifest.json").read_text())
        self.assertEqual((m["bodies_relayered"], m["base_id"], m["model"]), (2, "00DEF8", MODEL[:-4] + "_gf.nif"))
        self.assertEqual(m["source_sha256"], hashlib.sha256(self.raw).hexdigest())
        plan = json.loads((out / "plan.json").read_text())
        self.assertEqual(sorted(plan["outputs"]), ["Data/" + MODEL[:-4] + "_gf.nif", "FO4SFGateFix.esm"])
        self.assertEqual(mgf.verify_stage(str(out), plan, str(self.data)), [])
        self.assertIn("all checks pass", (out / "offline_check.txt").read_text())
        self.assertFalse((out / "work").exists())

    def test_a_stage_changed_after_the_fact_is_found(self):
        out = self.root / "staged-tamper"
        mgf.stage(self.args(out))
        plan = json.loads((out / "plan.json").read_text())
        nif_path = out / "Data" / "Meshes" / "fo4port" / "interiors" / "vault" / "gate" / "v111gearroomgate01_xrgd_test_gf.nif"
        nif_path.write_bytes(self.raw)
        problems = mgf.verify_stage(str(out), plan)
        self.assertEqual(len(problems), 1)
        self.assertIn("changed after the stage", problems[0])

    def test_stage_refuses_an_existing_folder_and_a_model_no_archive_holds(self):
        out = self.root / "exists"
        out.mkdir()
        with self.assertRaises(SystemExit):
            mgf.stage(self.args(out))
        empty = self.root / "Data2"
        shutil.copytree(self.data, empty)
        (empty / "FO4Port - Main.ba2").unlink()
        (empty / "FO4Port - Main.ba2").write_bytes(general_archive({"Meshes/other.nif": b"x"}))
        with self.assertRaises(SystemExit) as c:
            mgf.stage(self.args(self.root / "none", starfield_data=str(empty)))
        self.assertIn("holds", str(c.exception))

    def test_check_fails_when_the_override_would_shadow_the_ports_own_path(self):
        out = self.root / "build-own"
        built = self.run_tool("build", self.data / "FO4Port.esm", self.data / "Starfield.esm", out, "--model", MODEL[len("Meshes/"):].replace("/", "\\"))
        self.assertEqual(built.returncode, 0, built.stderr)
        check = self.run_tool("check", out / "FO4SFGateFix.esm", self.data / "FO4Port.esm", self.data / "Starfield.esm",
                              "--model", MODEL[len("Meshes/"):].replace("/", "\\"))
        self.assertEqual(check.returncode, 1)
        self.assertIn("the model path is the port's own", check.stdout)


if __name__ == "__main__":
    unittest.main()
