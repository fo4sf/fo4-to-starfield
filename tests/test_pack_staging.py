"""Unit tests for D3: scripts/pack_staging.py, --plugin-name / --prefix parameterization on interior_batch.py,
port_promote.py, PluginSpike, and deploy_starfield.py, < 4 GiB BA2 multi-part splitting with companion .esm plugins,
R3 SHA-256 byte-identical defaults, and R4 Git/game output directory refusal."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (
    os.path.join(ROOT, "src"),
    os.path.join(ROOT, "scripts"),
    os.path.join(ROOT, "scripts", "terrain"),
    os.path.join(ROOT, "tests"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import deploy_starfield  # noqa: E402
import interior_batch as ib  # noqa: E402
import pack_staging as ps  # noqa: E402
from pluginspike_fixture import ensure_pluginspike_dll  # noqa: E402
import port_promote  # noqa: E402
import vmad_patch  # noqa: E402


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _pluginspike_dll() -> str:
    return ensure_pluginspike_dll(ROOT)


class PackStagingTests(unittest.TestCase):
    def test_archive_and_companion_naming_and_42_byte_header(self):
        self.assertEqual(ps.normalize_plugin_name("FO4DLC"), ("FO4DLC.esm", "FO4DLC"))
        self.assertEqual(ps.normalize_plugin_name("FO4DLC.esm"), ("FO4DLC.esm", "FO4DLC"))
        self.assertEqual(ps.main_archive_name("FO4DLC.esm"), "FO4DLC - Main.ba2")
        self.assertEqual(ps.textures_archive_name("FO4DLC.esm"), "FO4DLC - Textures.ba2")
        self.assertEqual(ps.part_names(0, "FO4DLC.esm"), ("FO4DLC - Textures.ba2", None))
        self.assertEqual(ps.part_names(1, "FO4DLC.esm"), ("FO4DLCTextures2 - Textures.ba2", "FO4DLCTextures2.esm"))
        self.assertEqual(ps.part_names(2, "FO4DLC.esm"), ("FO4DLCTextures3 - Textures.ba2", "FO4DLCTextures3.esm"))

        with self.assertRaises(ValueError):
            ps.normalize_plugin_name("BadPlugin.esp")
        with self.assertRaises(ValueError):
            ps.normalize_plugin_name("../Escape.esm")

        comp = ps.companion_plugin_bytes()
        self.assertEqual(len(comp), 42)
        self.assertEqual(comp, ib.companion_plugin_bytes())
        self.assertEqual(comp[:4], b"TES4")

    def test_plan_parts_strictly_under_4gib_for_9gb_texture_set(self):
        # 9 synthetic texture files of 1,100 MiB each (~9.67 GiB total) must split into 3 parts, every part strictly
        # below ARCHIVE_WARN * ARCHIVE_LIMIT and strictly below 4 GiB - 1 B (4,294,967,295 B).
        self.assertLess(ps.ARCHIVE_LIMIT, ps.UINT32_MAX)
        self.assertEqual(ps.UINT32_MAX, 4_294_967_295)
        cap = int(ps.ARCHIVE_WARN * ps.ARCHIVE_LIMIT)
        sizes = {f"fo4dlc/set_{i:02d}_color.dds": 1100 * (1 << 20) for i in range(9)}
        parts = ps.plan_parts(sizes, cap)
        self.assertEqual(len(parts), 3)
        for p in parts:
            part_bytes = sum(sizes[r] for r in p)
            self.assertLessEqual(part_bytes, cap)
            self.assertLess(part_bytes, ps.UINT32_MAX)
        self.assertEqual(sorted(r for p in parts for r in p), sorted(sizes))

        # archive_check clamps even an overly large caller limit to UINT32_MAX (< 4 GiB).
        chk = ps.archive_check({"FO4DLC - Textures.ba2": ps.UINT32_MAX}, limit=10 * (1 << 30))
        self.assertFalse(chk["pass"])
        self.assertEqual(chk["limit"], ps.UINT32_MAX)

    def test_pack_staging_splits_companions_replans_and_preserves_prev(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = os.path.join(tmp, "staging")
            sf = os.path.join(tmp, "sf_tools")
            out1 = os.path.join(tmp, "pack1")
            out2 = os.path.join(tmp, "pack2")
            os.makedirs(os.path.join(staging, "meshes", "fo4dlc"))
            os.makedirs(os.path.join(staging, "textures", "fo4dlc"))
            os.makedirs(sf)
            with open(os.path.join(staging, "meshes", "fo4dlc", "a.nif"), "wb") as f:
                f.write(b"NIF" * 10)
            for name in ("a.dds", "b.dds", "c.dds", "d.dds", "e.dds"):
                with open(os.path.join(staging, "textures", "fo4dlc", name), "wb") as f:
                    f.write(b"T" * 40)

            def fake_archive(packer, out_ba2, dirs, fmt):
                total = 0
                for d in dirs:
                    root = os.path.join(packer.staging, d)
                    for base_d, _sub, files in os.walk(root):
                        for fn in files:
                            total += os.path.getsize(os.path.join(base_d, fn))
                os.makedirs(os.path.dirname(out_ba2), exist_ok=True)
                with open(out_ba2, "wb") as h:
                    h.write(b"BTDX" + b"\x00" * max(0, total - 4))

            # Limit = 110 bytes -> warn * limit = 99 bytes -> 5 * 40B textures split into 2+2+1 across 3 parts.
            r1 = ps.pack_staging(
                staging=staging,
                out_dir=out1,
                starfield=sf,
                plugin="FO4DLC.esm",
                limit=110,
                warn=0.9,
                build_archive_fn=fake_archive,
            )
            self.assertTrue(r1["pass"])
            self.assertEqual(
                [p["archive"] for p in r1["parts"]],
                ["FO4DLC - Textures.ba2", "FO4DLCTextures2 - Textures.ba2", "FO4DLCTextures3 - Textures.ba2"],
            )
            self.assertEqual([p["plugin"] for p in r1["parts"]], [None, "FO4DLCTextures2.esm", "FO4DLCTextures3.esm"])
            for comp in ("FO4DLCTextures2.esm", "FO4DLCTextures3.esm"):
                self.assertEqual(os.path.getsize(os.path.join(out1, comp)), 42)
            with open(os.path.join(out1, "FO4DLC.esm"), "wb") as f:
                f.write(ps.companion_plugin_bytes())
            inst = ps.install_set(out1, plugin="FO4DLC.esm")
            self.assertEqual(
                inst["files"],
                [
                    "FO4DLC.esm",
                    "FO4DLC - Main.ba2",
                    "FO4DLC - Textures.ba2",
                    "FO4DLCTextures2.esm",
                    "FO4DLCTextures2 - Textures.ba2",
                    "FO4DLCTextures3.esm",
                    "FO4DLCTextures3 - Textures.ba2",
                ],
            )
            self.assertEqual(inst["plugins_txt"], ["FO4DLC.esm", "FO4DLCTextures2.esm", "FO4DLCTextures3.esm"])

            # Add f.dds and pack into out2 with prev=out1: existing 5 files stay in their exact parts (moved == 0).
            with open(os.path.join(staging, "textures", "fo4dlc", "f.dds"), "wb") as f:
                f.write(b"T" * 40)
            r2 = ps.pack_staging(
                staging=staging,
                out_dir=out2,
                starfield=sf,
                plugin="FO4DLC",
                prev_port=out1,
                prev_result=r1,
                limit=110,
                warn=0.9,
                build_archive_fn=fake_archive,
            )
            self.assertTrue(r2["pass"])
            self.assertEqual(r2["moved"], 0)

    def test_pack_staging_refuses_git_and_game_output_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = os.path.join(tmp, "staging")
            os.makedirs(staging)
            git_repo = os.path.join(tmp, "repo")
            os.makedirs(os.path.join(git_repo, ".git"))
            game_dir = os.path.join(tmp, "Starfield")
            os.makedirs(os.path.join(game_dir, "Data"))
            with open(os.path.join(game_dir, "Starfield.exe"), "wb") as f:
                f.write(b"MZ")

            with self.assertRaises(SystemExit):
                ps.main(["--staging", staging, "--plugin", "FO4DLC.esm", "--out", os.path.join(git_repo, "out"), "--starfield", tmp])
            with self.assertRaises(SystemExit):
                ps.main(["--staging", staging, "--plugin", "FO4DLC.esm", "--out", os.path.join(game_dir, "Data"), "--starfield", tmp])

    def test_port_promote_default_prefix_is_sha256_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            cell_path = os.path.join(tmp, "TestCell01.json")
            containers = os.path.join(tmp, "containers.json")
            items = os.path.join(tmp, "items.json")
            sf_data = os.path.join(tmp, "sf_data")
            os.makedirs(sf_data)
            with open(os.path.join(sf_data, "Starfield.esm"), "wb") as f:
                f.write(ps.companion_plugin_bytes())
            with open(containers, "w", encoding="utf-8") as f:
                json.dump({"default": {"name": None, "items": []}, "by_editor_id": {}}, f)
            with open(items, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "default": {"name": None, "value": 5, "weight": 0.5},
                        "by_editor_id": {"DeskFan*": {"name": "Desk Fan", "value": 12, "weight": 3.0}},
                    },
                    f,
                )
            with open(cell_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "cell": "TestCell01",
                        "refs": [
                            {
                                "formkey": "001000:DLCCoast.esm",
                                "base_formkey": "002000:Fallout4.esm",
                                "type": "MiscItem",
                                "base_editor_id": "DeskFan01",
                                "model": "Props\\DeskFan01.nif",
                                "pos": [0.0, 0.0, 0.0],
                                "rot": [0.0, 0.0, 0.0],
                                "scale": 1.0,
                                "disabled": 0,
                            }
                        ],
                    },
                    f,
                )
            out_default = os.path.join(tmp, "default", "promote.json")
            out_explicit = os.path.join(tmp, "explicit", "promote.json")
            out_dlc = os.path.join(tmp, "dlc", "promote.json")
            os.makedirs(os.path.dirname(out_default))
            os.makedirs(os.path.dirname(out_explicit))
            os.makedirs(os.path.dirname(out_dlc))

            self.assertEqual(
                port_promote.main(
                    ["--out", out_default, "--containers-table", containers, "--items-table", items, "--starfield-data", sf_data, cell_path]
                ),
                0,
            )
            self.assertEqual(
                port_promote.main(
                    [
                        "--out", out_explicit, "--containers-table", containers, "--items-table", items,
                        "--starfield-data", sf_data, "--prefix", "fo4port", cell_path,
                    ]
                ),
                0,
            )
            self.assertEqual(
                port_promote.main(
                    [
                        "--out", out_dlc, "--containers-table", containers, "--items-table", items,
                        "--starfield-data", sf_data, "--prefix", "fo4dlc", cell_path,
                    ]
                ),
                0,
            )
            self.assertEqual(_sha256(out_default), _sha256(out_explicit))
            with open(out_default, encoding="utf-8") as f:
                d_def = json.load(f)
            with open(out_dlc, encoding="utf-8") as f:
                d_dlc = json.load(f)
            self.assertTrue(d_def["items"][0]["edid"].startswith("FO4Port_"))
            self.assertTrue(d_dlc["items"][0]["edid"].startswith("FO4DLC_"))

    def test_pluginspike_default_plugin_and_prefix_are_sha256_byte_identical_and_custom_fo4dlc_works(self):
        dll = _pluginspike_dll()
        with tempfile.TemporaryDirectory() as tmp:
            sf_data = os.path.join(tmp, "sf_data")
            os.makedirs(sf_data)
            env = dict(os.environ, STARFIELD_DATA=sf_data)

            def make_inputs(folder: str, prefix_edid: str, prefix_slug: str):
                os.makedirs(folder, exist_ok=True)
                manifest = os.path.join(folder, "manifest.json")
                cell = os.path.join(folder, "DLC03Acadia.json")
                with open(manifest, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "items": [
                                {
                                    "editor_id": f"{prefix_edid}_Wall01",
                                    "model": f"{prefix_slug}\\dlc03\\wall01.nif",
                                    "source": "DLC03\\Wall01.nif",
                                }
                            ],
                            "failures": [],
                        },
                        f,
                    )
                with open(cell, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "schema_version": 3,
                            "cell": "DLC03Acadia",
                            "cell_name": "Acadia",
                            "location_formkey": "004000:DLCCoast.esm",
                            "location_editor_id": "DLC03AcadiaLocation",
                            "location_name": "Acadia",
                            "refs": [
                                {
                                    "formkey": "004001:DLCCoast.esm",
                                    "base_formkey": "004002:DLCCoast.esm",
                                    "type": "Static",
                                    "base_editor_id": "DLC03Wall01",
                                    "model": "DLC03\\Wall01.nif",
                                    "pos": [70.0, 140.0, 0.0],
                                    "rot": [0.0, 0.0, 0.0],
                                    "scale": 1.0,
                                    "disabled": 0,
                                }
                            ],
                        },
                        f,
                    )
                return manifest, cell

            m_a, c_a = make_inputs(os.path.join(tmp, "in_a"), "FO4Port", "fo4port")
            out_a = os.path.join(tmp, "out_a")
            out_b = os.path.join(tmp, "out_b")
            subprocess.run(["dotnet", dll, out_a, m_a, c_a], check=True, env=env, capture_output=True)
            subprocess.run(
                ["dotnet", dll, out_b, m_a, "--plugin-name", "FO4Port.esm", "--edid-prefix", "FO4Port", c_a],
                check=True,
                env=env,
                capture_output=True,
            )
            self.assertEqual(_sha256(os.path.join(out_a, "FO4Port.esm")), _sha256(os.path.join(out_b, "FO4Port.esm")))
            self.assertEqual(_sha256(os.path.join(out_a, "formids.json")), _sha256(os.path.join(out_b, "formids.json")))

            m_c, c_c = make_inputs(os.path.join(tmp, "in_c"), "FO4DLC", "fo4dlc")
            out_c = os.path.join(tmp, "out_c")
            subprocess.run(
                ["dotnet", dll, out_c, m_c, "--plugin-name", "FO4DLC.esm", "--edid-prefix", "FO4DLC", c_c],
                check=True,
                env=env,
                capture_output=True,
            )
            self.assertTrue(os.path.isfile(os.path.join(out_c, "FO4DLC.esm")))
            with open(os.path.join(out_c, "formids.json"), encoding="utf-8") as f:
                fids_c = json.load(f)
            self.assertIn("CELL:FO4DLC_DLC03Acadia", fids_c)
            self.assertIn("LCTN:FO4DLC_InteriorsLocation", fids_c)
            self.assertIn("LCTN:FO4DLC_DLC03AcadiaLocation", fids_c)
            self.assertIn("STAT:FO4DLC_Wall01", fids_c)
            plug = vmad_patch.Plugin.read(os.path.join(out_c, "FO4DLC.esm"))
            self.assertEqual(plug.masters(), ["Starfield.esm"])

    def test_deploy_starfield_installs_and_uninstalls_custom_plugin_batch_without_touching_fo4port(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = os.path.join(tmp, "game")
            os.makedirs(os.path.join(game, "Data"))
            plugins_txt = os.path.join(tmp, "Plugins.txt")
            with open(plugins_txt, "w", encoding="utf-8") as f:
                f.write("*FO4Port.esm\n")
            with open(os.path.join(game, "Data", "FO4Port.esm"), "wb") as f:
                f.write(ps.companion_plugin_bytes())

            stage = os.path.join(tmp, "fo4dlc-stage")
            port = os.path.join(stage, "port")
            os.makedirs(port)
            esm_bytes = ps.companion_plugin_bytes()
            files_map = {
                "FO4DLC.esm": esm_bytes,
                "FO4DLC - Main.ba2": b"BTDX" + b"main" * 8,
                "FO4DLC - Textures.ba2": b"BTDX" + b"tex1" * 8,
                "FO4DLCTextures2.esm": esm_bytes,
                "FO4DLCTextures2 - Textures.ba2": b"BTDX" + b"tex2" * 8,
            }
            for fname, body in files_map.items():
                with open(os.path.join(port, fname), "wb") as f:
                    f.write(body)
            with open(os.path.join(stage, "result.json"), "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "pass": True,
                        "installed": False,
                        "plugin_name": "FO4DLC.esm",
                        "prefix": "fo4dlc",
                        "pins": {"plugin": hashlib.sha256(esm_bytes).hexdigest()},
                        "install": {
                            "files": list(files_map),
                            "plugins_txt": ["FO4DLC.esm", "FO4DLCTextures2.esm"],
                        },
                        "steps": {
                            "pack": {
                                "sha256": {
                                    k: hashlib.sha256(v).hexdigest() for k, v in files_map.items() if k != "FO4DLC.esm"
                                }
                            }
                        },
                    },
                    f,
                )

            with patch.object(deploy_starfield, "plugins_txt_path", return_value=plugins_txt):
                deploy_starfield.install(
                    SimpleNamespace(
                        action="install",
                        staging="",
                        batch=stage,
                        starfield=game,
                        min_free_gb=0.0,
                        dry_run=False,
                        other_core=False,
                        plugin_name="",
                    )
                )
            self.assertTrue(os.path.isfile(os.path.join(game, "Data", "FO4DLC.deploy.json")))
            self.assertTrue(os.path.isfile(os.path.join(game, "Data", "FO4DLCTextures2 - Textures.ba2")))
            with open(plugins_txt, encoding="utf-8") as f:
                lines = [ln.strip() for ln in f if ln.strip()]
            self.assertEqual(lines, ["*FO4Port.esm", "*FO4DLC.esm", "*FO4DLCTextures2.esm"])

            with patch.object(deploy_starfield, "plugins_txt_path", return_value=plugins_txt):
                deploy_starfield.uninstall(
                    SimpleNamespace(
                        action="uninstall",
                        staging="",
                        batch="",
                        starfield=game,
                        dry_run=False,
                        plugin_name="FO4DLC.esm",
                    )
                )
            self.assertFalse(os.path.exists(os.path.join(game, "Data", "FO4DLC.esm")))
            self.assertFalse(os.path.exists(os.path.join(game, "Data", "FO4DLCTextures2.esm")))
            self.assertTrue(os.path.isfile(os.path.join(game, "Data", "FO4Port.esm")))
            with open(plugins_txt, encoding="utf-8") as f:
                lines_after = [ln.strip() for ln in f if ln.strip()]
            self.assertEqual(lines_after, ["*FO4Port.esm"])

    def test_interior_batch_default_plugin_and_prefix_are_sha256_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = os.path.join(tmp, "work")
            os.makedirs(os.path.join(work, "meshes", "fo4port"))
            os.makedirs(os.path.join(work, "textures", "fo4port"))
            with open(os.path.join(work, "meshes", "fo4port", "m.nif"), "wb") as f:
                f.write(b"NIFDATA")
            with open(os.path.join(work, "textures", "fo4port", "t.dds"), "wb") as f:
                f.write(b"DDSDATA")

            plan = os.path.join(tmp, "plan.json")
            with open(plan, "w", encoding="utf-8") as f:
                json.dump({"batches": []}, f)
            base = os.path.join(tmp, "base")
            core = os.path.join(tmp, "core")
            os.makedirs(base)
            os.makedirs(core)
            with open(os.path.join(base, "FO4Port.esm"), "wb") as f:
                f.write(ps.companion_plugin_bytes())
            with open(os.path.join(base, "formids.json"), "w", encoding="utf-8") as f:
                json.dump({}, f)

            orig_build = ib.deploy_starfield.build_archive

            def fake_archive(packer, out_ba2, dirs, fmt):
                os.makedirs(os.path.dirname(out_ba2), exist_ok=True)
                with open(out_ba2, "wb") as h:
                    h.write(b"BTDX:" + fmt.encode("ascii") + b":" + ",".join(dirs).encode("ascii"))

            ib.deploy_starfield.build_archive = fake_archive
            try:
                def run_one(sub_name: str, plugin_arg: str, prefix_arg: str, target_esm: str):
                    out = os.path.join(tmp, sub_name)
                    port = os.path.join(out, "port")
                    os.makedirs(port)
                    with open(os.path.join(port, target_esm), "wb") as h:
                        h.write(ps.companion_plugin_bytes())
                    ns = ib.argparse.Namespace(
                        batch=1,
                        out=out,
                        work=work,
                        starfield=tmp,
                        base=base,
                        core=core,
                        plan=plan,
                        plugin_name=plugin_arg,
                        prefix=prefix_arg,
                        animated_doors=False,
                        pack_ratio=None,
                    )
                    log = os.path.join(out, "build.log")
                    pack_res = ib.pack(ns, port, None, None, log)
                    ib.finish(ns, {}, {"pack": pack_res}, {"CellA": {"result": "converted"}}, 0.0, None)
                    return out

                out_def = run_one("interiors_b01", "", "", "FO4Port.esm")
                out_exp = run_one("interiors_b01_exp", "FO4Port.esm", "fo4port", "FO4Port.esm")
                out_dlc = run_one("fo4dlc_stage", "FO4DLC.esm", "fo4dlc", "FO4DLC.esm")
            finally:
                ib.deploy_starfield.build_archive = orig_build

            for rel in ("README.txt", "port/FO4Port - Main.ba2", "port/FO4Port - Textures.ba2", "port/textures_parts.json"):
                self.assertEqual(_sha256(os.path.join(out_def, *rel.split("/"))), _sha256(os.path.join(out_exp, *rel.split("/"))))
            with open(os.path.join(out_def, "result.json"), encoding="utf-8") as f:
                r_def = json.load(f)
            self.assertNotIn("plugin_name", r_def)
            self.assertEqual(r_def["install"]["files"], ["FO4Port.esm", "FO4Port - Main.ba2", "FO4Port - Textures.ba2"])

            with open(os.path.join(out_dlc, "result.json"), encoding="utf-8") as f:
                r_dlc = json.load(f)
            self.assertEqual(r_dlc["plugin_name"], "FO4DLC.esm")
            self.assertEqual(r_dlc["prefix"], "fo4dlc")
            self.assertEqual(r_dlc["install"]["files"], ["FO4DLC.esm", "FO4DLC - Main.ba2", "FO4DLC - Textures.ba2"])


if __name__ == "__main__":
    unittest.main()
