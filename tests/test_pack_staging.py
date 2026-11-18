"""Unit tests for D3, D2 (R12 pinned cd03411a parity), and D5 (deploy_starfield --plugin-name safety):
scripts/pack_staging.py, --plugin-name / --prefix parameterization on interior_batch.py, port_promote.py, PluginSpike,
and deploy_starfield.py, < 4 GiB BA2 multi-part splitting with companion .esm plugins, R12 SHA-256 parity against
cd03411a constants, and R4 Git/game output directory refusal."""
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

# Pinned SHA-256 parity digests produced by commit cd03411a on the synthetic fixtures below (Rule R12).
CD03411A_COMPANION_PLUGIN_SHA256 = "40d450026d1fbf370e75d3957433003355926c026306d87f07f576f5c6a38a83"
CD03411A_PORT_PROMOTE_SHA256 = "a1dfb4fbdea8c4b4c25a363eb4956e2af60f55bd7674a5e9174ecfc8657e6c9d"
CD03411A_PLUGINSPIKE_DEFAULT_ESM_SHA256 = "f34e194183c273d217bbb16dba5e3e42345ac7cb0e25f8100427738342bbe418"
CD03411A_PLUGINSPIKE_DEFAULT_FORMIDS_SHA256 = "08a8150be056c334a85461b9973c04ac7bed63d9364eacbde772933388ba62ca"
CD03411A_PACK_MULTIPART_MAIN_BA2_SHA256 = "d2cb357494618b04021897f3b7672aaf66d895ce118a303d0bb8fc782f64bf8f"
CD03411A_PACK_MULTIPART_TEX1_BA2_SHA256 = "4744d0add3f27685b58f3c962aaaed7e264db7a330e270fa1be9d9191018a9d5"
CD03411A_PACK_MULTIPART_TEX2_ESM_SHA256 = "40d450026d1fbf370e75d3957433003355926c026306d87f07f576f5c6a38a83"
CD03411A_PACK_MULTIPART_TEX2_BA2_SHA256 = "4744d0add3f27685b58f3c962aaaed7e264db7a330e270fa1be9d9191018a9d5"
CD03411A_PACK_MULTIPART_TEX3_ESM_SHA256 = "40d450026d1fbf370e75d3957433003355926c026306d87f07f576f5c6a38a83"
CD03411A_PACK_MULTIPART_TEX3_BA2_SHA256 = "dd4c63e712e1b3f78c9fec98ccfdd612c3b118a5c755d3ec72757e2c1d50db80"
CD03411A_PACK_MULTIPART_PARTS_JSON_SHA256 = "c85bdf7dd3ac9c2285426592ff34e3bc73fad843cc8cb4c9ac058b4494edafe9"
CD03411A_IB_FINISH_README_SHA256 = "592c24c1709546b4dcadeaadd1120c15ebd01cd325978ea498fd74833a939d49"
CD03411A_IB_FINISH_MAIN_BA2_SHA256 = "4283a3ebda9787dc0338d4d0e5fd67364ea12d7fb5c334e3bcfeaed30f4c9fa0"
CD03411A_IB_FINISH_TEX_BA2_SHA256 = "2799a35d3077acfb6c9f4d02909b4a1f4eb8d8c29bce8be43ad38018fd9d6810"
CD03411A_IB_FINISH_PARTS_JSON_SHA256 = "0ff666e651a31501dc2d4dd346bbf8f250644d64ffd56b34c9c68f6da5f536ea"


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_text(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()


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
        self.assertEqual(hashlib.sha256(comp).hexdigest(), CD03411A_COMPANION_PLUGIN_SHA256)
        self.assertEqual(hashlib.sha256(ib.companion_plugin_bytes()).hexdigest(), CD03411A_COMPANION_PLUGIN_SHA256)
        self.assertEqual(comp[:4], b"TES4")

    def test_plan_parts_strictly_under_4gib_for_9gb_texture_set(self):
        # 9 synthetic texture files of 1,100 MiB each (~9.67 GiB total) must split into 3 parts, every part strictly
        # below ARCHIVE_WARN * ARCHIVE_LIMIT and strictly below 4 GiB - 1 B (4,294,967_295 B).
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

    def test_pack_staging_default_fo4port_multipart_matches_cd03411a(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = os.path.join(tmp, "staging")
            sf = os.path.join(tmp, "sf_tools")
            out_omitted = os.path.join(tmp, "pack_omitted")
            out_explicit = os.path.join(tmp, "pack_explicit")
            os.makedirs(os.path.join(staging, "meshes", "fo4port"))
            os.makedirs(os.path.join(staging, "textures", "fo4port"))
            os.makedirs(sf)
            with open(os.path.join(staging, "meshes", "fo4port", "a.nif"), "wb") as f:
                f.write(b"NIF" * 10)
            for name in ("a.dds", "b.dds", "c.dds", "d.dds", "e.dds"):
                with open(os.path.join(staging, "textures", "fo4port", name), "wb") as f:
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

            ps.pack_staging(
                staging=staging, out_dir=out_omitted, starfield=sf,
                limit=110, warn=0.9, build_archive_fn=fake_archive,
            )
            ps.pack_staging(
                staging=staging, out_dir=out_explicit, starfield=sf, plugin="FO4Port.esm",
                limit=110, warn=0.9, build_archive_fn=fake_archive,
            )
            for out_dir in (out_omitted, out_explicit):
                self.assertEqual(_sha256(os.path.join(out_dir, "FO4Port - Main.ba2")), CD03411A_PACK_MULTIPART_MAIN_BA2_SHA256)
                self.assertEqual(_sha256(os.path.join(out_dir, "FO4Port - Textures.ba2")), CD03411A_PACK_MULTIPART_TEX1_BA2_SHA256)
                self.assertEqual(_sha256(os.path.join(out_dir, "FO4PortTextures2.esm")), CD03411A_PACK_MULTIPART_TEX2_ESM_SHA256)
                self.assertEqual(_sha256(os.path.join(out_dir, "FO4PortTextures2 - Textures.ba2")), CD03411A_PACK_MULTIPART_TEX2_BA2_SHA256)
                self.assertEqual(_sha256(os.path.join(out_dir, "FO4PortTextures3.esm")), CD03411A_PACK_MULTIPART_TEX3_ESM_SHA256)
                self.assertEqual(_sha256(os.path.join(out_dir, "FO4PortTextures3 - Textures.ba2")), CD03411A_PACK_MULTIPART_TEX3_BA2_SHA256)
                self.assertEqual(_sha256_text(os.path.join(out_dir, "textures_parts.json")), CD03411A_PACK_MULTIPART_PARTS_JSON_SHA256)

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

    def test_port_promote_default_prefix_matches_cd03411a(self):
        with tempfile.TemporaryDirectory() as tmp:
            cell_path = os.path.join(tmp, "TestCell01.json")
            containers = os.path.join(tmp, "containers.json")
            items = os.path.join(tmp, "items.json")
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
                    ["--out", out_default, "--containers-table", containers, "--items-table", items, cell_path]
                ),
                0,
            )
            self.assertEqual(
                port_promote.main(
                    [
                        "--out", out_explicit, "--containers-table", containers, "--items-table", items,
                        "--prefix", "fo4port", cell_path,
                    ]
                ),
                0,
            )
            self.assertEqual(
                port_promote.main(
                    [
                        "--out", out_dlc, "--containers-table", containers, "--items-table", items,
                        "--prefix", "fo4dlc", cell_path,
                    ]
                ),
                0,
            )
            self.assertEqual(_sha256_text(out_default), CD03411A_PORT_PROMOTE_SHA256)
            self.assertEqual(_sha256_text(out_explicit), CD03411A_PORT_PROMOTE_SHA256)
            with open(out_default, encoding="utf-8") as f:
                d_def = json.load(f)
            with open(out_dlc, encoding="utf-8") as f:
                d_dlc = json.load(f)
            self.assertTrue(d_def["items"][0]["edid"].startswith("FO4Port_"))
            self.assertTrue(d_dlc["items"][0]["edid"].startswith("FO4DLC_"))

    def test_pluginspike_default_plugin_and_prefix_match_cd03411a_and_custom_fo4dlc_works(self):
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
            self.assertEqual(_sha256(os.path.join(out_a, "FO4Port.esm")), CD03411A_PLUGINSPIKE_DEFAULT_ESM_SHA256)
            self.assertEqual(_sha256(os.path.join(out_b, "FO4Port.esm")), CD03411A_PLUGINSPIKE_DEFAULT_ESM_SHA256)
            self.assertEqual(_sha256_text(os.path.join(out_a, "formids.json")), CD03411A_PLUGINSPIKE_DEFAULT_FORMIDS_SHA256)
            self.assertEqual(_sha256_text(os.path.join(out_b, "formids.json")), CD03411A_PLUGINSPIKE_DEFAULT_FORMIDS_SHA256)

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

    def _make_batch_stage(self, root: str, folder: str, plugin_esm: str | None):
        """Create a synthetic batch stage; when `plugin_esm` is None, omit `plugin_name` in result.json (default FO4Port)."""
        stage = os.path.join(root, folder)
        port = os.path.join(stage, "port")
        os.makedirs(port)
        actual_esm = plugin_esm or "FO4Port.esm"
        stem = actual_esm[:-4]
        esm_bytes = ps.companion_plugin_bytes()
        files_map = {
            actual_esm: esm_bytes,
            f"{stem} - Main.ba2": b"BTDX" + b"main" * 8,
            f"{stem} - Textures.ba2": b"BTDX" + b"tex1" * 8,
            f"{stem}Textures2.esm": esm_bytes,
            f"{stem}Textures2 - Textures.ba2": b"BTDX" + b"tex2" * 8,
        }
        for fname, body in files_map.items():
            with open(os.path.join(port, fname), "wb") as f:
                f.write(body)
        result_doc = {
            "batch": 1,
            "pass": True,
            "installed": False,
            "pins": {"plugin": hashlib.sha256(esm_bytes).hexdigest(), "core_plugin": hashlib.sha256(esm_bytes).hexdigest()},
            "install": {
                "files": list(files_map),
                "plugins_txt": [actual_esm, f"{stem}Textures2.esm"],
            },
            "steps": {
                "pack": {
                    "sha256": {
                        k: hashlib.sha256(v).hexdigest() for k, v in files_map.items() if k != actual_esm
                    }
                }
            },
        }
        if plugin_esm is not None:
            result_doc["plugin_name"] = plugin_esm
            result_doc["prefix"] = stem.lower()
            result_doc["core"] = None
        with open(os.path.join(stage, "result.json"), "w", encoding="utf-8") as f:
            json.dump(result_doc, f)
        return stage, files_map

    def test_deploy_starfield_installs_and_uninstalls_custom_plugin_batch_without_touching_fo4port(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = os.path.join(tmp, "game")
            os.makedirs(os.path.join(game, "Data"))
            plugins_txt = os.path.join(tmp, "Plugins.txt")
            with open(plugins_txt, "w", encoding="utf-8") as f:
                f.write("*FO4Port.esm\n")
            with open(os.path.join(game, "Data", "FO4Port.esm"), "wb") as f:
                f.write(ps.companion_plugin_bytes())

            stage, _files_map = self._make_batch_stage(tmp, "fo4dlc-stage", "FO4DLC.esm")

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
                        plugin_name="fo4dlc",  # case-insensitive match records canonical FO4DLC.esm
                    )
                )
            man_path = os.path.join(game, "Data", "FO4DLC.deploy.json")
            self.assertTrue(os.path.isfile(man_path))
            with open(man_path, encoding="utf-8") as f:
                man_doc = json.load(f)
            self.assertEqual(man_doc["plugin_name"], "FO4DLC.esm")
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

    def test_deploy_starfield_install_batch_refuses_plugin_name_mismatch_on_explicit_and_default_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = os.path.join(tmp, "game")
            os.makedirs(os.path.join(game, "Data"))
            plugins_txt = os.path.join(tmp, "Plugins.txt")
            with open(plugins_txt, "w", encoding="utf-8") as f:
                f.write("*Starfield.esm\n")

            dlc_stage, _ = self._make_batch_stage(tmp, "fo4dlc-stage", "FO4DLC.esm")
            port_stage, _ = self._make_batch_stage(tmp, "fo4port-stage", None)

            # 1a. Explicit FO4DLC.esm stage refused when --plugin-name asks for FO4Port.esm (naming both).
            with patch.object(deploy_starfield, "plugins_txt_path", return_value=plugins_txt):
                with self.assertRaisesRegex(SystemExit, r"FO4Port\.esm.*FO4DLC\.esm"):
                    deploy_starfield.install(
                        SimpleNamespace(
                            action="install", staging="", batch=dlc_stage, starfield=game,
                            min_free_gb=0.0, dry_run=False, other_core=False, plugin_name="FO4Port.esm",
                        )
                    )
            self.assertEqual(os.listdir(os.path.join(game, "Data")), [])

            # 1b. Default FO4Port.esm stage (no plugin_name in result.json) refused when --plugin-name asks for FO4DLC.esm.
            with patch.object(deploy_starfield, "plugins_txt_path", return_value=plugins_txt):
                with self.assertRaisesRegex(SystemExit, r"FO4DLC\.esm.*FO4Port\.esm"):
                    deploy_starfield.install(
                        SimpleNamespace(
                            action="install", staging="", batch=port_stage, starfield=game,
                            min_free_gb=0.0, dry_run=False, other_core=False, plugin_name="FO4DLC.esm",
                        )
                    )
            self.assertEqual(os.listdir(os.path.join(game, "Data")), [])

    def test_deploy_starfield_uninstall_refuses_manifest_plugin_name_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = os.path.join(tmp, "game")
            data = os.path.join(game, "Data")
            os.makedirs(data)
            plugins_txt = os.path.join(tmp, "Plugins.txt")
            with open(plugins_txt, "w", encoding="utf-8") as f:
                f.write("*FO4DLC.esm\n")

            # FO4DLC.deploy.json whose recorded plugin_name says FO4Other.esm must refuse uninstall --plugin-name FO4DLC.esm.
            dlc_man = os.path.join(data, "FO4DLC.deploy.json")
            deploy_starfield.write_manifest(
                dlc_man,
                {
                    "plugin_name": "FO4Other.esm",
                    "files": [],
                    "published_files": [],
                    "plugins_txt": plugins_txt,
                    "plugins_added": ["*FO4DLC.esm"],
                    "plugins_replaced": [],
                    "complete": True,
                    "artifacts": {},
                },
            )
            with patch.object(deploy_starfield, "plugins_txt_path", return_value=plugins_txt):
                with self.assertRaisesRegex(SystemExit, r"FO4Other\.esm.*FO4DLC\.esm"):
                    deploy_starfield.uninstall(
                        SimpleNamespace(action="uninstall", starfield=game, dry_run=False, plugin_name="FO4DLC.esm")
                    )
            self.assertTrue(os.path.isfile(dlc_man))

            # FO4Port.deploy.json tampered to say FO4DLC.esm must refuse default uninstall (FO4Port.esm).
            port_man = os.path.join(data, "FO4Port.deploy.json")
            deploy_starfield.write_manifest(
                port_man,
                {
                    "plugin_name": "FO4DLC.esm",
                    "files": [],
                    "published_files": [],
                    "plugins_txt": plugins_txt,
                    "plugins_added": [],
                    "plugins_replaced": [],
                    "complete": True,
                    "artifacts": {},
                },
            )
            with patch.object(deploy_starfield, "plugins_txt_path", return_value=plugins_txt):
                with self.assertRaisesRegex(SystemExit, r"FO4DLC\.esm.*FO4Port\.esm"):
                    deploy_starfield.uninstall(
                        SimpleNamespace(action="uninstall", starfield=game, dry_run=False, plugin_name="")
                    )
            self.assertTrue(os.path.isfile(port_man))

    def test_deploy_starfield_uninstall_treats_old_format_manifest_without_plugin_name_as_fo4port(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = os.path.join(tmp, "game")
            data = os.path.join(game, "Data")
            os.makedirs(data)
            plugins_txt = os.path.join(tmp, "Plugins.txt")
            with open(plugins_txt, "w", encoding="utf-8") as f:
                f.write("*Starfield.esm\n*FO4Port.esm\n")

            esm_path = os.path.join(data, "FO4Port.esm")
            with open(esm_path, "wb") as f:
                f.write(ps.companion_plugin_bytes())
            old_record = {
                # Deliberately no "plugin_name" key: mirrors the pre-D3 FO4Port.deploy.json format.
                "files": ["FO4Port.esm"],
                "published_files": ["FO4Port.esm"],
                "plugins_txt": plugins_txt,
                "plugins_added": ["*FO4Port.esm"],
                "plugins_replaced": [],
                "complete": True,
                "artifacts": {"FO4Port.esm": deploy_starfield.artifact_identity(esm_path)},
            }

            # If an old-format record without plugin_name sits at FO4DLC.deploy.json, uninstall --plugin-name FO4DLC.esm
            # reads it as FO4Port.esm and refuses cleanup!
            wrong_man = os.path.join(data, "FO4DLC.deploy.json")
            deploy_starfield.write_manifest(wrong_man, dict(old_record))
            with patch.object(deploy_starfield, "plugins_txt_path", return_value=plugins_txt):
                with self.assertRaisesRegex(SystemExit, r"FO4Port\.esm.*FO4DLC\.esm"):
                    deploy_starfield.uninstall(
                        SimpleNamespace(action="uninstall", starfield=game, dry_run=False, plugin_name="FO4DLC.esm")
                    )
            self.assertTrue(os.path.isfile(wrong_man))
            self.assertTrue(os.path.isfile(esm_path))

            # At FO4Port.deploy.json, default uninstall (and --plugin-name FO4Port.esm) succeeds cleanly.
            port_man = os.path.join(data, "FO4Port.deploy.json")
            deploy_starfield.write_manifest(port_man, dict(old_record))
            with patch.object(deploy_starfield, "plugins_txt_path", return_value=plugins_txt):
                deploy_starfield.uninstall(
                    SimpleNamespace(action="uninstall", starfield=game, dry_run=False, plugin_name="")
                )
            self.assertFalse(os.path.exists(port_man))
            self.assertFalse(os.path.exists(esm_path))
            with open(plugins_txt, encoding="utf-8") as f:
                self.assertEqual([ln.strip() for ln in f if ln.strip()], ["*Starfield.esm"])

    def test_interior_batch_default_plugin_and_prefix_match_cd03411a(self):
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

            for out_dir in (out_def, out_exp):
                self.assertEqual(_sha256_text(os.path.join(out_dir, "README.txt")), CD03411A_IB_FINISH_README_SHA256)
                self.assertEqual(_sha256(os.path.join(out_dir, "port", "FO4Port - Main.ba2")), CD03411A_IB_FINISH_MAIN_BA2_SHA256)
                self.assertEqual(_sha256(os.path.join(out_dir, "port", "FO4Port - Textures.ba2")), CD03411A_IB_FINISH_TEX_BA2_SHA256)
                self.assertEqual(_sha256_text(os.path.join(out_dir, "port", "textures_parts.json")), CD03411A_IB_FINISH_PARTS_JSON_SHA256)

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
