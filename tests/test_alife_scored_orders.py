"""Tests for X7 A-Life scored-orders offline prototype (schema, sim_math, CLI, 25+ seed benchmark, doc hygiene)."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fo4sf.alife import schema, sim_math  # noqa: E402

CLI_SCRIPT = REPO_ROOT / "scripts" / "alife" / "build_alife_mod.py"
BETTER_METHODS_DOC = REPO_ROOT / "docs" / "alife" / "BETTER-METHODS.md"


def _minimal_two_faction_cfg(order_mode: str | None = None, *, enemy_power: float = 1.0) -> dict:
    sim = {
        "default_enabled": True,
        "tick_real_s": 2.0,
        "offline_step_m_per_s": 2.0,
        "online_spawn_radius_m": 450.0,
        "offline_despawn_radius_m": 620.0,
        "waymarker_pool_size": 4,
        "max_active_squads": 6,
        "respawn_cooldown_s": 60.0,
        "show_notifications": False,
    }
    if order_mode is not None:
        sim["order_mode"] = order_mode
    return {
        "schema_version": 1,
        "mod_name": "Scored Orders Test",
        "plugin_name": "ScoredOrdersTest.esm",
        "light_master": True,
        "masters": ["Starfield.esm"],
        "worldspace": {"plugin": "Starfield.esm", "form_id": "0x01251B", "editor_id": "NewAtlantis",
                       "merge_offset_xy": [0.0, 0.0]},
        "simulation": sim,
        "factions": [
            {"id": "alpha", "index": 0, "name": "Alpha",
             "npc_template": {"plugin": "Starfield.esm", "form_id": "0x26FB62"},
             "player_relation": "ally", "relations": {"bravo": "enemy"}, "squad_size": 4, "combat_power": 1.0},
            {"id": "bravo", "index": 1, "name": "Bravo",
             "npc_template": {"plugin": "Starfield.esm", "form_id": "0x1AD194"},
             "player_relation": "enemy", "relations": {"alpha": "enemy"}, "squad_size": 4, "combat_power": enemy_power},
        ],
        "nodes": [
            {"index": 0, "id": "alpha_base", "kind": "base", "x": 0.0, "y": 0.0, "z": 0.0,
             "capacity": 3, "initial_owner": "alpha", "spawn_faction": "alpha"},
            {"index": 1, "id": "mid_west", "kind": "checkpoint", "x": 150.0, "y": 0.0, "z": 0.0,
             "capacity": 2, "initial_owner": None, "spawn_faction": None},
            {"index": 2, "id": "mid_east", "kind": "checkpoint", "x": 300.0, "y": 0.0, "z": 0.0,
             "capacity": 2, "initial_owner": None, "spawn_faction": None},
            {"index": 3, "id": "bravo_base", "kind": "base", "x": 450.0, "y": 0.0, "z": 0.0,
             "capacity": 3, "initial_owner": "bravo", "spawn_faction": "bravo"},
        ],
        "edges": [
            {"u": 0, "v": 1, "len_m": 150.0},
            {"u": 1, "v": 2, "len_m": 150.0},
            {"u": 2, "v": 3, "len_m": 150.0},
        ],
    }


class SchemaOrderModeTest(unittest.TestCase):
    def test_default_is_random_when_omitted(self):
        cfg = _minimal_two_faction_cfg(order_mode=None)
        norm = schema.checked(cfg)
        self.assertEqual(norm["simulation"]["order_mode"], "random")

    def test_valid_order_modes_accepted(self):
        for mode in ("random", "scored"):
            cfg = _minimal_two_faction_cfg(order_mode=mode)
            self.assertEqual(schema.validate_alife_config(cfg), [])
            self.assertEqual(schema.checked(cfg)["simulation"]["order_mode"], mode)

    def test_invalid_order_modes_rejected(self):
        for bad in ("greedy", "utility", "", 0, 1, True, None):
            cfg = _minimal_two_faction_cfg()
            cfg["simulation"]["order_mode"] = bad
            probs = schema.validate_alife_config(cfg)
            self.assertTrue(any("order_mode" in p for p in probs), f"expected order_mode refusal for {bad!r}: {probs}")

    def test_existing_presets_default_to_random(self):
        for name in schema.PRESETS:
            norm = schema.checked(schema.load_preset(name))
            self.assertEqual(norm["simulation"]["order_mode"], "random")


class ScoredOrdersBehaviorTest(unittest.TestCase):
    def test_default_matches_explicit_random_bit_for_bit(self):
        cfg = schema.load_preset("fo4sf_commonwealth")
        r_default = sim_math.simulate(copy.deepcopy(cfg), ticks=600, seed=17)
        r_explicit = sim_math.simulate(copy.deepcopy(cfg), ticks=600, seed=17, order_mode="random")
        self.assertEqual(r_default, r_explicit)
        self.assertEqual(r_default["order_mode"], "random")

    def test_scored_mode_deterministic_fast_and_uses_all_order_types(self):
        cfg = schema.load_preset("fo4sf_commonwealth")
        t0 = time.perf_counter()
        r1 = sim_math.simulate(copy.deepcopy(cfg), ticks=1000, seed=42, order_mode="scored")
        elapsed = time.perf_counter() - t0
        r2 = sim_math.simulate(copy.deepcopy(cfg), ticks=1000, seed=42, order_mode="scored")
        self.assertEqual(r1, r2)
        self.assertLess(elapsed, 1.0)
        self.assertEqual(r1["order_mode"], "scored")
        self.assertGreater(r1["orders"]["raid"], 0)
        self.assertGreater(r1["orders"]["reinforce"], 0)
        self.assertGreater(r1["orders"]["patrol"], 0)

    def test_invalid_order_mode_override_raises(self):
        cfg = _minimal_two_faction_cfg()
        with self.assertRaises(schema.AlifeConfigError):
            sim_math.simulate(cfg, ticks=100, seed=1, order_mode="bogus")

    def test_scored_prefers_weak_enemy_target_over_fortified_target(self):
        # Symmetric fork from alpha's staging lair (0): node 1 is undefended bravo checkpoint; node 2 is fortified bravo base.
        cfg = {
            "schema_version": 1,
            "mod_name": "Weakness Fork",
            "plugin_name": "WeaknessFork.esm",
            "light_master": True,
            "masters": ["Starfield.esm"],
            "worldspace": {"plugin": "Starfield.esm", "form_id": "0x01251B", "editor_id": "NewAtlantis",
                           "merge_offset_xy": [0.0, 0.0]},
            "simulation": {"respawn_cooldown_s": 10000.0, "max_active_squads": 6, "order_mode": "scored"},
            "factions": [
                {"id": "alpha", "index": 0, "name": "Alpha",
                 "npc_template": {"plugin": "Starfield.esm", "form_id": "0x26FB62"},
                 "player_relation": "ally", "relations": {"bravo": "enemy"}, "squad_size": 4, "combat_power": 1.0},
                {"id": "bravo", "index": 1, "name": "Bravo",
                 "npc_template": {"plugin": "Starfield.esm", "form_id": "0x1AD194"},
                 "player_relation": "enemy", "relations": {"alpha": "enemy"}, "squad_size": 8, "combat_power": 5.0},
            ],
            "nodes": [
                {"index": 0, "id": "alpha_camp", "kind": "lair", "x": 0.0, "y": 0.0, "z": 0.0,
                 "capacity": 2, "initial_owner": "alpha", "spawn_faction": "alpha"},
                {"index": 1, "id": "weak_outpost", "kind": "checkpoint", "x": 150.0, "y": 0.0, "z": 0.0,
                 "capacity": 2, "initial_owner": "bravo", "spawn_faction": None},
                {"index": 2, "id": "fortress", "kind": "checkpoint", "x": 0.0, "y": 150.0, "z": 0.0,
                 "capacity": 2, "initial_owner": "bravo", "spawn_faction": "bravo"},
            ],
            "edges": [
                {"u": 0, "v": 1, "len_m": 150.0},
                {"u": 0, "v": 2, "len_m": 150.0},
            ],
        }
        weak_picks = 0
        for seed in range(1, 21):
            res = sim_math.simulate(cfg, ticks=60, seed=seed, record_events=True)
            alpha_orders = [e[2] for e in res["events"] if e[1] == "order" and e[2]["faction"] == "alpha"]
            if alpha_orders and alpha_orders[0]["goal"] == 1:
                weak_picks += 1
        self.assertGreaterEqual(weak_picks, 18, f"expected alpha to pick undefended target over 40-power fortress: {weak_picks}/20")

    def test_sole_defender_holds_exposed_home_base_against_stronger_neighbor(self):
        # Single alpha squad defending an exposed home base beside a 40-power enemy fortress holds rather than deserting.
        cfg = {
            "schema_version": 1,
            "mod_name": "Exposed Base Hold",
            "plugin_name": "ExposedBaseHold.esm",
            "light_master": True,
            "masters": ["Starfield.esm"],
            "worldspace": {"plugin": "Starfield.esm", "form_id": "0x01251B", "editor_id": "NewAtlantis",
                           "merge_offset_xy": [0.0, 0.0]},
            "simulation": {"respawn_cooldown_s": 10000.0, "max_active_squads": 6, "order_mode": "scored"},
            "factions": [
                {"id": "alpha", "index": 0, "name": "Alpha",
                 "npc_template": {"plugin": "Starfield.esm", "form_id": "0x26FB62"},
                 "player_relation": "ally", "relations": {"bravo": "enemy"}, "squad_size": 4, "combat_power": 1.0},
                {"id": "bravo", "index": 1, "name": "Bravo",
                 "npc_template": {"plugin": "Starfield.esm", "form_id": "0x1AD194"},
                 "player_relation": "enemy", "relations": {"alpha": "enemy"}, "squad_size": 8, "combat_power": 5.0},
            ],
            "nodes": [
                {"index": 0, "id": "alpha_base", "kind": "base", "x": 0.0, "y": 0.0, "z": 0.0,
                 "capacity": 2, "initial_owner": "alpha", "spawn_faction": "alpha"},
                {"index": 1, "id": "fortress", "kind": "checkpoint", "x": 200.0, "y": 0.0, "z": 0.0,
                 "capacity": 2, "initial_owner": "bravo", "spawn_faction": "bravo"},
            ],
            "edges": [{"u": 0, "v": 1, "len_m": 200.0}],
        }
        res = sim_math.simulate(cfg, ticks=60, seed=1, record_events=True)
        alpha_raids = [e for e in res["events"] if e[1] == "order" and e[2]["faction"] == "alpha" and e[2]["order"] == "raid"]
        self.assertEqual(alpha_raids, [])

    def test_25_seed_benchmark_commonwealth_reduces_flip_flops(self):
        cfg = schema.load_preset("fo4sf_commonwealth")
        rep = sim_math.benchmark_order_modes(cfg, seeds=range(1, 26), ticks=1000)
        self.assertEqual(rep["seeds"], 25)
        rnd = rep["modes"]["random"]
        scd = rep["modes"]["scored"]
        self.assertLess(scd["mean_flip_flops"], rnd["mean_flip_flops"])
        self.assertGreater(scd["mean_garrison_utilization"], rnd["mean_garrison_utilization"])
        self.assertGreater(scd["mean_replenishes"], rnd["mean_replenishes"])
        self.assertEqual(scd["mean_factions_surviving"], 3.0)
        for order_kind in ("raid", "reinforce", "patrol"):
            self.assertGreater(scd["order_totals"][order_kind], 0)


class CliScoredOrdersTest(unittest.TestCase):
    def test_sim_math_cli_and_build_alife_mod_cli_accept_order_mode(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            cfg_path = tmp / "cfg.json"
            out_json = tmp / "sim_scored.json"
            cfg_path.write_text(json.dumps(_minimal_two_faction_cfg()), encoding="utf-8")

            env = dict(os.environ)
            env["PYTHONPATH"] = str(SRC_DIR) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

            p1 = subprocess.run(
                [sys.executable, "-m", "fo4sf.alife.sim_math", str(cfg_path),
                 "--ticks", "200", "--seed", "7", "--order-mode", "scored"],
                capture_output=True, text=True, env=env, check=False,
            )
            self.assertEqual(p1.returncode, 0, p1.stderr)
            d1 = json.loads(p1.stdout)
            self.assertEqual(d1["order_mode"], "scored")

            p2 = subprocess.run(
                [sys.executable, str(CLI_SCRIPT), "simulate", "--config", str(cfg_path),
                 "--ticks", "200", "--seed", "7", "--order-mode", "scored", "--json-out", str(out_json)],
                capture_output=True, text=True, env=env, check=False,
            )
            self.assertEqual(p2.returncode, 0, p2.stderr)
            self.assertIn("order mode", p2.stdout)
            self.assertIn("scored", p2.stdout)
            d2 = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(d1, d2)


class BetterMethodsDocHygieneTest(unittest.TestCase):
    def test_doc_banner_citations_honesty_and_no_local_paths(self):
        self.assertTrue(BETTER_METHODS_DOC.is_file(), f"missing {BETTER_METHODS_DOC}")
        text = BETTER_METHODS_DOC.read_text(encoding="utf-8")
        first_line = text.splitlines()[0]
        self.assertIn("Titles:", first_line)
        self.assertIn("Modes:", first_line)
        self.assertIn("Track:", first_line)
        self.assertIn("prototype, offline", first_line)
        self.assertEqual(re.findall(r"\b[A-Za-z]:[\\/]", text), [])
        for url in (
            "https://www.gamedeveloper.com/game-platforms/interview-inside-the-ai-of-i-s-t-a-l-k-e-r-i-",
            "https://www.taleworlds.com/en/News/273",
            "https://github.com/damiansirbu-stalker/AlifePlus",
            "https://github.com/ianpatt/sfse",
            "https://www.nexusmods.com/starfield/mods/10457",
        ):
            self.assertIn(url, text)
        self.assertIn("## 6. Evidence Gaps", text)
        self.assertIn("## 8. Owner Questions", text)


if __name__ == "__main__":
    unittest.main()
