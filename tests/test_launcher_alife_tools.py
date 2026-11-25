"""Headless tests for src/fo4sf/launcher/alife_tools.py (ModToolsModel + StepRunParser).

Pure headless stdlib tests: never imports tkinter, never launches Starfield, never writes into Git or game folders.
"""
import ast
import json
import os
import posixpath
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf.launcher import alife_tools  # noqa: E402


def _synthetic_tes4(masters=("Starfield.esm",), flags=0x101):
    def sub(sig, data):
        return sig + struct.pack("<H", len(data)) + data

    body = sub(b"HEDR", struct.pack("<fII", 0.96, 12, 0x800 + 12)) + sub(b"CNAM", b"synthetic\0")
    for master in masters:
        body += sub(b"MAST", master.encode("utf-8") + b"\0") + sub(b"DATA", bytes(8))
    return b"TES4" + struct.pack("<IIIIHH", len(body), flags, 0, 0, 0x210, 0) + body


def _make_shim_executable(folder: Path, stem: str, helper_py: Path) -> str:
    if os.name == "nt":
        shim = folder / f"{stem}.cmd"
        shim.write_text(f'@echo off\r\n"{sys.executable}" "{helper_py}" %*\r\n', encoding="utf-8")
        return str(shim)
    shim = folder / f"{stem}.sh"
    shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{helper_py}" "$@"\n', encoding="utf-8")
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return str(shim)


class AlifeToolsHeadlessTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.settings_path = self.root / "settings.json"
        self.launcher_path = ROOT / "scripts" / "launcher.py"
        self.sdk_script = ROOT / "scripts" / "alife" / "build_alife_mod.py"
        self.game_dir = self.root / "Fake Starfield"
        (self.game_dir / "Data").mkdir(parents=True)
        (self.game_dir / "Starfield.exe").write_bytes(b"")
        self.out_dir = self.root / "alife output dir"
        self.model = alife_tools.ModToolsModel(str(self.launcher_path), str(self.settings_path))

    def test_module_never_imports_tkinter(self):
        source = (ROOT / "src" / "fo4sf" / "launcher" / "alife_tools.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertNotIn("tkinter", imported)

    def test_steps_marks_and_progress(self):
        self.assertEqual(alife_tools.STEPS, ("init", "validate", "simulate", "package", "verify-dist"))
        for key in ("not_run", "running", "passed", "failed"):
            label, token = alife_tools.STEP_MARKS[key]
            self.assertIn(key.replace("_", " "), label)
            self.assertIn(token, ("muted", "warn", "ok", "bad"))
        self.assertEqual(alife_tools.progress({}), (0, 5))
        self.assertEqual(alife_tools.progress({"init": "passed", "validate": "passed", "simulate": "failed"}), (2, 5))
        self.assertEqual(alife_tools.progress({s: "passed" for s in alife_tools.STEPS}), (5, 5))
        self.assertEqual(alife_tools.progress_text({"init": "passed"}), "1/5 steps passed")

    def test_auto_discovers_sdk_script_and_supports_override(self):
        self.assertEqual(Path(self.model.sdk_script), self.sdk_script.resolve())
        missing = alife_tools.ModToolsModel(
            str(self.launcher_path),
            str(self.settings_path),
            sdk_script=str(self.root / "missing_sdk.py"),
        )
        with self.assertRaisesRegex(ValueError, "not found"):
            missing.command("init", output_dir=str(self.out_dir))

    def test_command_builders_for_all_five_steps_no_shell(self):
        self.settings_path.write_text(json.dumps({"starfield": str(self.game_dir)}), encoding="utf-8")
        self.model.reload()
        cfg = os.path.join(os.path.abspath(str(self.out_dir)), "alife_config.json")
        dist = os.path.join(os.path.abspath(str(self.out_dir)), "dist")
        prefix = [sys.executable, "-I", "-u", str(self.sdk_script.resolve())]

        self.assertEqual(
            self.model.command("init", output_dir=str(self.out_dir), template="custom", force=True),
            prefix + ["init", "--out", cfg, "--template", "custom", "--force"],
        )
        self.assertEqual(
            self.model.command("validate", output_dir=str(self.out_dir)),
            prefix + ["validate", "--config", cfg],
        )
        self.assertEqual(
            self.model.command("simulate", output_dir=str(self.out_dir), ticks=50, seed=99),
            prefix + ["simulate", "--config", cfg, "--ticks", "50", "--seed", "99"],
        )
        self.assertEqual(
            self.model.command("package", output_dir=str(self.out_dir), pack_ba2=False),
            prefix + ["package", "--config", cfg, "--out", dist, "--starfield-dir", str(self.game_dir.resolve())],
        )
        self.assertEqual(
            self.model.command("package", output_dir=str(self.out_dir), pack_ba2=True),
            prefix
            + ["package", "--config", cfg, "--out", dist, "--starfield-dir", str(self.game_dir.resolve()), "--pack-ba2"],
        )
        self.assertEqual(
            self.model.command("verify-dist", output_dir=str(self.out_dir)),
            prefix + ["verify-dist", "--dist-dir", dist],
        )

    def test_package_prefers_saved_instance_over_starfield_and_refuses_missing(self):
        with self.assertRaisesRegex(ValueError, "Locations tab"):
            self.model.command("package", output_dir=str(self.out_dir))

        instance_dir = self.root / "FO4SF Instance"
        instance_dir.mkdir()
        self.settings_path.write_text(
            json.dumps({"starfield": str(self.game_dir), "instance": str(instance_dir)}),
            encoding="utf-8",
        )
        argv = self.model.command("package", output_dir=str(self.out_dir))
        self.assertEqual(argv[-2:], ["--starfield-dir", str(instance_dir.resolve())])

    def test_invalid_step_template_ticks_and_seed_refused(self):
        with self.assertRaisesRegex(ValueError, "Unknown A-Life step"):
            self.model.command("bogus", output_dir=str(self.out_dir))
        with self.assertRaisesRegex(ValueError, "Template"):
            self.model.command("init", output_dir=str(self.out_dir), template="other")
        for bad_ticks in (0, -5, "abc", True):
            with self.assertRaisesRegex(ValueError, "Ticks"):
                self.model.command("simulate", output_dir=str(self.out_dir), ticks=bad_ticks)
        for bad_seed in ("xyz", False):
            with self.assertRaisesRegex(ValueError, "Seed"):
                self.model.command("simulate", output_dir=str(self.out_dir), seed=bad_seed)

    def test_validate_output_dir_refuses_empty_git_repo_and_game_folders(self):
        # Empty path
        self.assertTrue(self.model.validate_output_dir(""))
        self.assertTrue(self.model.validate_output_dir("   "))

        # Git checkout with .git directory
        git_repo = self.root / "repo_dir"
        (git_repo / ".git").mkdir(parents=True)
        reason_git = self.model.validate_output_dir(str(git_repo / "sub" / "out"))
        self.assertIn("Git checkout", reason_git)

        # Git worktree with .git file
        wt = self.root / "worktree_dir"
        wt.mkdir()
        (wt / ".git").write_text("gitdir: ../somewhere\n", encoding="utf-8")
        self.assertIn("Git checkout", self.model.validate_output_dir(str(wt / "dist")))

        # Inside current repo
        self.assertTrue(self.model.validate_output_dir(str(ROOT / "build" / "alife-out")))

        # Inside Starfield game folder (explicit, saved starfield, saved instance, steamapps, Starfield.exe)
        self.assertIn("game", self.model.validate_output_dir(str(self.game_dir / "Data" / "alife")))
        plain_sf = self.root / "MyStarfield"
        plain_sf.mkdir()
        self.assertIn(
            "game",
            self.model.validate_output_dir(str(plain_sf / "out"), starfield_dir=str(plain_sf)),
        )
        steam_out = self.root / "Library" / "steamapps" / "common" / "alife_out"
        self.assertIn("game", self.model.validate_output_dir(str(steam_out)))

        # Saved instance folder refused too
        inst = self.root / "SavedInstance"
        inst.mkdir()
        self.settings_path.write_text(json.dumps({"instance": str(inst)}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "game"):
            self.model.command("init", output_dir=str(inst / "out"))

        # Clean outside folder accepted
        self.assertEqual(self.model.validate_output_dir(str(self.out_dir)), "")

    def test_can_open_output_dir(self):
        ok, msg = self.model.can_open_output_dir("")
        self.assertFalse(ok)
        self.assertIn("Choose", msg)
        ok, msg = self.model.can_open_output_dir(str(self.out_dir))
        self.assertFalse(ok)
        self.assertIn("Init", msg)
        self.out_dir.mkdir()
        ok, path = self.model.can_open_output_dir(str(self.out_dir))
        self.assertTrue(ok)
        self.assertEqual(path, str(self.out_dir.resolve()))

    def test_cross_os_path_basename_and_game_folder_refusal_under_posix(self):
        drv = "D:"
        fake_posix_repo = "/srv/ci_work/fo4sf_checkout"
        real_exists = os.path.exists

        def posix_abspath(p):
            s = str(p)
            return posixpath.normpath(s) if posixpath.isabs(s) else posixpath.normpath(posixpath.join(fake_posix_repo, s))

        def fake_exists(p):
            if str(p) == f"{fake_posix_repo}/.git":
                return True
            return real_exists(p)

        with mock.patch("os.name", "posix"), \
                mock.patch("os.path.abspath", side_effect=posix_abspath), \
                mock.patch("os.path.dirname", side_effect=posixpath.dirname), \
                mock.patch("os.path.basename", side_effect=posixpath.basename), \
                mock.patch("os.path.split", side_effect=posixpath.split), \
                mock.patch("os.path.join", side_effect=posixpath.join), \
                mock.patch("os.path.normcase", side_effect=posixpath.normcase), \
                mock.patch("os.path.commonpath", side_effect=posixpath.commonpath), \
                mock.patch("os.path.exists", side_effect=fake_exists):
            self.assertEqual(alife_tools.path_basename(drv + "\\Games\\Data\\Starfield.esm"), "Starfield.esm")
            self.assertEqual(alife_tools.path_basename(drv + "\\Games/Data\\Starfield.esm"), "Starfield.esm")
            self.assertEqual(alife_tools.path_basename(drv + "\\Games\\Data\\"), "Data")
            self.assertEqual(alife_tools.path_basename(drv + "\\"), "")
            self.assertEqual(alife_tools.path_basename("/opt/starfield/Data/Starfield.esm"), "Starfield.esm")
            self.assertEqual(alife_tools.path_basename("/opt/starfield/Data/"), "Data")
            self.assertEqual(alife_tools.path_basename("\\\\nas\\mods\\Data\\Starfield.esm"), "Starfield.esm")
            self.assertEqual(alife_tools.path_basename("\\\\nas\\mods\\"), "")

            # Foreign Windows/UNC paths on a POSIX runner whose CWD is inside a .git checkout
            # must NOT be mis-anchored under CWD as git-checkout paths:
            self.assertIn(
                "game",
                alife_tools.validate_output_dir(
                    drv + "\\Library\\steamapps\\common\\alife_out",
                    repo_dir=fake_posix_repo,
                ),
            )
            self.assertIn("game", alife_tools.validate_output_dir(drv + "\\XboxGames\\Starfield\\Content\\out"))
            self.assertIn("game", alife_tools.validate_output_dir("/mnt/games/steamapps/common/alife_out"))
            self.assertIn(
                "game",
                alife_tools.validate_output_dir(
                    drv + "\\Games\\Starfield\\Data\\alife",
                    starfield_dir=drv + "\\Games\\Starfield",
                    repo_dir=fake_posix_repo,
                ),
            )
            self.assertIn(
                "game",
                alife_tools.validate_output_dir(
                    drv + "\\Games\\other\\..\\Starfield\\Data\\alife",
                    starfield_dir=drv + "\\Games\\Starfield",
                ),
            )
            self.assertEqual(
                alife_tools.validate_output_dir(
                    drv + "\\Games\\Starfield\\..\\SafeOut",
                    starfield_dir=drv + "\\Games\\Starfield",
                    repo_dir=fake_posix_repo,
                ),
                "",
            )
            self.assertIn(
                "game",
                alife_tools.validate_output_dir(
                    "\\\\nas\\games\\Starfield\\Data\\alife",
                    starfield_dir="\\\\nas\\games\\Starfield",
                    repo_dir=fake_posix_repo,
                ),
            )
            # Local POSIX relative subdir under CWD is still refused as inside the Git checkout:
            self.assertIn("Git checkout", alife_tools.validate_output_dir("build/alife-out"))
            # Foreign Windows repo path is still refused as inside repo_dir:
            self.assertIn(
                "repository",
                alife_tools.validate_output_dir(
                    drv + "\\Repos\\fo4sf\\out",
                    repo_dir=drv + "\\Repos\\fo4sf",
                ),
            )


class StepRunParserTests(unittest.TestCase):
    def test_validate_and_simulate_metrics_and_table_parsing(self):
        v_parser = alife_tools.StepRunParser("validate")
        for line in [
            "A-Life config alife_config.json: Starfield A-Life: New Atlantis -> StarfieldALife.esm (light master)\n",
            "+---------------------+-------------------+\n",
            "| graph               | value             |\n",
            "+---------------------+-------------------+\n",
            "| nodes               | 16/128 (112 free) |\n",
            "| edges               | 24/128 (104 free) |\n",
            "+---------------------+-------------------+\n",
            "validate: ok\n",
        ]:
            v_parser.observe(line)
        v_done = v_parser.finished(0)
        self.assertEqual(v_done["status"], "passed")
        self.assertEqual(v_done["metrics"]["nodes"], "16/128")
        self.assertEqual(v_done["error"], "")

        s_parser = alife_tools.StepRunParser("simulate")
        for line in [
            "A-Life offline simulation: Starfield A-Life: New Atlantis (16 nodes, 24 edges, 3 factions)\n",
            "+----------------------+-------+\n",
            "| metric               | value |\n",
            "+----------------------+-------+\n",
            "| ticks                |   200 |\n",
            "| seed                 |    42 |\n",
            "| squads spawned       |    11 |\n",
            "| edges traversed      |     6 |\n",
            "| offline battles      |     4 |\n",
            "| territory captures   |     2 |\n",
            "+----------------------+-------+\n",
            "+-------------+---------+--------+-------------+----------+\n",
            "| faction     | spawned | losses | nodes owned | captures |\n",
            "+-------------+---------+--------+-------------+----------+\n",
            "| uc_security |       4 |      0 |           5 |        1 |\n",
            "| spacers     |       4 |      3 |           1 |        1 |\n",
            "+-------------+---------+--------+-------------+----------+\n",
        ]:
            s_parser.observe(line)
        s_done = s_parser.finished(0)
        self.assertEqual(
            s_done["metrics"],
            {"nodes": "16/128", "spawns": "11", "battles": "4", "captures": "2"},
        )
        self.assertEqual(s_done["table_columns"], ["faction", "spawned", "losses", "nodes owned", "captures"])
        self.assertEqual(
            s_done["table_rows"],
            [["uc_security", "4", "0", "5", "1"], ["spacers", "4", "3", "1", "1"]],
        )
        self.assertEqual(s_parser.summary_table[0], ["metric", "value"])
        self.assertEqual(len(s_parser.tables), 2)

    def test_error_banner_extraction_never_leaks_tracebacks(self):
        # 1. Refused message
        p1 = alife_tools.StepRunParser("package")
        p1.observe("package refused: --out already exists: package into a new folder\n")
        self.assertEqual(p1.error_banner(2), "Package refused: --out already exists: package into a new folder")

        # 2. FAIL lines
        p2 = alife_tools.StepRunParser("validate")
        p2.observe("FAIL  nodes exceeds 128\n")
        p2.observe("FAIL  graph has 2 components\n")
        p2.observe("validate: 2 problem(s)\n")
        self.assertEqual(p2.error_banner(1), "Validate failed: nodes exceeds 128; graph has 2 components")

        # 3. Traceback stripped to clean banner
        p3 = alife_tools.StepRunParser("simulate")
        for line in [
            "Traceback (most recent call last):\n",
            '  File "scripts/alife/build_alife_mod.py", line 999, in main\n',
            "    boom()\n",
            "RuntimeError: unexpected disk full\n",
        ]:
            p3.observe(line)
        banner = p3.error_banner(1)
        self.assertNotIn("Traceback", banner)
        self.assertNotIn("line 999", banner)
        self.assertIn("unexpected disk full", banner)
        self.assertIn("Log tab", banner)

        # 4. Exit 0 -> empty banner
        self.assertEqual(p3.error_banner(0), "")


class RealPipelineEndToEndTests(unittest.TestCase):
    def test_real_five_step_pipeline_into_temp_dir(self):
        """Runs real scripts/alife/build_alife_mod.py init -> validate -> simulate -> package -> verify-dist
        into a TemporaryDirectory outside Git and outside Starfield using synthetic game/tool shims."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        work = Path(tmp.name)

        # Synthetic Starfield directory with Starfield.esm and Tools/ContentResources.zip
        sf_dir = work / "SyntheticStarfield"
        (sf_dir / "Data").mkdir(parents=True)
        (sf_dir / "Tools" / "Papyrus Compiler").mkdir(parents=True)
        (sf_dir / "Data" / "Starfield.esm").write_bytes(_synthetic_tes4(masters=(), flags=0x1))
        with zipfile.ZipFile(sf_dir / "Tools" / "ContentResources.zip", "w") as zf:
            zf.writestr("Scripts/Source/Starfield_Papyrus_Flags.flg", "// flags\n")
            zf.writestr("Scripts/Source/Quest.psc", "Scriptname Quest Native\n")

        # Cross-platform synthetic dotnet + PapyrusCompiler shims invoked by real build_alife_mod.py
        shims = work / "shims"
        shims.mkdir()
        dotnet_py = shims / "fake_dotnet.py"
        dotnet_py.write_text(
            """import os, struct, sys
args = sys.argv[1:]
idx = args.index('--') + 1
sub = args[idx]
if sub == 'build':
    esm_dir = args[idx + 3]
    def subrec(sig, data):
        return sig + struct.pack('<H', len(data)) + data
    body = subrec(b'HEDR', struct.pack('<fII', 0.96, 12, 0x80C)) + subrec(b'CNAM', b'synth\\0')
    body += subrec(b'MAST', b'Starfield.esm\\0') + subrec(b'DATA', bytes(8))
    tes4 = b'TES4' + struct.pack('<IIIIHH', len(body), 0x101, 0, 0, 0x210, 0) + body
    with open(os.path.join(esm_dir, 'StarfieldALife.esm'), 'wb') as out_fp:
        out_fp.write(tes4)
    print('build: ok')
elif sub == 'check':
    print('check: ok')
""",
            encoding="utf-8",
        )
        compiler_py = shims / "fake_compiler.py"
        compiler_py.write_text(
            """import os, re, sys
psc = sys.argv[1]
out_dir = [a[3:] for a in sys.argv[2:] if a.startswith('-o=')][0]
stem = os.path.splitext(re.split(r'[\\\\/]+', psc.rstrip('\\\\/'))[-1])[0]
os.makedirs(out_dir, exist_ok=True)
with open(os.path.join(out_dir, stem + '.pex'), 'wb') as out_fp:
    out_fp.write(b'\\xde\\xc0\\x57\\xfa' + b'\\x03\\x02\\x01\\x00' + stem.encode())
print('Compilation succeeded.')
""",
            encoding="utf-8",
        )
        fake_dotnet = _make_shim_executable(shims, "dotnet_shim", dotnet_py)
        fake_compiler = _make_shim_executable(shims, "compiler_shim", compiler_py)

        settings_path = work / "settings.json"
        settings_path.write_text(json.dumps({"starfield": str(sf_dir)}), encoding="utf-8")
        out_dir = work / "mod_workspace"

        model = alife_tools.ModToolsModel(str(ROOT / "scripts" / "launcher.py"), str(settings_path))
        statuses = {step: "not_run" for step in alife_tools.STEPS}
        metrics = {}
        sim_result = None

        step_calls = [
            ("init", model.command("init", output_dir=str(out_dir), template="vanilla")),
            ("validate", model.command("validate", output_dir=str(out_dir))),
            ("simulate", model.command("simulate", output_dir=str(out_dir), ticks=25, seed=42)),
            (
                "package",
                model.command("package", output_dir=str(out_dir))
                + ["--dotnet", fake_dotnet, "--compiler", fake_compiler],
            ),
            ("verify-dist", model.command("verify-dist", output_dir=str(out_dir))),
        ]

        for step, argv in step_calls:
            proc = subprocess.run(argv, cwd=str(ROOT), capture_output=True, text=True, errors="replace")
            parser = alife_tools.StepRunParser(step)
            for line in (proc.stdout + proc.stderr).splitlines(keepends=True):
                parser.observe(line)
            done = parser.finished(proc.returncode)
            self.assertEqual(proc.returncode, 0, f"{step} failed:\n{proc.stdout}\n{proc.stderr}")
            self.assertEqual(done["status"], "passed")
            self.assertEqual(done["error"], "")
            statuses[step] = done["status"]
            metrics.update(done["metrics"])
            if step == "simulate":
                sim_result = done

        self.assertEqual(alife_tools.progress(statuses), (5, 5))
        self.assertEqual(metrics.get("nodes"), "16/128")
        self.assertIn("spawns", metrics)
        self.assertIn("battles", metrics)
        self.assertIn("captures", metrics)
        self.assertIsNotNone(sim_result)
        self.assertEqual(sim_result["table_columns"][0], "faction")
        self.assertGreaterEqual(len(sim_result["table_rows"]), 3)
        self.assertTrue((out_dir / "dist" / "manifest.sha256.json").is_file())


if __name__ == "__main__":
    unittest.main()
