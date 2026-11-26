"""Round 11 R11-W3 tests for D2 (Preston's missing hat + Still 07 bare-hands overlap) and A2.3 (scoped 0x986 FO4_ConcordRaider).

Covers:
1. D2 Binary Proof & Fix:
   - Reproduces the exact 2g root cause: duplicating Starfield.esm:0x211140 (AA_Clothes_First_Mercenary_01_Hat)
     preserved MO2F=0x01 / MO3F=0x01 (HasFaceBonesModel) + XFLG=0x01, redirecting Starfield to a missing
     prestongarveyhat_m_facebones.nif.
   - Proves FalloutActorLooks.ApplyActorLooks emits ZERO MO2F, MO3F, or XFLG subrecords on 0x981, 0x984, and 0x989,
     sets BO64=0x10 on ARMO 0x985 and BO64=0x12 on ARMA 0x984 (matching Sam Coe companion hat 0x1C8E0A -> 0x25DEEB),
     and sets BO64=0x68 (BODY | UpperBody | Hands) on 0x981/0x983/0x989/0x98A to mask AA_Naked_Hands (0x030580).
2. A2.3 Scoped Concord Raider (0x000986 FO4_ConcordRaider):
   - Proves FO4SFMission.esm emits ZERO foreign NPC_ overrides of FO4ActorRaider.esm (no 0xF04800 override).
   - Proves local 0x000986 (FO4_ConcordRaider, FormVersion=581) carries DOFT=SOFT=0x988 and PRPS 0x0B120E=1.0.
   - Proves placed Concord raider ACHRs (0x803..0x807) point to local 0x000986 while non-Concord raider ACHRs (e.g.
     0xA24 Corvega boss) stay on shared FO4ActorRaider.esm:0xF04800 untouched.
3. Source, report, BOM, and cross-OS path-leak hygiene.
"""
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from fo4sf.planet.esm import Plugin  # noqa: E402

DRIVE_LEAK_RE = re.compile(r"\b[A-Za-z]:[\\/]")


def _iter_raw_records(plugin_path: Path):
    """Yield (sig_bytes, formid_u32, flags_u32, formver_u16, subrecords_list) across all nested GRUPs."""
    data = plugin_path.read_bytes()

    def walk(buf: bytes, p: int, lim: int):
        while p + 24 <= lim:
            sig = buf[p : p + 4]
            if sig == b"GRUP":
                gsz = struct.unpack_from("<I", buf, p + 4)[0]
                if gsz < 24 or p + gsz > lim:
                    break
                yield from walk(buf, p + 24, p + gsz)
                p += gsz
            else:
                rsz, rflg, rfid = struct.unpack_from("<III", buf, p + 4)
                fver = struct.unpack_from("<H", buf, p + 20)[0]
                raw = buf[p + 24 : p + 24 + rsz]
                if rflg & 0x00040000 and len(raw) >= 4:
                    raw = zlib.decompress(raw[4:])
                subs = []
                q = 0
                xxxx = None
                while q + 6 <= len(raw):
                    ss, sl = struct.unpack_from("<4sH", raw, q)
                    q += 6
                    if ss == b"XXXX" and sl == 4:
                        xxxx = struct.unpack_from("<I", raw, q)[0]
                        q += 4
                        continue
                    if xxxx is not None:
                        sl = xxxx
                        xxxx = None
                    subs.append((ss, raw[q : q + sl]))
                    q += sl
                yield sig, rfid, rflg, fver, subs
                p += 24 + rsz

    yield from walk(data, 0, len(data))


