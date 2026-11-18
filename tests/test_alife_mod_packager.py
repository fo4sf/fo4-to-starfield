"""Standalone A-Life mod builder (scripts/alife/build_alife_mod.py): init, validate, simulate, the package output
refusal guard, verify-dist on a synthetic distribution folder, and log-audit on synthetic runtime log lines.
Synthetic only: nothing here needs the game, dotnet or the Papyrus compiler (the real package run is the verifier's
end-to-end check, docs/alife/STANDALONE-RELEASE-CHECKLIST.md)."""
import contextlib
import io
import json
import os
import shutil
import struct
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "alife"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import build_alife_mod as bam  # noqa: E402

try:
    from fo4sf.alife import sim_math  # noqa: F401
    HAVE_SIM = True
except ImportError:
    HAVE_SIM = False
VANILLA = os.path.join(ROOT, "src", "fo4sf", "alife", "presets", "vanilla_new_atlantis.json")


def run_cli(*argv):
    """(exit code, stdout, stderr) of build_alife_mod.main(argv)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = bam.main(list(argv))
    return rc, out.getvalue(), err.getvalue()


def synthetic_config(**over):
    """Two hostile factions on a four-node line: alpha base - relay - checkpoint - beta base."""
    cfg = {
        "schema_version": 1, "mod_name": "Synthetic A-Life", "plugin_name": "SynthALife.esm",
        "light_master": False, "masters": ["Starfield.esm"],
        "worldspace": {"plugin": "Starfield.esm", "form_id": "0x00012345", "editor_id": "SynthWorld",
                       "merge_offset_xy": [0.0, 0.0]},
        "simulation": {"default_enabled": True, "tick_real_s": 2.0, "offline_step_m_per_s": 1.35,
                       "online_spawn_radius_m": 450.0, "offline_despawn_radius_m": 620.0,
                       "waymarker_pool_size": 8, "max_active_squads": 6, "respawn_cooldown_s": 60.0,
                       "show_notifications": True},
        "factions": [
            {"id": "alpha", "index": 0, "name": "Alpha Company", "npc_template":
                {"plugin": "Starfield.esm", "form_id": "0x00001001"}, "player_relation": "ally",
             "relations": {"beta": "enemy"}, "squad_size": 4, "combat_power": 1.2},
            {"id": "beta", "index": 1, "name": "Beta Raiders", "npc_template":
                {"plugin": "Starfield.esm", "form_id": "0x00001002"}, "player_relation": "enemy",
             "relations": {"alpha": "enemy"}, "squad_size": 3, "combat_power": 1.0},
        ],
        "nodes": [
            {"index": 0, "id": "alpha_base", "kind": "base", "x": 0.0, "y": 0.0, "z": 10.0, "capacity": 3,
             "initial_owner": 0, "spawn_faction": 0},
            {"index": 1, "id": "crossroads", "kind": "relay", "x": 300.0, "y": 0.0, "z": 10.0, "capacity": 0,
             "initial_owner": -1, "spawn_faction": -1},
            {"index": 2, "id": "gate", "kind": "checkpoint", "x": 600.0, "y": 50.0, "z": 12.0, "capacity": 2,
             "initial_owner": -1, "spawn_faction": -1},
            {"index": 3, "id": "beta_base", "kind": "base", "x": 900.0, "y": 0.0, "z": 8.0, "capacity": 3,
             "initial_owner": 1, "spawn_faction": 1},
        ],
        "edges": [{"u": 0, "v": 1, "len_m": 300.0}, {"u": 1, "v": 2, "len_m": 305.0},
                  {"u": 2, "v": 3, "len_m": 305.0}],
    }
    cfg.update(over)
    return cfg


def tes4(masters, flags=bam.TES4_MASTER):
    """A synthetic Starfield TES4 header record (HEDR, CNAM, MAST/DATA pairs)."""
    def sub(sig, data):
        return sig + struct.pack("<H", len(data)) + data
    body = sub(b"HEDR", struct.pack("<fII", 0.96, 12, 0x800 + 12)) + sub(b"CNAM", b"synthetic\0")
    for m in masters:
        body += sub(b"MAST", m.encode() + b"\0") + sub(b"DATA", bytes(8))
    return b"TES4" + struct.pack("<IIIIHH", len(body), flags, 0, 0, 0x210, 0) + body


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="alife_pkg_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write_cfg(self, cfg, name="alife_config.json"):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
        return path


class InitTest(Tmp):
    def setUp(self):
        super().setUp()
        if not os.path.isfile(VANILLA):
            self.skipTest("vanilla preset not present yet")

    def test_vanilla_starter_is_commented_and_valid(self):
        out = os.path.join(self.tmp, "cfg", "alife_config.json")
        rc, text, _ = run_cli("init", "--out", out)
        self.assertEqual(rc, 0, text)
        with open(out, encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertIn("_comment", cfg)
        self.assertEqual(cfg["masters"], ["Starfield.esm"])
        rc, text, _ = run_cli("validate", "--config", out)
        self.assertEqual(rc, 0, text)
        self.assertIn("validate: ok", text)
        self.assertIn("standalone: Starfield.esm only", text)

    def test_custom_template_targets_a_custom_worldspace_master(self):
        out = os.path.join(self.tmp, "custom.json")
        self.assertEqual(run_cli("init", "--out", out, "--template", "custom")[0], 0)
        rc, text, _ = run_cli("validate", "--config", out, "--json")
        rep = json.loads(text)
        self.assertEqual(rc, 0, rep["problems"])
        self.assertEqual(rep["worldspace"]["plugin"], "MyWorldspace.esm")
        self.assertEqual(rep["masters"]["expected"], ["Starfield.esm", "MyWorldspace.esm"])
        self.assertFalse(rep["masters"]["standalone"])

    def test_refuses_to_overwrite_without_force(self):
        out = self.write_cfg({"keep": True}, "existing.json")
        rc, _, err = run_cli("init", "--out", out)
        self.assertEqual(rc, 2)
        self.assertIn("exists", err)
        with open(out, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"keep": True})
        self.assertEqual(run_cli("init", "--out", out, "--force")[0], 0)


class ValidateTest(Tmp):
    def test_report_headroom_connectivity_relations_masters(self):
        rc, text, _ = run_cli("validate", "--config", self.write_cfg(synthetic_config()), "--json")
        rep = json.loads(text)
        self.assertEqual(rc, 0, rep["problems"])
        g = rep["graph"]
        self.assertEqual((g["nodes"], g["edges"], g["node_headroom"], g["edge_headroom"]), (4, 3, 124, 125))
        self.assertTrue(g["connected"])
        self.assertEqual(g["kinds"], {"base": 2, "relay": 1, "checkpoint": 1})
        self.assertEqual(g["garrison_capacity"], 8)
        self.assertEqual(rep["factions"], ["alpha", "beta"])
        self.assertEqual(rep["relations"], [["self", "enemy"], ["enemy", "self"]])
        self.assertEqual(rep["player_relation"], {"alpha": "ally", "beta": "enemy"})
        self.assertEqual(rep["masters"]["expected"], ["Starfield.esm"])
        self.assertTrue(rep["masters"]["standalone"])
        self.assertEqual(rep["spawn_nodes"], 2)

    def test_text_report_shows_headroom(self):
        rc, text, _ = run_cli("validate", "--config", self.write_cfg(synthetic_config()))
        self.assertEqual(rc, 0, text)
        self.assertIn("4/128 (124 free)", text)
        self.assertIn("3/128 (125 free)", text)
        self.assertIn("faction relations", text)

    def test_one_sided_relation_reads_both_ways(self):
        cfg = synthetic_config()
        cfg["factions"][1]["relations"] = {}
        rep = json.loads(run_cli("validate", "--config", self.write_cfg(cfg), "--json")[1])
        self.assertEqual(rep["relations"], [["self", "enemy"], ["enemy", "self"]])

    def test_disconnected_graph_fails(self):
        cfg = synthetic_config(edges=[{"u": 0, "v": 1, "len_m": 300.0}, {"u": 2, "v": 3, "len_m": 305.0}])
        rc, text, _ = run_cli("validate", "--config", self.write_cfg(cfg), "--json")
        rep = json.loads(text)
        self.assertEqual(rc, 1)
        self.assertFalse(rep["valid"])
        self.assertFalse(rep["graph"]["connected"])
        self.assertEqual(rep["graph"]["components"], 2)

    def test_undeclared_template_plugin_fails(self):
        cfg = synthetic_config()
        cfg["factions"][1]["npc_template"] = {"plugin": "OtherMod.esm", "form_id": "0x000801"}
        rc, text, _ = run_cli("validate", "--config", self.write_cfg(cfg), "--json")
        rep = json.loads(text)
        self.assertEqual(rc, 1)
        self.assertEqual(rep["masters"]["undeclared"], ["OtherMod.esm"])

    def test_declared_extra_master_is_carried_only_when_referenced(self):
        cfg = synthetic_config(masters=["Starfield.esm", "Unused.esm", "OtherMod.esm"])
        cfg["factions"][1]["npc_template"] = {"plugin": "OtherMod.esm", "form_id": "0x000801"}
        rep = json.loads(run_cli("validate", "--config", self.write_cfg(cfg), "--json")[1])
        self.assertTrue(rep["valid"], rep["problems"])
        self.assertEqual(rep["masters"]["expected"], ["Starfield.esm", "OtherMod.esm"])
        self.assertEqual(rep["masters"]["unused_declared"], ["Unused.esm"])

    def test_comment_keys_are_ignored(self):
        cfg = synthetic_config(_comment="note")
        cfg["nodes"][0]["_why"] = "spawn point"
        self.assertEqual(run_cli("validate", "--config", self.write_cfg(cfg))[0], 0)

    def test_unreadable_config_is_refused(self):
        path = os.path.join(self.tmp, "bad.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{not json")
        self.assertEqual(run_cli("validate", "--config", path)[0], 2)


@unittest.skipUnless(HAVE_SIM, "fo4sf.alife.sim_math not present yet")
class SimulateTest(Tmp):
    def test_summary_table_and_json_are_deterministic(self):
        cfg = self.write_cfg(synthetic_config())
        j1, j2 = os.path.join(self.tmp, "a.json"), os.path.join(self.tmp, "b.json")
        rc, text, _ = run_cli("simulate", "--config", cfg, "--ticks", "300", "--seed", "7", "--json-out", j1)
        self.assertEqual(rc, 0, text)
        for label in ("squads spawned", "edges traversed", "offline battles", "territory captures",
                      "garrison utilization"):
            self.assertIn(label, text)
        self.assertEqual(run_cli("simulate", "--config", cfg, "--ticks", "300", "--seed", "7",
                                 "--json-out", j2)[0], 0)
        with open(j1, encoding="utf-8") as f:
            r1 = json.load(f)
        with open(j2, encoding="utf-8") as f:
            r2 = json.load(f)
        self.assertEqual(r1, r2)
        for key in ("squads_spawned", "edges_traversed", "battles", "captures", "garrison_utilization"):
            self.assertIn(key, r1)
        self.assertGreater(r1["squads_spawned"], 0)
        self.assertTrue(0.0 <= r1["garrison_utilization"] <= 1.0)

    def test_invalid_config_is_not_simulated(self):
        cfg = synthetic_config(edges=[{"u": 0, "v": 1, "len_m": 300.0}])
        rc, _, err = run_cli("simulate", "--config", self.write_cfg(cfg))
        self.assertEqual(rc, 2)
        self.assertIn("not valid", err)


class RefusalTest(Tmp):
    def assert_refused(self, out, why, starfield=None):
        with self.assertRaises(bam.Refused) as cm:
            bam.refuse_out(out, starfield)
        self.assertIn(why, str(cm.exception))
        parent = os.path.dirname(os.path.abspath(out))
        if os.path.isdir(parent):
            self.assertFalse([n for n in os.listdir(parent) if ".partial-" in n])

    def test_inside_this_repository(self):
        self.assert_refused(os.path.join(ROOT, "dist", "mymod"), "Git worktree")

    def test_inside_any_git_worktree_folder_or_file(self):
        repo = os.path.join(self.tmp, "otherrepo")
        os.makedirs(os.path.join(repo, ".git"))
        self.assert_refused(os.path.join(repo, "sub", "dist"), "Git worktree")
        wt = os.path.join(self.tmp, "worktree")
        os.makedirs(wt)
        with open(os.path.join(wt, ".git"), "w") as f:
            f.write("gitdir: elsewhere\n")
        self.assert_refused(os.path.join(wt, "dist"), "Git worktree")

    def test_inside_a_game_installation(self):
        game = os.path.join(self.tmp, "Games", "Starfield")
        os.makedirs(os.path.join(game, "Data"))
        open(os.path.join(game, "Starfield.exe"), "wb").close()
        self.assert_refused(os.path.join(game, "Data", "mymod"), "game installation")
        other = os.path.join(self.tmp, "Games", "OtherGame")
        os.makedirs(os.path.join(other, "Data"))
        open(os.path.join(other, "Data", "Starfield.esm"), "wb").close()
        self.assert_refused(os.path.join(other, "out"), "game installation")

    def test_inside_the_given_starfield_dir_or_a_store_library(self):
        sf = os.path.join(self.tmp, "anywhere")
        os.makedirs(sf)
        self.assert_refused(os.path.join(sf, "dist"), "game installation", starfield=sf)
        self.assert_refused(os.path.join(self.tmp, "Library", "steamapps", "common", "x"), "game installation")
        self.assert_refused(os.path.join(self.tmp, "XboxGames", "Starfield", "Content", "x"), "game installation")

    def test_existing_out_is_refused(self):
        out = os.path.join(self.tmp, "dist")
        os.makedirs(out)
        self.assert_refused(out, "exists")

    def test_clean_folder_is_accepted(self):
        bam.refuse_out(os.path.join(self.tmp, "dist", "mymod"), os.path.join(self.tmp, "Starfield"))

    def test_package_cli_refuses_before_any_work(self):
        game = os.path.join(self.tmp, "Starfield")
        os.makedirs(os.path.join(game, "Data"))
        open(os.path.join(game, "Starfield.exe"), "wb").close()
        cfg = self.write_cfg(synthetic_config())
        for out in (os.path.join(ROOT, "build", "alife-dist"), os.path.join(game, "Data", "alife")):
            rc, text, err = run_cli("package", "--config", cfg, "--out", out, "--starfield-dir", game)
            self.assertEqual(rc, 2, text)
            self.assertIn("package refused", err)
            self.assertFalse(os.path.exists(out))
        self.assertEqual(sorted(os.listdir(os.path.join(game, "Data"))), [])


class VerifyDistTest(Tmp):
    PLUGIN = "SynthALife.esm"

    def make_dist(self, masters=("Starfield.esm",), flags=bam.TES4_MASTER, ba2=False, light=False,
                  manifest_masters=None):
        dist = os.path.join(self.tmp, "dist")
        os.makedirs(os.path.join(dist, "Data", "Scripts"))
        with open(os.path.join(dist, "Data", self.PLUGIN), "wb") as f:
            f.write(tes4(masters, flags))
        pex = {s: bam.PEX_MAGIC + bytes([3, 2, 1, 0]) + s.encode() for s in bam.SCRIPTS}
        ba2_name = None
        if ba2:
            import ba2_fixture
            os.rmdir(os.path.join(dist, "Data", "Scripts"))
            ba2_name = "SynthALife - Main.ba2"
            with open(os.path.join(dist, "Data", ba2_name), "wb") as f:
                f.write(ba2_fixture.general_archive({f"Scripts\\{s}.pex": b for s, b in pex.items()}))
        else:
            for s, b in pex.items():
                with open(os.path.join(dist, "Data", "Scripts", s + ".pex"), "wb") as f:
                    f.write(b)
        with open(os.path.join(dist, bam.SNIPPET), "w") as f:
            f.write(f"*{self.PLUGIN}\n")
        with open(os.path.join(dist, bam.README), "w") as f:
            f.write("synthetic\n")
        bam.write_manifest(dist, {"mod_name": "Synthetic", "plugin": self.PLUGIN,
                                  "masters": list(manifest_masters or masters), "light_master": light,
                                  "scripts": list(bam.SCRIPTS), "ba2": ba2_name})
        return dist

    def test_clean_loose_dist_verifies(self):
        dist = self.make_dist()
        self.assertEqual(bam.verify_dist(dist), [])
        rc, text, _ = run_cli("verify-dist", "--dist-dir", dist)
        self.assertEqual(rc, 0, text)
        self.assertIn("verify-dist: ok", text)

    def test_clean_ba2_dist_verifies(self):
        self.assertEqual(bam.verify_dist(self.make_dist(ba2=True)), [])

    def test_manifest_has_no_machine_paths(self):
        dist = self.make_dist()
        with open(os.path.join(dist, bam.MANIFEST), encoding="utf-8") as f:
            text = f.read()
        self.assertNotIn(self.tmp, text)
        self.assertNotIn("\\\\", text)
        self.assertEqual(sorted(json.loads(text)["files"]),
                         sorted([f"Data/{self.PLUGIN}", bam.SNIPPET, bam.README] +
                                [f"Data/Scripts/{s}.pex" for s in bam.SCRIPTS]))

    def test_tampered_file_fails(self):
        dist = self.make_dist()
        with open(os.path.join(dist, "Data", "Scripts", bam.SCRIPTS[0] + ".pex"), "ab") as f:
            f.write(b"x")
        p = bam.verify_dist(dist)
        self.assertTrue(any("sha256" in x for x in p), p)
        self.assertEqual(run_cli("verify-dist", "--dist-dir", dist)[0], 1)

    def test_unlisted_and_missing_files_fail(self):
        dist = self.make_dist()
        open(os.path.join(dist, "Data", "extra.esp"), "wb").close()
        os.remove(os.path.join(dist, "Data", "Scripts", bam.SCRIPTS[2] + ".pex"))
        p = bam.verify_dist(dist)
        self.assertTrue(any("not in the manifest" in x for x in p), p)
        self.assertTrue(any(bam.SCRIPTS[2] in x and "missing" in x for x in p), p)

    def test_master_list_and_flags(self):
        p = bam.verify_dist(self.make_dist(masters=("Starfield.esm", "Extra.esm"),
                                           manifest_masters=("Starfield.esm",)))
        self.assertTrue(any("masters" in x for x in p), p)
        shutil.rmtree(os.path.join(self.tmp, "dist"))
        p = bam.verify_dist(self.make_dist(flags=0))
        self.assertTrue(any("Master flag" in x for x in p), p)
        shutil.rmtree(os.path.join(self.tmp, "dist"))
        p = bam.verify_dist(self.make_dist(light=True))
        self.assertTrue(any("Small" in x for x in p), p)
        shutil.rmtree(os.path.join(self.tmp, "dist"))
        self.assertEqual(bam.verify_dist(self.make_dist(light=True, flags=bam.TES4_MASTER | bam.TES4_SMALL)), [])

    def test_non_pex_script_fails(self):
        dist = self.make_dist()
        path = os.path.join(dist, "Data", "Scripts", bam.SCRIPTS[1] + ".pex")
        with open(path, "wb") as f:
            f.write(b"not a pex")
        man_path = os.path.join(dist, bam.MANIFEST)
        with open(man_path, encoding="utf-8") as f:
            man = json.load(f)
        os.remove(man_path)
        bam.write_manifest(dist, {k: v for k, v in man.items() if k not in ("files", "kind", "manifest_version")})
        p = bam.verify_dist(dist)
        self.assertEqual(len(p), 1, p)
        self.assertIn("not a compiled Papyrus script", p[0])

    def test_snippet_and_manifest_problems(self):
        dist = self.make_dist()
        with open(os.path.join(dist, bam.SNIPPET), "w") as f:
            f.write("*Other.esm\n")
        self.assertTrue(any(bam.SNIPPET in x for x in bam.verify_dist(dist)))
        os.remove(os.path.join(dist, bam.MANIFEST))
        self.assertEqual(bam.verify_dist(dist), [f"{bam.MANIFEST} missing"])

    def test_tes4_reader(self):
        path = os.path.join(self.tmp, "x.esm")
        with open(path, "wb") as f:
            f.write(tes4(["Starfield.esm", "A.esm"], bam.TES4_MASTER | bam.TES4_SMALL))
        h = bam.read_tes4(path)
        self.assertEqual(h["masters"], ["Starfield.esm", "A.esm"])
        self.assertTrue(h["master_flag"] and h["small_flag"])
        self.assertEqual(h["hedr_records"], 12)
        with open(path, "wb") as f:
            f.write(b"TES3" + bytes(40))
        with self.assertRaises(ValueError):
            bam.read_tes4(path)

    def test_scrub_paths(self):
        s = bam.scrub_paths("check ok: " + "D:" + "\\Games\\Data\\Starfield.esm and /opt/build/x/SynthALife.esm")
        self.assertEqual(s, "check ok: Starfield.esm and SynthALife.esm")


LOG = """\
[11/18/2026 - 06:00:00AM] ALIFE_MOD rt=0.00 step=init squads=0 nodes=4 edges=3
[11/18/2026 - 06:00:01AM] ALIFE_MOD rt=0.50 step=options enabled=1 max=6 notify=1
[11/18/2026 - 06:00:02AM] ALIFE_MOD rt=2.00 step=squad_spawn squad=0 faction=alpha node=0 members=4
[11/18/2026 - 06:00:02AM] ALIFE_MOD rt=2.00 step=squad_spawn squad=1 faction=beta node=3 members=3
[11/18/2026 - 06:00:04AM] ALIFE_MOD rt=4.00 step=order squad=0 order=raid goal=2
[11/18/2026 - 06:00:30AM] ALIFE_MOD rt=30.0 step=materialize squad=0 members=4
[11/18/2026 - 06:01:30AM] ALIFE_MOD rt=90.0 step=dematerialize squad=0 members=3
[11/18/2026 - 06:02:00AM] ALIFE_MOD rt=120.0 step=battle node=2 squad=0 faction=alpha loser=1
[11/18/2026 - 06:02:10AM] ALIFE_MOD rt=130.0 step=battle_end node=2 winner=alpha loser=beta
[11/18/2026 - 06:02:10AM] ALIFE_MOD rt=130.0 step=squad_defeated squad=1 faction=beta
[11/18/2026 - 06:02:12AM] ALIFE_MOD rt=132.0 step=capture node=2 owner_from=-1 owner_to=alpha squad=0
[11/18/2026 - 06:02:14AM] Some other mod's line step=error
[11/18/2026 - 06:03:00AM] ALIFE_MOD rt=0.10 step=load_game squads=1
[11/18/2026 - 06:03:01AM] ALIFE_MOD rt=1.00 step=replenish squad=0 faction=alpha members=4
"""


class LogAuditTest(Tmp):
    def write_log(self, text):
        path = os.path.join(self.tmp, "StarfieldALife.0.log")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_counts_every_event_kind(self):
        rc, text, _ = run_cli("log-audit", "--file", self.write_log(LOG), "--json")
        res = json.loads(text)
        self.assertEqual(rc, 0, res)
        c = res["counts"]
        self.assertEqual(res["alife_lines"], 13)
        self.assertEqual((c["init"], c["load"], c["spawn"], c["replenish"]), (1, 1, 2, 1))
        self.assertEqual((c["materialize"], c["dematerialize"], c["battle"], c["battle_end"]), (1, 1, 1, 1))
        self.assertEqual((c["capture"], c["squad_dead"], c["error"]), (1, 1, 0))
        self.assertEqual(res["captures_by_faction"], {"alpha": 1})
        self.assertEqual(res["spawns_by_faction"], {"alpha": 1, "beta": 1})
        self.assertEqual(res["sessions"], 2)
        self.assertEqual(res["rt_backwards"], 0)          # the load rebased rt: a new session, not a regression
        self.assertEqual(res["max_squads_online"], 1)
        self.assertEqual(res["unknown_steps"], {"options": 1, "order": 1})

    def test_text_table(self):
        rc, text, _ = run_cli("log-audit", "--file", self.write_log(LOG))
        self.assertEqual(rc, 0, text)
        self.assertIn("3D materializations", text)
        self.assertIn("log-audit: ok", text)

    def test_error_line_fails(self):
        path = self.write_log(LOG + "[x] ALIFE_MOD rt=2.00 step=error what=no_waymarker squad=0\n")
        rc, text, _ = run_cli("log-audit", "--file", path, "--json")
        res = json.loads(text)
        self.assertEqual(rc, 1)
        self.assertEqual(res["error_count"], 1)
        self.assertEqual(res["errors"][0]["kv"]["what"], "no_waymarker")

    def test_empty_or_initless_log_fails(self):
        self.assertEqual(run_cli("log-audit", "--file", self.write_log("nothing here\n"))[0], 1)
        rc, text, _ = run_cli("log-audit", "--file",
                              self.write_log("[x] ALIFE_MOD rt=1.0 step=squad_spawn squad=0 faction=a\n"), "--json")
        self.assertEqual(rc, 1)
        self.assertFalse(json.loads(text)["criteria"]["has_init"])

    def test_time_regression_and_unmatched_dematerialize_are_reported(self):
        log = ("[x] ALIFE_MOD rt=5.0 step=init\n[x] ALIFE_MOD rt=9.0 step=tick\n"
               "[x] ALIFE_MOD rt=3.0 step=dematerialize squad=4\n")
        res = json.loads(run_cli("log-audit", "--file", self.write_log(log), "--json")[1])
        self.assertEqual(res["rt_backwards"], 1)
        self.assertEqual(res["dematerialize_without_materialize"], 1)


if __name__ == "__main__":
    unittest.main()
