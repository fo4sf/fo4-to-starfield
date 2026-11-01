"""The FO4SF game folder (src/fo4sf/launcher/instance.py) made from a synthetic Starfield folder: hard links for the game's
files, copies of the game folder's INIs, only the game's own files in Data, nothing written in the source, nothing
overwritten, and a stopped run goes on. No game."""
import contextlib
import hashlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf.launcher import files, instance  # noqa: E402

GAME = {
    "Starfield.exe": b"MZ game",
    "steam_api64.dll": b"MZ steam",
    "sfse_loader.exe": b"MZ sfse",
    "Starfield.ini": b"[General]\r\nsLanguage=en\r\n",
    "Ultra.ini": b"[Display]\r\n",
    "Tools/Archive2/Archive2.exe": b"MZ archive2",
    "Data/Starfield.esm": b"TES4 sf",
    "Data/Starfield - Textures01.ba2": b"BTDX tex",
    "Data/Constellation.esm": b"TES4 cons",
    "Data/Constellation - Localization.ba2": b"BTDX loc",
    "Data/SFBGS003.esm": b"TES4 003",
    "Data/SFBGS003 - Main.ba2": b"BTDX 003",
    "Data/BlueprintShips-Starfield.esm": b"TES4 bp",
    "Data/BlueprintShips-Starfield - Localization.ba2": b"BTDX bploc",
}
MODS = {                                        # the player's mod pack and our installs: never in the FO4SF folder
    "Data/SomeOwnerMod.esm": b"TES4 mod",
    "Data/SomeOwnerMod - Main.ba2": b"BTDX mod",
    "Data/FO4Port.esm": b"TES4 port",
    "Data/FO4Port.deploy.json": b"{}",
    "Data/textures/loose.dds": b"DDS ",
    "Data/SFSE/Plugins/SomeOwnerPlugin.dll": b"MZ plug",
}


def write(root, rel, data):
    p = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)


def digest_tree(root):
    out = {}
    for d, _dirs, names in os.walk(root):
        for n in names:
            p = os.path.join(d, n)
            with open(p, "rb") as f:
                out[os.path.relpath(p, root)] = (hashlib.sha256(f.read()).hexdigest(), os.stat(p).st_mtime_ns)
    return out


def plenty(_path):
    return SimpleNamespace(free=500 * 1024 ** 3)


class InstanceTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = t.name
        self.src = os.path.join(self.root, "SteamLibrary", "steamapps", "common", "Starfield")
        for rel, data in {**GAME, **MODS}.items():
            write(self.src, rel, data)
        self.dst = os.path.join(self.root, "FO4SF", "Starfield")

    def create(self, **kw):
        kw.setdefault("disk_usage", plenty)
        kw.setdefault("say", lambda *_: None)
        return instance.create(self.src, self.dst, **kw)

    def test_plan_links_the_game_copies_its_inis_and_leaves_the_mods_out(self):
        p = instance.plan(self.src, self.dst)
        self.assertEqual(sorted(p["copy"]), ["Starfield.ini", "Ultra.ini"])
        self.assertEqual(sorted(p["link"]), sorted(r for r in GAME if not r.endswith(".ini")))
        self.assertEqual(sorted(p["left_out"]), ["Data/FO4Port.deploy.json", "Data/FO4Port.esm", "Data/SFSE/",
                                                 "Data/SomeOwnerMod - Main.ba2", "Data/SomeOwnerMod.esm", "Data/textures/"])
        self.assertTrue(any("left out of Data" in line for line in instance.summary(p)))

    def test_create_makes_links_and_copies_and_never_writes_in_the_source(self):
        before = digest_tree(self.src)
        self.create()
        self.assertEqual(digest_tree(self.src), before)                      # the Steam install is untouched
        for rel in GAME:
            src, dst = os.path.join(self.src, *rel.split("/")), os.path.join(self.dst, *rel.split("/"))
            with open(dst, "rb") as f:
                self.assertEqual(f.read(), GAME[rel])
            self.assertEqual(os.path.samefile(src, dst), not rel.endswith(".ini"), rel)
        for rel in MODS:
            self.assertFalse(os.path.exists(os.path.join(self.dst, *rel.split("/"))), rel)
        with open(os.path.join(self.dst, "Starfield.ini"), "ab") as f:      # the FO4SF folder's settings are its own
            f.write(b"SLocalSavePath=Saves\\FO4SF\\\r\n")
        with open(os.path.join(self.src, "Starfield.ini"), "rb") as f:
            self.assertEqual(f.read(), GAME["Starfield.ini"])
        rec = files.load_json(os.path.join(self.dst, instance.RECORD))
        self.assertTrue(rec["complete"])
        self.assertEqual(os.path.normcase(rec["source"]), os.path.normcase(os.path.abspath(self.src)))

    def test_a_kept_data_folder_comes_along(self):
        p = instance.plan(self.src, self.dst, keep_data_dirs=["Textures"])
        self.assertIn("Data/textures/loose.dds", p["link"])
        self.assertNotIn("Data/textures/", p["left_out"])

    def test_a_stopped_run_goes_on_and_a_rerun_changes_nothing(self):
        calls = []

        def stop_after_three(src, dst):
            if len(calls) == 3:
                raise OSError("power cut")
            calls.append(dst)
            os.link(src, dst)
        with self.assertRaises(OSError):
            self.create(link=stop_after_three)
        self.assertFalse(files.load_json(os.path.join(self.dst, instance.RECORD))["complete"])
        self.create()
        self.assertTrue(files.load_json(os.path.join(self.dst, instance.RECORD))["complete"])
        before = digest_tree(self.dst)
        self.create()
        after = digest_tree(self.dst)
        self.assertEqual(after.pop(instance.RECORD)[0], before.pop(instance.RECORD)[0])   # rewritten, same content
        self.assertEqual(after, before)                                    # every game file as it was

    def test_a_file_that_is_not_the_games_is_never_overwritten(self):
        self.create()
        exe = os.path.join(self.dst, "Starfield.exe")
        os.remove(exe)
        write(self.dst, "Starfield.exe", b"MZ something else")
        with self.assertRaisesRegex(instance.InstanceRefused, "not the game's file"):
            self.create()
        with open(exe, "rb") as f:
            self.assertEqual(f.read(), b"MZ something else")

    def test_refusals_before_anything_is_written(self):
        cases = [
            (os.path.join(self.src, "FO4SF"), "outside the Starfield install"),
            (os.path.join(self.root, "SteamLibrary", "steamapps", "FO4SF"), "steamapps"),
            (os.path.join(self.root, "OneDrive", "FO4SF"), "onedrive"),
        ]
        for target, text in cases:
            with self.subTest(target=target):
                with self.assertRaisesRegex(instance.InstanceRefused, text):
                    instance.create(self.src, target, disk_usage=plenty, say=lambda *_: None)
                self.assertFalse(os.path.exists(os.path.join(target, instance.RECORD)))
        busy = os.path.join(self.root, "busy")
        write(busy, "notes.txt", b"mine")
        with self.assertRaisesRegex(instance.InstanceRefused, "not empty"):
            instance.create(self.src, busy, disk_usage=plenty)
        with self.assertRaisesRegex(instance.InstanceRefused, "GB would be left free"):
            self.create(disk_usage=lambda _p: SimpleNamespace(free=10 * 1024 ** 3))
        with self.assertRaisesRegex(instance.InstanceRefused, "not a Starfield game folder"):
            instance.plan(os.path.join(self.root, "nothing"), self.dst)

    def test_another_drive_is_refused(self):
        from unittest import mock
        devices = {os.path.abspath(self.src): 1, os.path.abspath(self.root): 2}
        with mock.patch.object(instance, "_device", side_effect=lambda p: devices[os.path.abspath(p)]):
            with self.assertRaisesRegex(instance.InstanceRefused, "another drive"):
                instance.check_target(self.src, os.path.join(self.root, "new"), 40, 0, plenty)

    def test_a_folder_made_from_another_install_is_refused(self):
        self.create()
        other = os.path.join(self.root, "Other", "Starfield")
        for rel, data in GAME.items():
            write(other, rel, data)
        with self.assertRaisesRegex(instance.InstanceRefused, "was made from"):
            instance.create(other, self.dst, disk_usage=plenty)

    def symlink(self, link, target):
        try:
            os.symlink(target, link, target_is_directory=True)
        except (OSError, NotImplementedError) as e:          # Windows without the symlink right
            self.skipTest(f"no directory symlinks here: {e}")

    def test_a_link_inside_the_folder_is_refused_before_anything_is_written_through_it(self):
        # #655 finding 1, with a POSIX symlink in place of the NTFS junction (tests/test_launcher_instance_windows_safety.py)
        exterior = os.path.join(self.root, "exterior")
        os.makedirs(exterior)
        os.makedirs(self.dst)
        files.save_json(os.path.join(self.dst, instance.RECORD),
                        {"schema": 1, "source": os.path.abspath(self.src), "made": [], "complete": False})
        self.symlink(os.path.join(self.dst, "Data"), exterior)
        with self.assertRaisesRegex(instance.InstanceRefused, "link or junction inside the FO4SF folder"):
            self.create()
        self.assertEqual(os.listdir(exterior), [])
        self.assertFalse(os.path.exists(os.path.join(self.dst, "Starfield.exe")))   # refused before the first file

    def test_a_link_that_appears_during_the_run_is_refused_at_that_file(self):
        exterior = os.path.join(self.root, "exterior")
        os.makedirs(exterior)
        made = []

        def link_then_plant(src, dst):
            os.link(src, dst)
            made.append(dst)
            if len(made) == 1:                              # after the first file: a link where Data will go
                self.symlink(os.path.join(self.dst, "Data"), exterior)
        with self.assertRaisesRegex(instance.InstanceRefused, "is a link or junction"):
            self.create(link=link_then_plant)
        self.assertEqual(os.listdir(exterior), [])

    def test_an_alias_of_a_steam_library_is_refused(self):
        # #655 finding 2: the denylist sees the resolved path, not only the spelling given
        alias = os.path.join(self.root, "library-alias")
        self.symlink(alias, os.path.join(self.root, "SteamLibrary", "steamapps", "common"))
        target = os.path.join(alias, "FO4SF")
        with self.assertRaisesRegex(instance.InstanceRefused, "steamapps"):
            instance.check_target(self.src, target, 0, 0, plenty)
        self.assertFalse(os.path.lexists(target))

    def test_cli_plan_and_create(self):
        spec = importlib.util.spec_from_file_location("launcher_cli_inst", os.path.join(ROOT, "scripts", "launcher.py"))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(cli.main(["instance", "plan", "--starfield", self.src, "--at", self.dst,
                                       "--min-free-gb", "0"]), 0)
        self.assertIn("plan only", out.getvalue())
        self.assertFalse(os.path.exists(self.dst))                          # plan writes nothing
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["instance", "create", "--starfield", self.src, "--at", self.dst,
                                       "--min-free-gb", "0"]), 0)
            self.assertEqual(cli.main(["instance", "create", "--starfield", self.src,
                                       "--at", os.path.join(self.src, "x"), "--min-free-gb", "0"]), 2)
        self.assertTrue(os.path.isfile(os.path.join(self.dst, instance.RECORD)))


if __name__ == "__main__":
    unittest.main()
