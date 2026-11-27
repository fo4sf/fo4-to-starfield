"""Synthetic unit tests for scripts/research/fo4_scene_reference.py (F0).

Zero game files required and zero .psc files committed under tests/.
"""
from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_RESEARCH = REPO_ROOT / "scripts" / "research"
if str(SCRIPTS_RESEARCH) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_RESEARCH))

import fo4_scene_reference as f0  # noqa: E402


def _build_synthetic_gnrl_ba2(entries: list[tuple[str, bytes]]) -> bytes:
    """Construct a minimal uncompressed FO4 v1 GNRL BA2 archive matching src/fo4sf/ba2.py."""
    names_blob = bytearray()
    for name, _ in entries:
        nb = name.encode("utf-8")
        names_blob.extend(struct.pack("<H", len(nb)))
        names_blob.extend(nb)

    table_size = len(entries) * 36
    data_start = 24 + table_size
    name_off = data_start + sum(len(data) for _, data in entries)

    buf = bytearray()
    buf.extend(struct.pack("<4sI4sIQ", b"BTDX", 1, b"GNRL", len(entries), name_off))

    cur_off = data_start
    payload_buf = bytearray()
    for name, data in entries:
        ext = (Path(name).suffix.lstrip(".")[:4]).ljust(4, "\x00").encode("ascii")
        buf.extend(struct.pack("<I4sIIQIII", 0, ext, 0, 0x100100, cur_off, 0, len(data), 0xBAADF00D))
        payload_buf.extend(data)
        cur_off += len(data)

    buf.extend(payload_buf)
    buf.extend(names_blob)
    return bytes(buf)


SYNTHETIC_QF_PSC = """\
Scriptname Fragments:Quests:QF_TestQuest_00000100 extends Quest Hidden

; RegisterForAnimationEvent(self, "CommentedOutEvent")
{
  PlayerRef.MoveTo(CommentedMarker)
  Game.FadeOutGame(true, true, 0.5, 1.0, true)
}

Function Fragment_0()
    ObjectReference kPlayer = Game.GetPlayer()
    InputEnableLayer kLayer = InputEnableLayer.Create()
    kLayer.DisablePlayerControls()
    RegisterForAnimationEvent(kPlayer, "pipboyIdleRoot")
    WaitForAnimationEvent(kPlayer, "pipboyClamp")
    RegisterForRemoteEvent(kDoor, "OnOpen")
    kDoor.PlayAnimation("Stage2")
    kPlayer.PlayIdle(FakeIdle)
    kPlayer.MoveTo(kMarker)
    kPlayer.SetPosition(1.0, 2.0, 3.0)
    kFurn.Activate(kPlayer)
    kGate.SetOpen(True)
    kGate.Lock(False, False)
EndFunction

Event OnAnimationEvent(ObjectReference akSource, string asEventName)
    if asEventName == "KlaxonStop"
        kLayer.Delete()
    endif
EndEvent
"""


