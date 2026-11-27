"""Tests for Codsworth / Handy chrome PBR materials, _s.dds conversion, and HandyLens.BGEM."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
for _p in (str(REPO / "src"), str(REPO / "scripts" / "actors"), str(REPO / "scripts" / "mission"), str(REPO / "scripts" / "probes")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fo4sf import convert_material as cm, nif, sfnif  # noqa: E402
import convert_codsworth as cc  # noqa: E402
import convert_handy as ch  # noqa: E402
import make_mission as mm  # noqa: E402


def _load_test_actor_rebind():
    spec = importlib.util.spec_from_file_location("test_actor_rebind", REPO / "tests" / "test_actor_rebind.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def inspect_actor_mat_pbr(mat: dict) -> str | None:
    """Return an error string if `mat` sets Metalness > 0.5 with Roughness < 0.4 and no roughness texture."""
    layer = (mat.get("Summary") or {}).get("Layer1") or {}
    tex = layer.get("Textures") or {}

    metalness = 0.0
    m_info = tex.get("Metalness") or {}
    if m_info.get("UseReplacement"):
        metalness = float((m_info.get("Replacement") or {}).get("x", 0.0))

    rough_file = ""
    r_info = tex.get("Roughness") or {}
    if isinstance(r_info.get("File"), str):
        rough_file = r_info["File"].strip()
    rough_use_repl = bool(r_info.get("UseReplacement", False))
    rough_val = float((r_info.get("Replacement") or {}).get("x", 1.0)) if rough_use_repl else 1.0

    for obj in mat.get("Objects") or []:
        for c in obj.get("Components") or []:
            ctype = c.get("Type")
            cidx = c.get("Index")
            data = c.get("Data") or {}
            if ctype == "BSMaterial::MRTextureFile" and cidx == 3:
                fn = data.get("FileName") or ""
                if isinstance(fn, str) and fn.strip():
                    rough_file = fn.strip()
            elif ctype == "BSMaterial::TextureReplacement" and cidx == 4:
                if str(data.get("Enabled", "")).lower() == "true":
                    val = (((data.get("Color") or {}).get("Data") or {}).get("Value") or {}).get("Data") or {}
                    metalness = max(metalness, float(val.get("x", 0.0)))
            elif ctype == "BSMaterial::TextureReplacement" and cidx == 3:
                if str(data.get("Enabled", "")).lower() == "true":
                    val = (((data.get("Color") or {}).get("Data") or {}).get("Value") or {}).get("Data") or {}
                    rough_val = min(rough_val, float(val.get("x", 1.0)))
                    rough_use_repl = True

    has_rough_tex = bool(rough_file) and not rough_use_repl
    if metalness > 0.5 and not has_rough_tex and rough_val < 0.4:
        return f"Metalness={metalness} > 0.5 with Roughness={rough_val} < 0.4 and no active roughness texture"
    return None


def _sample_mat(with_rough_tex: bool = True) -> dict:
    from test_materials import mini_template

    t = mini_template()
    t["Objects"][1]["Components"].append(
        {"Type": "BSMaterial::MRTextureFile", "Index": 0, "Data": {"FileName": "Data\\textures\\x_color.dds"}}
    )
    t["Objects"][1]["Components"].append(
        {"Type": "BSMaterial::MRTextureFile", "Index": 1, "Data": {"FileName": "Data\\textures\\x_normal.dds"}}
    )
    if with_rough_tex:
        t["Objects"][1]["Components"].append(
            {"Type": "BSMaterial::MRTextureFile", "Index": 3, "Data": {"FileName": "Data\\textures\\x_rough.dds"}}
        )
    else:
        t["Summary"]["Layer1"]["Textures"]["Roughness"]["File"] = ""
    return cm.build_mat(
        t,
        "FO4Port_HandyTest",
        "Data\\textures\\x_color.dds",
        "Data\\textures\\x_normal.dds",
        "Data\\textures\\x_rough.dds" if with_rough_tex else "",
    )


class CodsworthChromeMatTests(unittest.TestCase):
    def test_checker_catches_untextured_shiny_metal_negative_control(self) -> None:
        bad = _sample_mat(with_rough_tex=False)
        bad["Summary"]["Layer1"]["Textures"]["Metalness"] = {
            "File": "",
            "Replacement": {"w": 1, "x": 0.85, "y": 0.85, "z": 0.85},
            "UseReplacement": True,
        }
        bad["Summary"]["Layer1"]["Textures"]["Roughness"] = {
            "File": "",
            "Replacement": {"w": 1, "x": 0.22, "y": 0.22, "z": 0.22},
            "UseReplacement": True,
        }
        err = inspect_actor_mat_pbr(bad)
        self.assertIsNotNone(err)
        self.assertIn("Metalness=0.85", err)

    def test_patch_codsworth_steel_mat_preserves_roughness_texture(self) -> None:
        mat = _sample_mat(with_rough_tex=True)
        patched = cc.patch_codsworth_steel_mat(mat)
        self.assertIsNone(inspect_actor_mat_pbr(patched))
        r_info = patched["Summary"]["Layer1"]["Textures"]["Roughness"]
        self.assertEqual(r_info["File"], "Data\\textures\\x_rough.dds")
        self.assertFalse(r_info["UseReplacement"])
        m_info = patched["Summary"]["Layer1"]["Textures"]["Metalness"]
        self.assertEqual(m_info["Replacement"]["x"], cc.CODSWORTH_METALNESS)
        mr3 = [
            c for o in patched["Objects"] for c in o.get("Components", [])
            if c.get("Type") == "BSMaterial::MRTextureFile" and c.get("Index") == 3
        ]
        self.assertEqual(len(mr3), 1)

    def test_patch_codsworth_steel_mat_fallback_without_roughness_texture_is_safe(self) -> None:
        mat = _sample_mat(with_rough_tex=False)
        patched = cc.patch_codsworth_steel_mat(mat)
        self.assertIsNone(inspect_actor_mat_pbr(patched))
        r_info = patched["Summary"]["Layer1"]["Textures"]["Roughness"]
        self.assertGreaterEqual(r_info["Replacement"]["x"], 0.4)

    def test_repo_has_no_untextured_shiny_actor_mats(self) -> None:
        for mat_path in sorted(REPO.rglob("*.mat")):
            rel = mat_path.relative_to(REPO).as_posix()
            if ".claude/" in rel or ".git/" in rel:
                continue
            mat = json.loads(mat_path.read_text(encoding="utf-8"))
            self.assertIsNone(inspect_actor_mat_pbr(mat), f"{rel} failed PBR check")

    def test_build_resolves_s_dds_and_generates_handylens_mat(self) -> None:
        tar = _load_test_actor_rebind()
        fo4 = tar.skinned_nif()
        # Add BSShaderTextureSet to the test shape so _shape_texture_paths extracts diffuse/normal with empty spec
        ts_payload = struct.pack("<I", 8)
        for slot in (
            b"textures\\actors\\handy\\HandyTorso_d.dds\x00",
            b"textures\\actors\\handy\\HandyTorso_n.dds\x00",
            b"\x00", b"\x00", b"\x00", b"\x00", b"\x00", b"\x00",
        ):
            ts_payload += struct.pack("<I", len(slot)) + slot
        ts_idx = fo4.add_block("BSShaderTextureSet", ts_payload)
        # BSLightingShaderProperty: shader_type(4) + name_idx(4) + n_extra(4=0) + controller(4) + flags1(4) + flags2(4) + uv(16) + ts_ref(4)
        sh_blk = struct.pack("<IiI", 0, -1, 0) + b"\x00" * 28 + struct.pack("<i", ts_idx)
        sh_idx = fo4.add_block("BSLightingShaderProperty", sh_blk)
        shape_i = next(i for i in range(len(fo4.blocks)) if fo4.type_of(i) == "BSTriShape")
        blk_s = bytearray(fo4.blocks[shape_i])
        # In test_fo4skin.shape_block: av_fields(72B) + bound(16B) + skin_ref(4B) + shader_ref(4B) + alpha_ref(4B)
        self.assertEqual(struct.unpack_from("<ii", blk_s, 92), (-1, -1))
        struct.pack_into("<i", blk_s, 92, sh_idx)
        fo4.blocks[shape_i] = bytes(blk_s)
        fo4_bytes = nif.serialize(fo4)

        def s_str(txt: str) -> bytes:
            b = txt.encode("latin-1") + b"\x00"
            return struct.pack("<I", len(b)) + b

        bgem_bytes = (
            b"BGEM" + struct.pack("<II", 2, 3) + b"\x00" * 30
            + s_str("actors/handy/handytorso_d.dds") + s_str("") + s_str("shared/cubemaps/eyecubemap.dds")
            + s_str("actors/handy/handytorso_n.dds") + s_str("")
        )

        class FakeSrc:
            def __init__(self, _d):
                pass

            def mesh(self, _n):
                return fo4_bytes

            def texture(self, name):
                if name.lower().endswith("handytorso_s.dds"):
                    return b"FAKE_S_DDS"
                return None

            def material(self, name):
                if name.lower().endswith("handylens.bgem"):
                    return bgem_bytes
                return None

        calls = []

        class FakeConv:
            neutral = "materials\\fo4port\\_neutral.mat"

            def __init__(self, _src, staging, *_a, spec_mask_roughness=False, **_kw):
                self.staging = staging
                self.spec_mask_roughness = spec_mask_roughness

            def _convert_texture_set(self, stem, diffuse, normal, spec):
                calls.append(("texset", stem, spec, self.spec_mask_roughness))
                mat_rel = f"materials/fo4port/{stem}.mat"
                p = Path(self.staging, *mat_rel.split("/"))
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(_sample_mat(with_rough_tex=bool(spec))), encoding="utf-8")
                return mat_rel.replace("/", "\\")

            def glass_material(self, base, normal):
                calls.append(("glass", base, normal))
                mat_rel = "materials/fo4port/glass/actors/handy/handytorso_d_deadbeef.mat"
                p = Path(self.staging, *mat_rel.split("/"))
                p.parent.mkdir(parents=True, exist_ok=True)
                mat = _sample_mat(with_rough_tex=True)
                mat["Summary"]["Layer1"]["Textures"]["Metalness"]["Replacement"]["x"] = 0.0
                p.write_text(json.dumps(mat), encoding="utf-8")
                return mat_rel.replace("/", "\\")

            def _shape_material(self, _n, _s):
                return self.neutral

        with tempfile.TemporaryDirectory() as td:
            stage = Path(td) / "stage"
            with mock.patch.object(cc.pipeline, "Fo4Archives", FakeSrc), \
                 mock.patch.object(cc.pipeline, "Converter", FakeConv), \
                 mock.patch.object(cc, "read_starfield", lambda _d, _n: tar.template()):
                rc = cc.main(["--fo4-data", "x", "--sf-data", "x", "--content-resources", "x", "--texconv", "x", "--staging", str(stage)])
            self.assertEqual(rc, 0)
            rep = json.loads((stage / "codsworth_report.json").read_text(encoding="utf-8"))
            self.assertEqual(rep["s_dds_converted"], {"Body": "textures\\actors\\handy\\HandyTorso_s.dds"})
            self.assertEqual(rep["handy_lens_material"], "materials\\fo4port\\glass\\actors\\handy\\handytorso_d_deadbeef.mat")
            self.assertTrue(any(c[0] == "texset" and c[2].lower().endswith("handytorso_s.dds") and c[3] is True for c in calls))
            self.assertTrue(any(c[0] == "glass" and "handytorso_d.dds" in c[1] for c in calls))

            # Every generated .mat (plus make_mission.copy_assets upgrade) passes the PBR invariant
            data_out = Path(td) / "data"
            mm.copy_assets(str(stage), str(data_out))
            for mat_p in list(stage.rglob("*.mat")) + list(data_out.rglob("*.mat")):
                mat = json.loads(mat_p.read_text(encoding="utf-8"))
                self.assertIsNone(inspect_actor_mat_pbr(mat), f"{mat_p} failed PBR check")

    def test_convert_parts_accepts_lens_material(self) -> None:
        from fo4sf.ba2 import Ba2
        import stage_ra2_handy as ra2
        if not ((ra2.FO4_DATA / "Fallout4 - Meshes.ba2").is_file() and (ra2.STARFIELD_DIR / "Data" / "Starfield - Meshes01.ba2").is_file()):
            self.skipTest("game data absent")
        fo4a = Ba2(str(ra2.FO4_DATA / "Fallout4 - Animations.ba2"))
        fo4m = Ba2(str(ra2.FO4_DATA / "Fallout4 - Meshes.ba2"))
        sf = lambda rel: ra2._read_archive(ra2.STARFIELD_DIR / "Data", "Starfield - Meshes*.ba2", rel)  # noqa: E731
        lens_mat = "materials\\fo4port\\glass\\actors\\handy\\handytorso_d_testlens.mat"
        files, rep, _skel, _names = ch.convert_parts(
            ch.read_codsworth_parts(fo4m),
            fo4a.read(fo4a.find(ch.SRC_SKELETON)),
            sf(ch.SF_MESH_TEMPLATE),
            sf(ch.SF_SKELETON_TEMPLATES["minibota"]),
            dict(ch.HANDY_MATERIALS),
            bind_overrides=ra2.BIND_OVERRIDES_FO4,
            lens_material=lens_mat,
        )
        self.assertTrue(rep["verify_mesh"]["ok"])
        self.assertIn("HandyLens", rep["verify_mesh"]["shapes"])
        self.assertEqual(rep["skipped"], [])
        self.assertEqual(len(rep["placed"]), 24)
        parsed = nif.parse(files[ch.OUT_MESH])
        shaders = [
            parsed.strings[struct.unpack_from("<i", parsed.blocks[sfnif.parse_bsgeometry(parsed.blocks[i]).shader], 0)[0]].decode("latin-1")
            for i in range(len(parsed.blocks))
            if parsed.type_of(i) == "BSGeometry"
        ]
        self.assertIn(lens_mat, shaders)


CHROME_STAGE = Path(r"D:\Modding\staging\codsworth_handy_chrome")


@unittest.skipUnless(CHROME_STAGE.is_dir(), "codsworth_handy_chrome staging folder not built")
class StagedChromeOutputTests(unittest.TestCase):
    def test_staged_chrome_mats_and_rough_dds(self) -> None:
        rep = json.loads((CHROME_STAGE / "codsworth_report.json").read_text(encoding="utf-8"))
        self.assertEqual(len(rep["s_dds_converted"]), 5)
        self.assertTrue(rep["handy_lens_material"])
        lens_p = CHROME_STAGE / Path(*rep["handy_lens_material"].split("\\"))
        self.assertTrue(lens_p.is_file())
        mats = sorted(CHROME_STAGE.rglob("*.mat"))
        self.assertGreaterEqual(len(mats), 7)  # 5 body + _neutral + HandyLens
        for mp in mats:
            mat = json.loads(mp.read_text(encoding="utf-8"))
            self.assertIsNone(inspect_actor_mat_pbr(mat), f"{mp} failed PBR check")
        # All 5 Handy _rough.dds are converted from FO4 _s.dds (larger than the 43,852-byte 256x256 fallback)
        handy_roughs = sorted((CHROME_STAGE / "textures" / "fo4port" / "texsets" / "actors" / "handy").glob("*_rough.dds"))
        self.assertEqual(len(handy_roughs), 5)
        for rp in handy_roughs:
            self.assertGreater(rp.stat().st_size, 43852, f"{rp.name} looks like flat 0.745 fallback")


if __name__ == "__main__":
    unittest.main()