class TestR11D2A23ActorLooks(unittest.TestCase):
    @unittest.skipUnless(shutil.which("dotnet"), "dotnet SDK required for Mutagen binary verification")
    def test_d2_hat_no_facebones_flag_and_a23_scoped_concord_raider_binary(self):
        mission_proj = REPO_ROOT / "dotnet" / "Mission" / "Mission.csproj"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            harness_dir = tmp_path / "r11_w3_harness"
            harness_dir.mkdir(parents=True, exist_ok=True)
            (harness_dir / "Harness.csproj").write_text(
                f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net9.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
  <ItemGroup>
    <ProjectReference Include="{mission_proj}" />
  </ItemGroup>
</Project>
""",
                encoding="utf-8",
            )
            (harness_dir / "Program.cs").write_text(
                """FalloutActorLooks.RunStandaloneSelfTest(args[0]);
Console.WriteLine("R11_W3_SELFTEST_OK");
""",
                encoding="utf-8",
            )
            esm_dir = tmp_path / "esms"
            res = subprocess.run(
                ["dotnet", "run", "--project", str(harness_dir / "Harness.csproj"), "-c", "Release", "--", str(esm_dir)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0, f"R11-W3 selftest failed:\n{res.stdout}\n{res.stderr}")
            self.assertIn("R11_W3_SELFTEST_OK", res.stdout)

            # Verify synthetic Starfield.esm DID carry XFLG=0x01 (Model.Flags = HasFaceBonesModel) on 0x211140
            sf_recs = list(_iter_raw_records(esm_dir / "Starfield.esm"))
            sf_hat_arma = next(subs for sig, fid, _, _, subs in sf_recs if sig == b"ARMA" and (fid & 0xFFFFFF) == 0x211140)
            sf_hat_sub_sigs = [s for s, _ in sf_hat_arma]
            self.assertGreaterEqual(sf_hat_sub_sigs.count(b"XFLG"), 2, "Synthetic 0x211140 must carry Male+Female XFLG=1 to test D2 stripping")

            # Now inspect raw binary subrecords of FO4SFMission.esm!
            mission_path = esm_dir / "FO4SFMission.esm"
            m_recs = list(_iter_raw_records(mission_path))

            # 1. TES4 masters order (Task 1i drops static FO4TerrainCore.esm dependency):
            #    [0]=Starfield.esm, [1]=FO4ActorRaider.esm -> local index == 0x02
            tes4_subs = next(subs for sig, _, _, _, subs in m_recs if sig == b"TES4")
            masters = [b.rstrip(b"\x00").decode("utf-8") for s, b in tes4_subs if s == b"MAST"]
            self.assertEqual(masters, ["Starfield.esm", "FO4ActorRaider.esm"])
            local_hi = len(masters)  # 0x02
            raider_hi = masters.index("FO4ActorRaider.esm")  # 0x01

            # 2. D2 checks on ARMA (0x981, 0x984, 0x989) & ARMO (0x983, 0x985, 0x98A)
            armas = {fid & 0xFFFFFF: dict(subs) for sig, fid, _, _, subs in m_recs if sig == b"ARMA" and (fid >> 24) == local_hi}
            arma_raw_sigs = {
                fid & 0xFFFFFF: [s for s, _ in subs]
                for sig, fid, _, _, subs in m_recs
                if sig == b"ARMA" and (fid >> 24) == local_hi
            }
            for aid in (0x981, 0x984, 0x989):
                self.assertIn(aid, armas)
                for forbidden in (b"MO2F", b"MO3F", b"XFLG"):
                    self.assertNotIn(
                        forbidden,
                        arma_raw_sigs[aid],
                        f"D2 regression: ARMA 0x{aid:X} emitted {forbidden!r} (HasFaceBonesModel redirect!)",
                    )

            self.assertEqual(
                armas[0x984][b"MOD2"].rstrip(b"\x00").decode("utf-8").replace("/", "\\").lower(),
                r"fo4port\armor\preston_garvey\prestongarveyhat_m.nif",
            )
            self.assertEqual(struct.unpack("<Q", armas[0x984][b"BO64"])[0], 0x12)
            self.assertEqual(struct.unpack("<Q", armas[0x981][b"BO64"])[0], 0x68)
            self.assertEqual(struct.unpack("<Q", armas[0x989][b"BO64"])[0], 0x28)

            armos = {fid & 0xFFFFFF: dict(subs) for sig, fid, _, _, subs in m_recs if sig == b"ARMO" and (fid >> 24) == local_hi}
            self.assertEqual(struct.unpack("<Q", armos[0x985][b"BO64"])[0], 0x10)
            self.assertEqual(struct.unpack("<Q", armos[0x983][b"BO64"])[0], 0x68)
            self.assertEqual(struct.unpack("<Q", armos[0x98A][b"BO64"])[0], 0x28)

            # 3. A2.3 + Review #7 checks: ZERO foreign NPC_ overrides of FO4ActorRaider.esm; local 0x986 FO4_ConcordRaider
            #    present; ZERO NPC_ records in FO4SFMission.esm carry 0x003D094D Spacer spacesuit outfit; all 3 later-mission
            #    FO4_LvlRaider-cloned bosses (0x0A23 FO4_CorvegaBoss, 0x0AD1 FO4_Kellogg, 0x0B31 FO4_CourserZ247) wear 0x988
            #    + PRPS 0x0B120E=1.0; non-raider FO4_Sturges (0x0A00) stays untouched; Concord ACHRs (0x803..0x807) -> 0x986
            #    while non-Concord ACHR (0xA24) -> FO4ActorRaider.esm:0xF04800!
            npc_records = [(fid, fver, dict(subs)) for sig, fid, _, fver, subs in m_recs if sig == b"NPC_"]
            raider_overrides = [fid for fid, _, _ in npc_records if (fid >> 24) == raider_hi]
            self.assertEqual(raider_overrides, [], f"A2.3 violation: foreign FO4ActorRaider.esm overrides found: {raider_overrides}")

            spacer_carriers = []
            for fid, _, sd in npc_records:
                for tag in (b"DOFT", b"SOFT"):
                    if tag in sd and (struct.unpack("<I", sd[tag])[0] & 0xFFFFFF) == 0x3D094D:
                        spacer_carriers.append((fid, sd.get(b"EDID", b"").rstrip(b"\x00").decode("utf-8", "replace"), tag))
            self.assertEqual(
                spacer_carriers,
                [],
                f"Review #7 regression: NPC_ records in FO4SFMission.esm still carry 0x003D094D Spacer spacesuit: {spacer_carriers}",
            )

            local_npcs = {fid & 0xFFFFFF: (fver, sd) for fid, fver, sd in npc_records if (fid >> 24) == local_hi}
            self.assertIn(0x986, local_npcs, "Missing local 0x000986 FO4_ConcordRaider")
            fver_986, sd_986 = local_npcs[0x986]
            self.assertEqual(fver_986, 581)
            self.assertEqual(sd_986[b"EDID"].rstrip(b"\x00"), b"FO4_ConcordRaider")
            self.assertEqual(struct.unpack("<I", sd_986[b"DOFT"])[0], (local_hi << 24) | 0x988)
            self.assertEqual(struct.unpack("<I", sd_986[b"SOFT"])[0], (local_hi << 24) | 0x988)
            self.assertNotIn(b"CNTO", sd_986, "R13 E3: FO4_ConcordRaider must have 0 CNTO inventory items")
            aidt = sd_986[b"AIDT"]
            self.assertGreaterEqual(aidt[0], 1, "FO4_ConcordRaider AIDT Aggression must be >= Aggressive")
            self.assertGreaterEqual(aidt[1], 3, "FO4_ConcordRaider AIDT Confidence must be >= Brave")

            import sys as _sys
            if str(REPO_ROOT / "scripts" / "actors") not in _sys.path:
                _sys.path.insert(0, str(REPO_ROOT / "scripts" / "actors"))
            import stage_c5_actor_looks as _c5
            self.assertFalse(any("malehands" in s.lower() for s in _c5.RAIDER_OUTFIT_SOURCES))
            self.assertEqual(_c5.fo4_human_bone_to_sf("Belly_skin", ["C_Spine1", "C_Spine2", "C_Chest"]), "C_Spine1")
            self.assertEqual(_c5.fo4_human_bone_to_sf("UpperBelly_skin", ["C_Spine1", "C_Spine2", "C_Chest"]), "C_Spine2")

            for boss_id, boss_edid in (
                (0x0A23, b"FO4_CorvegaBoss"),
                (0x0AD1, b"FO4_Kellogg"),
                (0x0B31, b"FO4_CourserZ247"),
            ):
                self.assertIn(boss_id, local_npcs, f"Missing seeded later-mission boss 0x{boss_id:04X}")
                _, sd_boss = local_npcs[boss_id]
                self.assertEqual(sd_boss[b"EDID"].rstrip(b"\x00"), boss_edid)
                self.assertEqual(struct.unpack("<I", sd_boss[b"DOFT"])[0], (local_hi << 24) | 0x988)
                self.assertEqual(struct.unpack("<I", sd_boss[b"SOFT"])[0], (local_hi << 24) | 0x988)
                prps = sd_boss.get(b"PRPS", b"")
                self.assertEqual(len(prps) % 12, 0)
                entries = [struct.unpack_from("<IfI", prps, off) for off in range(0, len(prps), 12)]
                self.assertTrue(
                    any((av & 0xFFFFFF) == 0x0B120E and abs(val - 1.0) < 1e-4 for av, val, _ in entries),
                    f"Review #7: 0x{boss_id:04X} ({boss_edid!r}) missing PRPS 0x0B120E == 1.0: {entries}",
                )

            _, sd_sturges = local_npcs[0x0A00]
            self.assertNotIn(b"DOFT", sd_sturges)
            self.assertNotIn(b"SOFT", sd_sturges)

            achrs = {fid & 0xFFFFFF: dict(subs) for sig, fid, _, _, subs in m_recs if sig == b"ACHR" and (fid >> 24) == local_hi}
            for rid in range(0x803, 0x808):
                self.assertIn(rid, achrs)
                base_fid = struct.unpack("<I", achrs[rid][b"NAME"])[0]
                self.assertEqual(
                    base_fid,
                    (local_hi << 24) | 0x986,
                    f"Concord ACHR 0x{rid:X} base 0x{base_fid:08X} != local 0x{(local_hi << 24) | 0x986:08X}",
                )

            corvega_base = struct.unpack("<I", achrs[0xA24][b"NAME"])[0]
            self.assertEqual(
                corvega_base,
                (raider_hi << 24) | 0xF04800,
                f"Non-Concord ACHR 0xA24 base 0x{corvega_base:08X} was unexpectedly mutated away from FO4ActorRaider.esm:0xF04800",
            )

            # Verify fo4sf.planet.esm.Plugin also parses cleanly
            with Plugin(str(mission_path)) as plug:
                edids = {r.edid for r in plug.records("NPC_")}
                self.assertIn("FO4_ConcordRaider", edids)
                self.assertIn("FO4_CorvegaBoss", edids)
                self.assertIn("FO4_Kellogg", edids)
                self.assertIn("FO4_CourserZ247", edids)
                self.assertNotIn("FO4_LvlRaider", edids)

    def test_r11_w3_owned_files_hygiene(self):
        owned = [
            REPO_ROOT / "dotnet" / "Mission" / "FalloutActorLooks.cs",
            REPO_ROOT / "scripts" / "actors" / "stage_c5_actor_looks.py",
            REPO_ROOT / "docs" / "actors" / "c5-actor-and-hud-looks-report.md",
            REPO_ROOT / "tests" / "test_r10_c5_looks.py",
            REPO_ROOT / "tests" / "test_r11_d2_a23_actor_looks.py",
        ]
        for path in owned:
            self.assertTrue(path.is_file(), f"Missing owned file: {path}")
            raw = path.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM present in {path.name}")
            text = raw.decode("utf-8")
            if not path.name.startswith("test_"):
                leaks = DRIVE_LEAK_RE.findall(text)
                self.assertEqual(leaks, [], f"Local drive-letter path leak in {path.name}: {leaks}")

        doc = (REPO_ROOT / "docs" / "actors" / "c5-actor-and-hud-looks-report.md").read_text(encoding="utf-8")
        first_line = doc.splitlines()[0]
        self.assertTrue(first_line.startswith("Titles: Fallout 4") and "| Modes:" in first_line and "| Track:" in first_line)
        for token in (
            "HasFaceBonesModel",
            "MO2F",
            "prestongarveyhat_m_facebones.nif",
            "FO4_ConcordRaider",
            "0x000986",
            "FO4_CorvegaBoss",
            "FO4_Kellogg",
            "FO4_CourserZ247",
            "0x003D094D",
            "AA_Naked_Hands",
            "0x68",
            "ran in game",
            "pushed, not run",
        ):
            self.assertIn(token, doc, f"Report missing required R11 D2/A2.3/Review-#7 forensic token: {token}")


if __name__ == "__main__":
    unittest.main()