class TestF0SceneReference(unittest.TestCase):
    def test_no_psc_files_under_tests(self) -> None:
        psc_files = list((REPO_ROOT / "tests").rglob("*.psc"))
        self.assertEqual([], psc_files, f"unexpected .psc fixtures under tests/: {psc_files}")

    def test_privacy_guard_refuses_git_and_game_dirs(self) -> None:
        with self.assertRaises(f0.PrivacyError):
            f0.validate_output_dir(REPO_ROOT / "private-export")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Worktree-style .git file
            wt = tmp_path / "worktree"
            wt.mkdir()
            (wt / ".git").write_text("gitdir: /somewhere/else", encoding="utf-8")
            nested = wt / "sub" / "out"
            with self.assertRaises(f0.PrivacyError):
                f0.validate_output_dir(nested)

            # Game data root refusal
            game_data = tmp_path / "Fallout4Data"
            game_data.mkdir()
            with self.assertRaises(f0.PrivacyError):
                f0.validate_output_dir(game_data / "pack", forbidden_roots=(game_data,))

            # SteamLibrary path check
            steam_out = tmp_path / "SteamLibrary" / "common" / "out"
            with self.assertRaises(f0.PrivacyError):
                f0.validate_output_dir(steam_out)

            # External safe folder passes
            safe_out = tmp_path / "safe-fo4-ref"
            self.assertEqual(safe_out.resolve(), f0.validate_output_dir(safe_out, forbidden_roots=(game_data,)))

    def test_base_zip_extract_calls_spans_and_comments_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zpath = Path(tmp) / "Base.zip"
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("Fragments/Quests/QF_TestQuest_00000100.psc", SYNTHETIC_QF_PSC)

            zidx = f0.BaseZipIndex(zpath)
            entry = zidx.resolve_entry("Fragments:Quests:QF_TestQuest_00000100")
            self.assertEqual("Fragments/Quests/QF_TestQuest_00000100.psc", entry)

            lines = zidx.read_lines(entry)
            span = f0.find_function_span(lines, "Fragment_0")
            self.assertIsNotNone(span)
            s_ln, e_ln = span
            self.assertLess(s_ln, e_ln)
            self.assertIn("Function Fragment_0()", lines[s_ln - 1])
            self.assertIn("EndFunction", lines[e_ln - 1])

            analysis = f0.extract_script_calls_and_events(entry, lines)
            ev_names = {ev["event"] for ev in analysis["animation_events"]}
            self.assertEqual({"pipboyIdleRoot", "pipboyClamp", "KlaxonStop"}, ev_names)
            self.assertNotIn("CommentedOutEvent", ev_names)

            calls = analysis["calls"]
            for cat in (
                "RegisterForAnimationEvent",
                "WaitForAnimationEvent",
                "RegisterForRemoteEvent",
                "PlayAnimation",
                "PlayIdle",
                "Game",
                "MoveTo",
                "SetPosition",
                "Activate",
                "SetOpen",
                "Lock",
                "InputLayer",
            ):
                self.assertTrue(calls.get(cat), f"expected calls extracted for category {cat}")

            # Commented-out Game.FadeOutGame line (line 6) must not be extracted
            game_lines = {c["line"] for c in calls["Game"]}
            self.assertNotIn(6, game_lines)

    def test_scan_animations_ba2_returns_filenames_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ba2_path = Path(tmp) / "Test - Animations.ba2"
            hkx_a = b"\x00\x01HEADER\x00pipboyClamp\x00pipboyIdleRoot\x00TAIL"
            hkx_b = b"\x00\x01HEADER\x00Stage2\x00TAIL"
            ba2_path.write_bytes(
                _build_synthetic_gnrl_ba2(
                    [
                        ("Meshes\\Actors\\Character\\_1stPerson\\Animations\\Pipboy\\Activate.hkx", hkx_a),
                        ("Meshes\\Furniture\\Door\\Open.hkx", hkx_b),
                    ]
                )
            )
            found = f0.scan_animations_ba2(ba2_path, ["pipboyClamp", "pipboyIdleRoot", "MissingEvt"])
            self.assertEqual(
                [r"Meshes\Actors\Character\_1stPerson\Animations\Pipboy\Activate.hkx"],
                found["pipboyClamp"],
            )
            self.assertEqual(
                [r"Meshes\Actors\Character\_1stPerson\Animations\Pipboy\Activate.hkx"],
                found["pipboyIdleRoot"],
            )
            self.assertEqual([], found["MissingEvt"])

    def test_self_check_pass_and_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tpath = Path(tmp)
            zpath = tpath / "Base.zip"
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("Fragments/Quests/QF_TestQuest_00000100.psc", SYNTHETIC_QF_PSC)

            out_dir = tpath / "out"
            (out_dir / "quests").mkdir(parents=True)
            total_lines = len(SYNTHETIC_QF_PSC.splitlines())
            good_md = out_dir / "quests" / "TestQuest.md"
            good_md.write_text(
                f"# TestQuest (`Fallout4.esm 00000100`)\n"
                f"- Source: `Base.zip:Fragments/Quests/QF_TestQuest_00000100.psc:1-{total_lines}`\n"
                f"- Ref: `Fallout4.esm 0001F180`\n",
                encoding="utf-8",
            )
            (out_dir / "index.md").write_text("# Index\n", encoding="utf-8")

            valid_ids = {"00000100", "0001F180"}

            def fake_verify(ids):
                miss = [x for x in ids if x not in valid_ids]
                return len(ids) - len(miss), len(ids), miss

            res, tot, errs = f0.self_check_pack(out_dir, zpath, fake_verify)
            self.assertEqual([], errs)
            self.assertEqual(res, tot)
            self.assertEqual(3, tot)  # 1 zip span + 2 form ids

            # Inject broken zip path, OOB line range, and missing FormID
            bad_md = out_dir / "quests" / "BadQuest.md"
            bad_md.write_text(
                "- Missing: `Base.zip:NoSuch/Script.psc:1-5`\n"
                "- OOB: `Base.zip:Fragments/Quests/QF_TestQuest_00000100.psc:1-9999`\n"
                "- BadID: `Fallout4.esm DEADBEEF`\n",
                encoding="utf-8",
            )
            res2, tot2, errs2 = f0.self_check_pack(out_dir, zpath, fake_verify)
            self.assertEqual(3, len(errs2))
            self.assertEqual(3, res2)
            self.assertEqual(6, tot2)


if __name__ == "__main__":
    unittest.main()
