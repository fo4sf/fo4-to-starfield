"""Playing from the FO4SF game folder (docs/ai/fo4sf-instance.md steps 2 to 4): the folder's own Plugins.txt stands in
the player's place only while the game runs and the player's comes back byte for byte (also after a crash, from the
journal), its own Starfield.ini takes the saves path and the Papyrus keys, and our tools run on its own Plugins.txt.
Synthetic folders and a fake process table; no game."""
import base64
import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from fo4sf.launcher import crashwatch, files, instance, settings  # noqa: E402
from test_launcher_crashwatch import FakeSystem  # noqa: E402
from test_launcher_instance import GAME, plenty, write  # noqa: E402

PLAYER = b"# This file is used by Starfield to keep track of your downloaded content.\r\n*MyModPack.esm\r\n*Another.esp\r\n"
OURS = b"*FO4Port.esm\r\n*FO4TerrainCore.esm\r\n"


class FolderPlayTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = t.name
        src = os.path.join(self.root, "Steam", "Starfield")
        for rel, data in GAME.items():
            write(src, rel, data)
        self.folder = os.path.join(self.root, "FO4SF", "Starfield")
        instance.create(src, self.folder, disk_usage=plenty, say=lambda *_: None)
        self.local = os.path.join(self.root, "AppData", "Local")
        self.player = os.path.join(self.local, "Starfield", "Plugins.txt")
        write(self.local, "Starfield/Plugins.txt", PLAYER)
        write(instance.local_dir(self.folder), "Starfield/Plugins.txt", OURS)
        env = mock.patch.dict(os.environ, {"LOCALAPPDATA": self.local})
        env.start()
        self.addCleanup(env.stop)
        self.said = []

    def read(self, p):
        with open(p, "rb") as f:
            return f.read()

    # --- the swap -----------------------------------------------------------------------------------------------
    def test_swap_round_trip_puts_the_players_list_back_byte_for_byte(self):
        instance.swap_in(self.folder, self.player, self.said.append)
        self.assertEqual(self.read(self.player), OURS)                       # the game reads FO4SF's list
        backups = [n for n in os.listdir(instance.local_dir(self.folder)) if n.startswith("player-Plugins.txt.bak-")]
        self.assertEqual(len(backups), 1)                                    # a second copy, kept
        rewritten = b"*FO4TerrainCore.esm\r\n*FO4Port.esm\r\n"
        with open(self.player, "wb") as f:                                   # the game rewrites it at its start
            f.write(rewritten)
        self.assertTrue(instance.swap_out(self.folder, self.said.append))
        self.assertEqual(self.read(self.player), PLAYER)
        self.assertEqual(self.read(instance.plugins_txt(self.folder)), rewritten)   # FO4SF keeps the game's order
        self.assertFalse(os.path.exists(os.path.join(self.folder, instance.SWAP)))
        self.assertFalse(instance.swap_out(self.folder))                    # nothing left to put back

    def test_a_player_without_a_plugins_txt_gets_none_back(self):
        os.remove(self.player)
        instance.swap_in(self.folder, self.player, self.said.append)
        instance.swap_out(self.folder, self.said.append)
        self.assertFalse(os.path.exists(self.player))

    def test_a_left_journal_is_put_back_first_and_never_overwritten(self):
        instance.swap_in(self.folder, self.player, self.said.append)
        with self.assertRaisesRegex(instance.InstanceRefused, "left from an earlier start"):
            instance.swap_in(self.folder, self.player, self.said.append)
        with self.assertRaisesRegex(instance.InstanceRefused, "running"):
            instance.recover(self.folder, lambda: True, self.said.append)
        self.assertEqual(self.read(self.player), OURS)                       # left alone under a running game
        with open(self.player, "wb") as f:                                   # whoever rewrote it, it is kept aside
            f.write(b"*Unknown.esm\r\n")
        self.assertTrue(instance.recover(self.folder, lambda: False, self.said.append))
        self.assertEqual(self.read(self.player), PLAYER)
        self.assertEqual(self.read(instance.plugins_txt(self.folder)), OURS)  # a recovery never adopts a stranger's
        kept = [n for n in os.listdir(os.path.dirname(instance.plugins_txt(self.folder))) if ".after-" in n]
        self.assertEqual(len(kept), 1)
        self.assertFalse(instance.recover(self.folder, lambda: False, self.said.append))

    def test_a_kept_list_is_never_overwritten_and_a_retry_reuses_its_own(self):
        # #655 finding 3: the same second's name, with other bytes, gets -2; with the same bytes it is reused
        base = instance.plugins_txt(self.folder) + ".after-20261101-123456"
        os.makedirs(os.path.dirname(base), exist_ok=True)
        with open(base, "wb") as f:
            f.write(b"*Older.esm\r\n")
        self.assertEqual(instance._keep_after(base, b"*New.esm\r\n"), base + "-2")
        self.assertEqual(self.read(base), b"*Older.esm\r\n")
        self.assertEqual(instance._keep_after(base, b"*New.esm\r\n"), base + "-2")    # a retry: the same evidence
        self.assertEqual(instance._keep_after(base, b"*Older.esm\r\n"), base)
        self.assertEqual(instance._keep_after(base[:-1] + "9", b"*New.esm\r\n"), base + "-2")   # a later second too
        self.assertEqual(sorted(n for n in os.listdir(os.path.dirname(base)) if ".after-" in n),
                         [os.path.basename(base), os.path.basename(base) + "-2"])

    # --- the folder's own INI ------------------------------------------------------------------------------------
    def test_saves_go_to_their_own_folder_through_the_folders_ini(self):
        ini = os.path.join(self.folder, "Starfield.ini")
        instance.ensure_saves(self.folder, self.said.append)
        text = self.read(ini).decode()
        self.assertIn("[General]\r\nsLanguage=en\r\nSLocalSavePath=Saves\\FO4SF\\\r\n", text)   # CRLF kept
        before = self.read(ini)
        instance.ensure_saves(self.folder, self.said.append)
        self.assertEqual(self.read(ini), before)                             # once
        os.remove(ini)
        os.link(os.path.join(self.root, "Steam", "Starfield", "Starfield.ini"), ini)
        with self.assertRaisesRegex(instance.InstanceRefused, "hard-linked"):
            instance.ensure_saves(self.folder)                              # never through a link to Steam's file

    def test_set_ini_key(self):
        self.assertEqual(instance.set_ini_key("", "General", "A", "1"), ("[General]\nA=1\n", True))
        self.assertEqual(instance.set_ini_key("[general]\na=1\n", "General", "A", "1"), ("[general]\na=1\n", False))
        self.assertEqual(instance.set_ini_key("[General]\nA=0\r\n[Display]\nB=2", "General", "A", "1")[0],
                         "[General]\nA=1\r\n[Display]\nB=2")
        self.assertEqual(instance.set_ini_key("[Display]\nB=2", "General", "A", "1")[0], "[Display]\nB=2\n[General]\nA=1\n")
        self.assertEqual(instance.set_ini_key("[General]\nX=1\n[D]\n", "General", "A", "1")[0], "[General]\nX=1\nA=1\n[D]\n")

    # --- our tools on the folder ---------------------------------------------------------------------------------
    def test_run_gives_the_folder_its_own_plugins_txt_and_guards_the_target(self):
        seen = {}
        code = instance.run(self.folder, ["python", "exp_install.py", "install", "--starfield", self.folder],
                            call=lambda cmd, cwd, env: seen.update(env=env) or 0)
        self.assertEqual(code, 0)
        self.assertEqual(seen["env"]["LOCALAPPDATA"], instance.local_dir(self.folder))
        steam = os.path.join(self.root, "Steam", "Starfield")
        for cmd in (["x", "--starfield", steam], ["x", f"--starfield={steam}"]):
            with self.assertRaisesRegex(instance.InstanceRefused, "is not the FO4SF game folder"):
                instance.run(self.folder, cmd, call=lambda *a, **k: 0)
        with self.assertRaisesRegex(instance.InstanceRefused, "running"):
            instance.run(self.folder, ["x"], running=lambda: True, call=lambda *a, **k: 0)
        with self.assertRaisesRegex(instance.InstanceRefused, "not a finished FO4SF game folder"):
            instance.run(steam, ["x"], call=lambda *a, **k: 0)

    # --- play ----------------------------------------------------------------------------------------------------
    def values(self, **kw):
        v = settings.defaults()
        v.update({"instance": self.folder, "route": "exe", "load_order": "off"})
        v.update(kw)
        return v

    def game(self, rewrite=None, **kw):
        sys_ = FakeSystem([(4242, 0, 30, 0)], **kw)
        start = sys_.start_game

        def start_game(route, starfield):
            self.during = (self.read(self.player), starfield)
            if rewrite is not None:
                with open(self.player, "wb") as f:
                    f.write(rewrite)
            start(route, starfield)
        sys_.start_game = start_game
        return sys_

    def play(self, values, system):
        return crashwatch.play(values, "ignored", system=system, say=self.said.append, folder=self.folder)

    def test_play_starts_the_folder_with_its_list_and_gives_the_players_back(self):
        sys_ = self.game(rewrite=b"*FO4TerrainCore.esm\r\n*FO4Port.esm\r\n")
        r = self.play(self.values(papyrus_logging="on"), sys_)
        self.assertTrue(r["started"])
        self.assertEqual(self.during, (OURS, os.path.abspath(self.folder)))   # the folder, with FO4SF's list
        self.assertEqual(self.read(self.player), PLAYER)                    # and the player's back after it
        self.assertEqual(self.read(instance.plugins_txt(self.folder)), b"*FO4TerrainCore.esm\r\n*FO4Port.esm\r\n")
        ini = self.read(os.path.join(self.folder, "Starfield.ini")).decode()
        self.assertIn("bEnableLogging=1", ini)                               # Papyrus in the folder's own INI
        self.assertIn("SLocalSavePath=Saves\\FO4SF\\", ini)
        self.assertFalse(os.path.exists(os.path.join(self.folder, instance.SWAP)))

    def test_route_steam_is_refused_for_the_folder(self):
        with self.assertRaisesRegex(ValueError, "route=steam"):
            self.play(self.values(route="steam"), self.game())
        self.assertEqual(self.read(self.player), PLAYER)

    def test_a_start_that_fails_gives_the_players_list_back(self):
        sys_ = self.game()
        sys_.start_error = OSError(2, "not found")
        with self.assertRaisesRegex(ValueError, "could not start"):
            self.play(self.values(), sys_)
        self.assertEqual(self.read(self.player), PLAYER)
        self.assertFalse(os.path.exists(os.path.join(self.folder, instance.SWAP)))

    def test_a_game_still_running_keeps_the_swap_until_it_closes(self):
        sys_ = FakeSystem([])

        def pids(image=crashwatch.GAME_EXE):                                 # comes up just as the watch gives up
            return [4242] if sys_.started_at is not None and sys_.t - sys_.started_at >= 180 else []
        sys_.pids = pids
        r = self.play(self.values(), sys_)
        self.assertFalse(r["started"])
        self.assertTrue(os.path.exists(os.path.join(self.folder, instance.SWAP)))   # never swapped under a game
        self.assertEqual(self.read(self.player), OURS)
        self.assertTrue(any("comes back at the next launcher start" in s for s in self.said))
        self.assertTrue(instance.recover(self.folder, lambda: False, self.said.append))   # once it has closed
        self.assertEqual(self.read(self.player), PLAYER)

    def test_play_command_uses_the_setting_and_refuses_another_starfield(self):
        spec = importlib.util.spec_from_file_location("launcher_cli_play", os.path.join(ROOT, "scripts", "launcher.py"))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        path = os.path.join(self.root, "s.json")
        settings.save(path, self.values())
        with mock.patch.object(cli.crashwatch, "play", return_value={"dry_run": True}) as play, \
                mock.patch.object(cli.instance, "recover", return_value=False) as recover:
            self.assertEqual(cli.main(["play", "--settings", path, "--dry-run"]), 0)
            self.assertEqual(play.call_args.kwargs["folder"], self.folder)
            recover.assert_called_once()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["play", "--settings", path, "--starfield", self.root]), 2)
        with mock.patch.object(cli.instance, "run", return_value=0) as run:
            self.assertEqual(cli.main(["instance", "run", "--settings", path, "--", "python", "x.py", "--a"]), 0)
            self.assertEqual(run.call_args.args[1], ["python", "x.py", "--a"])

    def test_the_setting_frees_papyrus_from_my_games(self):
        v = self.values(papyrus_logging="on", bridge="off")
        self.assertEqual(settings.problems(v), [])
        v["instance"] = ""
        self.assertTrue(any("my_games" in p for p in settings.problems(v)))


if __name__ == "__main__":
    unittest.main()
