import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
import zlib

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DRIVER_PATH = os.path.join(REPO, "scripts", "slice", "make_interactive_fidelity.py")
PSC_PATH = os.path.join(REPO, "scripts", "slice", "FO4SF_ActivateChain.psc")

spec = importlib.util.spec_from_file_location("make_interactive_fidelity", DRIVER_PATH)
mif = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mif)


def subrec(sig, payload):
    s = sig.encode("ascii")
    if len(payload) > 0xFFFF:
        return b"XXXX" + struct.pack("<HI", 4, len(payload)) + s + struct.pack("<H", 0) + payload
    return s + struct.pack("<H", len(payload)) + payload


def rec(sig, fid, payload, flags=0, compress=False):
    if compress:
        flags |= 0x00040000
        payload = struct.pack("<I", len(payload)) + zlib.compress(payload)
    return sig.encode("ascii") + struct.pack("<IIIII", len(payload), flags, fid, 0, 0) + payload


def grup(label_bytes, gtype, body):
    return b"GRUP" + struct.pack("<I", 24 + len(body)) + label_bytes + struct.pack("<iII", gtype, 0, 0) + body


def tes4_header(masters=()):
    subs = [subrec("HEDR", struct.pack("<fII", 0.96, 1, 0x800))]
    for m in masters:
        subs.append(subrec("MAST", m.encode("utf-8") + b"\x00"))
        subs.append(subrec("DATA", struct.pack("<Q", 0)))
    return rec("TES4", 0, b"".join(subs), flags=1)


def vmad_activate_chain(target_fids, delays, unblock_flags, parent_only=False, extra_script=None):
    scripts = []
    if extra_script:
        scripts.append(struct.pack("<H", len(extra_script)) + extra_script.encode("ascii") + b"\x00" + struct.pack("<H", 0))

    props = []
    if target_fids is not None:
        p_t = struct.pack("<H", 7) + b"Targets" + struct.pack("<BB", 11, 1) + struct.pack("<I", len(target_fids))
        for tfid in target_fids:
            p_t += struct.pack("<HHI", 0, 0xFFFF, tfid)
        props.append(p_t)

        p_d = struct.pack("<H", 6) + b"Delays" + struct.pack("<BB", 14, 1) + struct.pack("<I", len(delays))
        for d in delays:
            p_d += struct.pack("<f", d)
        props.append(p_d)

        p_u = struct.pack("<H", 14) + b"UnblockTargets" + struct.pack("<BB", 15, 1) + struct.pack("<I", len(unblock_flags))
        for u in unblock_flags:
            p_u += struct.pack("<B", 1 if u else 0)
        props.append(p_u)

    if parent_only:
        props.append(struct.pack("<H", 18) + b"ParentActivateOnly" + struct.pack("<BBB", 5, 1, 1))

    sname = b"FO4SF_ActivateChain"
    scripts.append(struct.pack("<H", len(sname)) + sname + b"\x00" + struct.pack("<H", len(props)) + b"".join(props))
    return struct.pack("<hHH", 6, 2, len(scripts)) + b"".join(scripts)


def vmad_legacy_single():
    sname = b"DefaultActivateLinkedRefOnActivate"
    entry = struct.pack("<H", len(sname)) + sname + b"\x00" + struct.pack("<H", 0)
    return struct.pack("<hHH", 6, 2, 1) + entry


class TestInteractiveFidelityPython(unittest.TestCase):
    def test_psc_and_precheck_contract(self):
        with open(PSC_PATH, encoding="utf-8") as f:
            psc = f.read()
        for prop in ("ParentActivateOnly", "Targets", "Delays", "UnblockTargets"):
            self.assertIn(prop, psc)

        with tempfile.TemporaryDirectory() as td:
            good_zip = os.path.join(td, "good.zip")
            with zipfile.ZipFile(good_zip, "w") as zf:
                zf.writestr(
                    "Scripts/Source/ScriptObject.psc",
                    "Scriptname ScriptObject Native\nEvent OnInit()\nEndEvent\n",
                )
                zf.writestr(
                    "Scripts/Source/Form.psc",
                    "Scriptname Form extends ScriptObject Native\n",
                )
                zf.writestr(
                    "Scripts/Source/ObjectReference.psc",
                    "Scriptname ObjectReference extends Form Native\n"
                    "Event OnCellAttach()\nEndEvent\n"
                    "Event OnLoad()\nEndEvent\n"
                    "Event OnActivate(ObjectReference akActionRef)\nEndEvent\n"
                    "Function BlockActivation(bool abBlocked = true, bool abHideActivateText = false) native\n"
                    "bool Function Activate(ObjectReference akActivator, bool abDefaultProcessingOnly = false) native\n",
                )
                zf.writestr(
                    "Scripts/Source/Utility.psc",
                    "Scriptname Utility extends ScriptObject Native\nFunction Wait(float afSeconds) global native\n",
                )
            res = mif.precheck_zip(good_zip)
            self.assertTrue(res["ok"], res)

            bad_zip = os.path.join(td, "bad.zip")
            with zipfile.ZipFile(bad_zip, "w") as zf:
                zf.writestr("Scripts/Source/ScriptObject.psc", "Scriptname ScriptObject Native\n")
            res_bad = mif.precheck_zip(bad_zip)
            self.assertFalse(res_bad["ok"])
            self.assertIn("ObjectReference.BlockActivation", res_bad["missing"])

    def test_binary_diff_counts_interior_and_exterior_all_five_families(self):
        with tempfile.TemporaryDirectory() as td:
            core_path = os.path.join(td, "FO4TerrainCore.esm")
            port_path = os.path.join(td, "FO4Port.esm")
            ovl_path = os.path.join(td, "FO4SFInteractiveFidelity.esm")

            # FO4Port.esm (master 00 = Starfield.esm, self = 01): interior cell 0x01000810 with stripped refs
            int_cell_fid = 0x01000810
            r1 = rec("REFR", 0x01000811, subrec("NAME", struct.pack("<I", 0x01000800)) + subrec("DATA", struct.pack("<ffffff", 1, 2, 3, 0, 0, 0)))
            r2 = rec("REFR", 0x01000812, subrec("NAME", struct.pack("<I", 0x01000801)) + subrec("DATA", struct.pack("<ffffff", 4, 5, 6, 0, 0, 0)))
            int_cell = rec("CELL", int_cell_fid, subrec("DATA", b"\x01\x00"))
            int_children = grup(struct.pack("<I", int_cell_fid), 6, grup(struct.pack("<I", int_cell_fid), 9, r1 + r2))
            cell_top = grup(b"CELL", 0, grup(struct.pack("<i", 0), 2, grup(struct.pack("<i", 1), 3, int_cell + int_children)))
            with open(port_path, "wb") as f:
                f.write(tes4_header(["Starfield.esm"]) + cell_top)

            # FO4TerrainCore.esm (master 00 = Starfield.esm, self = 01): world 0x01000803, top cell 0x01001805, ext (-10, 11) 0x01000DAF
            wrld_fid = 0x01000803
            top_fid = 0x01001805
            ext_fid = 0x01000DAF
            # Legacy button in before: DefaultActivateLinkedRefOnActivate + LinkCustom02 (0x0005D5E7) -> XAPR=1, XLKR=0
            ext_btn_before = rec(
                "REFR",
                0x01000902,
                subrec("NAME", struct.pack("<I", 0x01000801))
                + subrec("DATA", struct.pack("<ffffff", -990.0, 1110.0, 98.0, 0, 0, 0))
                + subrec("VMAD", vmad_legacy_single())
                + subrec("XLKR", struct.pack("<II", 0x0005D5E7, 0x01000903)),
            )
            ext_cell = rec("CELL", ext_fid, subrec("XCLC", struct.pack("<iiI", -10, 11, 0)))
            ext_children = grup(struct.pack("<I", ext_fid), 6, grup(struct.pack("<I", ext_fid), 9, ext_btn_before))
            top_cell = rec("CELL", top_fid, subrec("DATA", b"\x02\x00"))
            wrld_rec = rec("WRLD", wrld_fid, subrec("EDID", b"FO4Core_Commonwealth\x00"))
            ext_sub = grup(struct.pack("<hh", -2, 1), 5, ext_cell + ext_children)
            ext_blk = grup(struct.pack("<hh", -1, 0), 4, ext_sub)
            wrld_children = grup(struct.pack("<I", wrld_fid), 1, top_cell + ext_blk)
            wrld_top = grup(b"WRLD", 0, wrld_rec + wrld_children)
            with open(core_path, "wb") as f:
                f.write(tes4_header(["Starfield.esm"]) + wrld_top)

            # Overlay (masters: 00=Starfield.esm, 01=FO4TerrainCore.esm, 02=FO4Port.esm, self=03)
            # Interior overrides:
            # - r1 (0x02000811): compressed + oversized pad + XESP(opposite|popin) + XLKR(1 valid + 1 MultirefLOD skipped? here valid) + XLOC(50, key)
            # - r2 (0x02000812): FO4SF_ActivateChain driving 2 targets (delays 0.0, 0.5) + ParentActivateOnly
            # - r_door_int (0x03000800): persistent XTEL door
            r1_after = rec(
                "REFR",
                0x02000811,
                subrec("NAME", struct.pack("<I", 0x02000800))
                + subrec("XXXX", b"")[:0]  # exercised via >64KB dummy subrecord below
                + subrec("ZNAM", b"\x00" * 66000)
                + subrec("DATA", struct.pack("<ffffff", 1, 2, 3, 0, 0, 0))
                + subrec("XESP", struct.pack("<II", 0x03000801, 3))
                + subrec("XLOC", struct.pack("<B3sIB7s", 50, b"\x00\x00\x00", 0x02000804, 1, b"\x00" * 7))
                + subrec("XLKR", struct.pack("<II", 0x03000802, 0x02000812)),
                flags=0x800,
                compress=True,
            )
            r2_after = rec(
                "REFR",
                0x02000812,
                subrec("NAME", struct.pack("<I", 0x02000801))
                + subrec("DATA", struct.pack("<ffffff", 4, 5, 6, 0, 0, 0))
                + subrec("VMAD", vmad_activate_chain([0x02000811, 0x03000800], [0.0, 0.5], [False, True], parent_only=True)),
            )
            r_door_int = rec(
                "REFR",
                0x03000800,
                subrec("NAME", struct.pack("<I", 0x0024F9CE))
                + subrec("DATA", struct.pack("<ffffff", -1, 2, 0, 0, 0, 0))
                + subrec("XTEL", struct.pack("<IffffffII", 0x03000805, -995.0, 1105.0, 99.0, 0, 0, 1.0, 0, 0)),
                flags=0x400,
            )
            ovl_int_cell = rec("CELL", 0x02000810, subrec("DATA", b"\x01\x00"))
            ovl_int_children = grup(
                struct.pack("<I", 0x02000810),
                6,
                grup(struct.pack("<I", 0x02000810), 8, r_door_int) + grup(struct.pack("<I", 0x02000810), 9, r1_after + r2_after),
            )
            ovl_cell_top = grup(b"CELL", 0, grup(struct.pack("<i", 0), 2, grup(struct.pack("<i", 1), 3, ovl_int_cell + ovl_int_children)))

            # Exterior TopCell persistent door at (-994.9, 1109.5) -> grid (-10, 11) + upgraded button in (-10, 11)
            r_door_ext = rec(
                "REFR",
                0x03000805,
                subrec("NAME", struct.pack("<I", 0x0024F9CE))
                + subrec("DATA", struct.pack("<ffffff", -994.9, 1109.5, 98.6, 0, 0, 0))
                + subrec("XTEL", struct.pack("<IffffffII", 0x03000800, 0, -6, 0, 0, 0, 2.0, 0, 0)),
                flags=0x400,
            )
            ext_btn_after = rec(
                "REFR",
                0x01000902,
                subrec("NAME", struct.pack("<I", 0x01000801))
                + subrec("DATA", struct.pack("<ffffff", -990.0, 1110.0, 98.0, 0, 0, 0))
                + subrec("VMAD", vmad_activate_chain([0x01000903], [0.25], [True], extra_script="FO4SF_LoadDoor")),
            )
            ovl_top_cell = rec("CELL", 0x01001805, subrec("DATA", b"\x02\x00"))
            ovl_top_children = grup(struct.pack("<I", 0x01001805), 6, grup(struct.pack("<I", 0x01001805), 8, r_door_ext))
            ovl_ext_cell = rec("CELL", 0x01000DAF, subrec("XCLC", struct.pack("<iiI", -10, 11, 0)))
            ovl_ext_children = grup(struct.pack("<I", 0x01000DAF), 6, grup(struct.pack("<I", 0x01000DAF), 9, ext_btn_after))
            ovl_wrld = rec("WRLD", 0x01000803, subrec("EDID", b"FO4Core_Commonwealth\x00"))
            ovl_wrld_children = grup(
                struct.pack("<I", 0x01000803),
                1,
                ovl_top_cell
                + ovl_top_children
                + grup(struct.pack("<hh", -1, 0), 4, grup(struct.pack("<hh", -2, 1), 5, ovl_ext_cell + ovl_ext_children)),
            )
            ovl_wrld_top = grup(b"WRLD", 0, ovl_wrld + ovl_wrld_children)

            with open(ovl_path, "wb") as f:
                f.write(tes4_header(["Starfield.esm", "FO4TerrainCore.esm", "FO4Port.esm"]) + ovl_cell_top + ovl_wrld_top)

            groups = mif.build_target_groups(cells_arg="synth_group=FO4Port.esm:000810+ext:-10,11")
            rep = mif.diff_counts([core_path, port_path], [core_path, port_path, ovl_path], groups)
            self.assertTrue(rep["non_decreasing"])
            b = rep["totals"]["before"]
            a = rep["totals"]["after"]
            self.assertEqual(b["xesp"], 0)
            self.assertEqual(b["xloc"], 0)
            self.assertEqual(b["xlkr"], 0)
            self.assertEqual(b["xapr"], 1)  # legacy DefaultActivateLinkedRefOnActivate in before
            self.assertEqual(b["xtel"], 0)

            self.assertEqual(a["xesp"], 1)
            self.assertEqual(a["xloc"], 1)
            self.assertEqual(a["xlkr"], 1)
            self.assertEqual(a["xapr"], 3)  # 2 interior + 1 upgraded exterior
            self.assertEqual(a["xtel"], 2)  # 1 interior + 1 TopCell exterior attributed to (-10, 11)

            cell_int = [c for c in rep["cells"] if c["kind"] == "CELL_INT"][0]["after"]
            self.assertEqual(cell_int["xesp_opposite"], 1)
            self.assertEqual(cell_int["xesp_popin"], 1)
            self.assertEqual(cell_int["xloc_with_key"], 1)
            self.assertEqual(cell_int["xapr_delays"], 1)
            self.assertEqual(cell_int["xapr_parent_only_refs"], 1)

            cell_ext = [c for c in rep["cells"] if c["kind"] == "CELL_EXT"][0]["after"]
            self.assertEqual(cell_ext["xtel_script_bridged"], 1)

    def test_fold_hardlink_readme_safety_and_verify_tamper_refusal(self):
        with tempfile.TemporaryDirectory() as td:
            port_esm = os.path.join(td, "FO4Port.esm")
            with open(port_esm, "wb") as f:
                f.write(b"port-bytes")

            core_dir = os.path.join(td, "core-set")
            os.makedirs(os.path.join(core_dir, "Data", "Meshes"), exist_ok=True)
            core_esm = os.path.join(core_dir, "FO4TerrainCore.esm")
            mars_esm = os.path.join(core_dir, "FO4TerrainCore_Mars.esm")
            mesh_file = os.path.join(core_dir, "Data", "Meshes", "sample.nif")
            with open(core_esm, "wb") as f:
                f.write(b"core-bytes")
            with open(mars_esm, "wb") as f:
                f.write(b"mars-bytes")
            with open(mesh_file, "wb") as f:
                f.write(b"mesh-bytes")

            orig_core_readme = (
                "Core set.\n"
                "  scripts/game/exp_install.py install --exp-dir <this folder> --starfield <game> "
                "--plugins FO4TerrainCore.esm,FO4TerrainCore_Mars.esm --pack\n"
            )
            core_readme_path = os.path.join(core_dir, "README.txt")
            with open(core_readme_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(orig_core_readme)

            stage_dir = os.path.join(td, "stage")
            os.makedirs(os.path.join(stage_dir, "Data", "Scripts"), exist_ok=True)
            plugin_path = os.path.join(stage_dir, mif.PLUGIN)
            pex_path = os.path.join(stage_dir, "Data", "Scripts", f"{mif.CHAIN_SCRIPT}.pex")
            with open(plugin_path, "wb") as f:
                f.write(b"fidelity-esm-bytes")
            with open(pex_path, "wb") as f:
                f.write(b"fidelity-pex-bytes")
            with open(os.path.join(stage_dir, "README.txt"), "w", encoding="utf-8", newline="\n") as f:
                f.write("Stage readme.\n")

            plan = {
                "kind": "interactive-fidelity",
                "plugin": mif.PLUGIN,
                "plugin_sha256": mif.sha256(plugin_path),
                "scripts": {mif.CHAIN_SCRIPT: mif.sha256(pex_path)},
                "checked_against_sha256": {
                    "FO4Port.esm": mif.sha256(port_esm),
                    "FO4TerrainCore.esm": mif.sha256(core_esm),
                },
            }
            plan_path = os.path.join(stage_dir, "plan.json")
            mif.save_json(plan_path, plan)

            # Stage verify passes
            self.assertEqual(
                mif.main(["verify", "--exp-dir", stage_dir, "--plan", plan_path, "--port", port_esm, "--core", core_esm]),
                0,
            )

            # Extra rogue .esm in stage_dir must fail verify
            rogue_esm = os.path.join(stage_dir, "Rogue.esm")
            with open(rogue_esm, "wb") as f:
                f.write(b"rogue")
            self.assertEqual(
                mif.main(["verify", "--exp-dir", stage_dir, "--plan", plan_path, "--port", port_esm, "--core", core_esm]),
                1,
            )
            os.remove(rogue_esm)

            # Fold into out_dir
            folded_dir = os.path.join(td, "folded")
            self.assertEqual(
                mif.main(["fold", "--stage", stage_dir, "--core-dir", core_dir, "--out", folded_dir, "--port", port_esm]),
                0,
            )

            # CRITICAL: core_dir/README.txt must remain byte-for-byte untouched (never overwritten via hardlink!)
            with open(core_readme_path, encoding="utf-8") as f:
                self.assertEqual(f.read(), orig_core_readme)
            with open(os.path.join(folded_dir, "README.txt"), encoding="utf-8") as f:
                folded_readme = f.read()
            self.assertIn("FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFInteractiveFidelity.esm", folded_readme)

            # Re-folding onto an already-folded folder without --clean-prior must fail; with --clean-prior must succeed
            folded_again = os.path.join(td, "folded-again")
            with self.assertRaises(SystemExit):
                mif.main(["fold", "--stage", stage_dir, "--core-dir", folded_dir, "--out", folded_again, "--port", port_esm])
            self.assertEqual(
                mif.main(["fold", "--clean-prior", "--stage", stage_dir, "--core-dir", folded_dir, "--out", folded_again, "--port", port_esm]),
                0,
            )

            # Tampering with the folded .pex must fail verify
            with open(os.path.join(folded_dir, "Data", "Scripts", f"{mif.CHAIN_SCRIPT}.pex"), "wb") as f:
                f.write(b"tampered")
            self.assertEqual(
                mif.main(["verify", "--exp-dir", folded_dir, "--plan", plan_path, "--port", port_esm]),
                1,
            )

    def test_public_surface_clean(self):
        generic_local_path_patterns = (
            r"\b[A-Za-z]:[\\/][A-Za-z0-9_.-]+",
            r"/(?:home|Users)/[A-Za-z0-9_.-]+",
        )
        doc_path = os.path.join(REPO, "docs", "slice", "converter-interactive-fidelity.md")
        cs_paths = [
            os.path.join(REPO, "dotnet", "PluginSpike", "InteractiveFidelity.cs"),
            os.path.join(REPO, "dotnet", "InteractiveFidelity", "Program.cs"),
            os.path.join(REPO, "dotnet", "InteractiveFidelity", "OverlayBuilder.cs"),
            os.path.join(REPO, "dotnet", "InteractiveFidelity", "FidelityCheck.cs"),
            os.path.join(REPO, "dotnet", "InteractiveFidelity", "SelfTest.cs"),
        ]
        for path in [DRIVER_PATH, PSC_PATH, doc_path] + cs_paths:
            with open(path, encoding="utf-8") as f:
                text = f.read()
            for pat in generic_local_path_patterns:
                self.assertIsNone(
                    mif.re.search(pat, text),
                    f"machine-specific path pattern {pat!r} found in {os.path.basename(path)}",
                )


@unittest.skipUnless(
    shutil.which("dotnet") and os.environ.get("FO4SF_DOTNET_TESTS"),
    "set FO4SF_DOTNET_TESTS=1 with dotnet installed to run C# synthetic suites",
)
class TestInteractiveFidelityDotnet(unittest.TestCase):
    def test_interactive_fidelity_selftest(self):
        with tempfile.TemporaryDirectory() as td:
            proj = os.path.join(REPO, "dotnet", "InteractiveFidelity")
            r = subprocess.run(["dotnet", "run", "--project", proj, "--", "selftest", td], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("selftest pass", r.stdout)

    def test_plugin_spike_interactive_fidelity_tests(self):
        proj = os.path.join(REPO, "dotnet", "PluginSpike.Tests")
        r = subprocess.run(["dotnet", "run", "--project", proj], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Interactive fidelity synthetic checks and binary round-trip passed.", r.stdout)


if __name__ == "__main__":
    unittest.main()
