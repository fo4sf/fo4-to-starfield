"""Starfield A-Life Modder SDK data layer: schema, graph builder, offline simulator and the two presets.

Synthetic fixtures only. One opt-in check reads a real Starfield.esm read-only: set FO4SF_STARFIELD_ESM to its path
to confirm the vanilla preset's WRLD and NPC_ FormIDs carry the EditorIDs the preset names.
"""
import copy
import io
import json
import math
import os
import posixpath
import re
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from fo4sf.alife import graph_builder as gb  # noqa: E402
from fo4sf.alife import schema, sim_math  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
NW = os.path.join(REPO, "scripts", "alife", "nw_subgraph.json")
PROPS = ("FactionSquadSize", "FactionPower", "FactionRelationsFlat", "NodeX", "NodeY", "NodeZ", "NodeCap",
         "NodeKind", "NodeInitialOwner", "NodeSpawnFaction", "EdgeU", "EdgeV", "EdgeLen", "MergeOffsetX",
         "MergeOffsetY", "OnlineSpawnRadiusM", "OfflineDespawnRadiusM", "OfflineSpeedMps", "TickIntervalS",
         "MaxActiveSquads", "RespawnCooldownS")


def mini(n_nodes=4, edge_len=100.0, relation="enemy", cooldown=60.0, max_squads=8, extra_factions=0):
    """A line graph 0-1-..-(n-1): faction a spawns at node 0, faction b at the last node."""
    nodes = []
    for i in range(n_nodes):
        kind = "base" if i in (0, n_nodes - 1) else "checkpoint"
        nodes.append({"index": i, "id": f"n{i}", "kind": kind, "x": i * edge_len, "y": 0.0, "z": 0.0,
                      "capacity": 2 if kind == "base" else 1,
                      "initial_owner": "a" if i == 0 else "b" if i == n_nodes - 1 else None,
                      "spawn_faction": "a" if i == 0 else "b" if i == n_nodes - 1 else None})
    factions = [
        {"id": "a", "index": 0, "name": "Alpha", "npc_template": {"plugin": "Starfield.esm", "form_id": "0x1AD194"},
         "player_relation": "ally", "relations": {"b": relation}, "squad_size": 4, "combat_power": 1.0},
        {"id": "b", "index": 1, "name": "Beta", "npc_template": {"plugin": "Starfield.esm", "form_id": "0x169D7C"},
         "player_relation": "enemy", "relations": {}, "squad_size": 3, "combat_power": 1.0},
    ]
    return {
        "schema_version": 1, "mod_name": "Mini", "plugin_name": "MiniALife.esm", "light_master": True,
        "masters": ["Starfield.esm", "Unused.esm"],
        "worldspace": {"plugin": "Starfield.esm", "form_id": "0001251B", "editor_id": "TestWorld",
                       "merge_offset_xy": [10.0, -20.0]},
        "simulation": {"respawn_cooldown_s": cooldown, "max_active_squads": max_squads},
        "factions": factions,
        "nodes": nodes,
        "edges": [{"u": i, "v": i + 1, "len_m": edge_len} for i in range(n_nodes - 1)],
    }


class SchemaValid(unittest.TestCase):
    def test_minimal_config_is_valid_and_defaults_fill(self):
        cfg = mini()
        self.assertEqual(schema.validate_alife_config(cfg), [])
        norm = schema.checked(cfg)
        self.assertEqual(norm["simulation"]["online_spawn_radius_m"], 450.0)
        self.assertEqual(norm["simulation"]["offline_despawn_radius_m"], 620.0)
        self.assertEqual(norm["worldspace"]["form_id"], "0x01251B")
        self.assertEqual(norm["editor_prefix"], "MiniALife")
        self.assertEqual(norm["masters"], ["Starfield.esm"])           # Unused.esm is not referenced
        self.assertEqual(norm["nodes"][0]["initial_owner"], 0)
        self.assertEqual(norm["nodes"][1]["initial_owner"], -1)
        self.assertEqual(norm["factions"][1]["relations"], {"a": "enemy"})   # mirrored
        self.assertEqual(norm["factions"][0]["editor_id"], "MiniALife_Faction_A")

    def test_payload_shapes(self):
        p = schema.export_writer_payload(mini())
        json.dumps(p)                                                    # serializable
        self.assertEqual(p["payload_version"], 1)
        for k in PROPS:
            self.assertIn(k, p["properties"])
        props = p["properties"]
        self.assertEqual(props["FactionRelationsFlat"], [1, -1, -1, 1])
        self.assertEqual(props["NodeKind"], [1, 2, 2, 1])
        self.assertEqual(props["NodeInitialOwner"], [0, -1, -1, 1])
        self.assertEqual(props["NodeSpawnFaction"], [0, -1, -1, 1])
        self.assertEqual(props["EdgeU"], [0, 1, 2])
        self.assertEqual(props["EdgeLen"], [100.0] * 3)
        self.assertEqual((props["MergeOffsetX"], props["MergeOffsetY"]), (10.0, -20.0))
        self.assertIsInstance(props["MaxActiveSquads"], int)
        self.assertTrue(all(isinstance(v, float) for v in props["FactionPower"] + props["NodeX"]))
        self.assertEqual(p["globals"], {"SimEnabled": 1.0, "OnlineRadius": 450.0, "MaxSquads": 8.0,
                                        "Notifications": 1.0})
        self.assertEqual(p["waymarker_pool_size"], 8)
        for k in ("plugin_name", "light_master", "masters", "worldspace", "simulation", "factions", "nodes",
                  "edges"):
            self.assertIn(k, p)
        self.assertEqual(p["factions"][0]["player_reaction"], 1)
        self.assertEqual(p["factions"][1]["player_reaction"], -1)

    def test_relations_flat_three_factions_symmetric(self):
        cfg = mini()
        cfg["factions"].append({"id": "c", "index": 2, "name": "Gamma",
                                "npc_template": {"plugin": "Starfield.esm", "form_id": "0x3B3CDD"},
                                "player_relation": "neutral", "relations": {"a": "ally"}, "squad_size": 2,
                                "combat_power": 2.0})
        cfg["nodes"][1].update(kind="base", initial_owner="c", spawn_faction=2)
        flat = schema.export_writer_payload(cfg)["properties"]["FactionRelationsFlat"]
        F = 3
        for a in range(F):
            self.assertEqual(flat[a * F + a], 1)
            for b in range(F):
                self.assertEqual(flat[a * F + b], flat[b * F + a])
        self.assertEqual(flat[0 * F + 2], 1)
        self.assertEqual(flat[1 * F + 2], 0)

    def test_form_id_forms(self):
        self.assertEqual(schema.parse_form_id("0x1251B"), "0x01251B")
        self.assertEqual(schema.parse_form_id("0001251B"), "0x01251B")
        self.assertEqual(schema.parse_form_id("03000803", "FO4TerrainCore.esm"), "0x000803")  # load-order byte
        self.assertEqual(schema.parse_form_id("34", "Starfield.esm"), "0x000034")
        for bad in ("", "0x", "xyz", "0x123456789", "00000000", 1234, None, "FF000000"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                schema.parse_form_id(bad)
        with self.assertRaises(ValueError):
            schema.parse_form_id("0x7FF", "Custom.esm")

    def test_load_path_dict_and_comments(self):
        cfg = mini()
        cfg["_comment"] = "top"
        cfg["worldspace"]["_note"] = "x"
        cfg["simulation"]["_why"] = "y"
        cfg["factions"][0]["_n"] = 1
        cfg["factions"][0]["relations"]["_c"] = "ignored"
        cfg["nodes"][0]["_spot"] = "marker"
        cfg["edges"][0]["_road"] = True
        d = schema.load_alife_config(cfg)
        self.assertIsNot(d, cfg)
        self.assertEqual(schema.validate_alife_config(d), [])
        self.assertNotIn("_comment", schema.export_writer_payload(d))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "c.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(mini(), f)
            self.assertEqual(schema.validate_alife_config(schema.load_alife_config(path)), [])
            bad = os.path.join(tmp, "bad.json")
            with open(bad, "w", encoding="utf-8") as f:
                f.write("{not json")
            with self.assertRaises(schema.AlifeConfigError):
                schema.load_alife_config(bad)
            with open(bad, "w", encoding="utf-8") as f:
                f.write("[1, 2]")
            with self.assertRaises(schema.AlifeConfigError):
                schema.load_alife_config(bad)

    def test_edge_by_node_id_and_computed_length(self):
        cfg = mini()
        cfg["edges"] = [{"u": "n0", "v": "n1"}, {"u": "n1", "v": "n2", "len_m": 100.0},
                        {"u": 2, "v": "n3", "len_m": 120.0}]
        norm = schema.checked(cfg)
        self.assertEqual(norm["edges"][0], {"u": 0, "v": 1, "len_m": 100.0})

    def test_export_refuses_invalid(self):
        cfg = mini()
        cfg["schema_version"] = 2
        with self.assertRaises(schema.AlifeConfigError) as cm:
            schema.export_writer_payload(cfg)
        self.assertTrue(any("schema_version" in p for p in cm.exception.problems))

    def test_validator_never_raises(self):
        for junk in (None, [], "x", {"nodes": "x"}, {"factions": [1, 2], "nodes": [None], "edges": [None]},
                     {"edges": [{"u": 0, "v": 1, "len_m": "x"}]}):
            self.assertTrue(schema.validate_alife_config(junk))

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfgp, outp = os.path.join(tmp, "c.json"), os.path.join(tmp, "p.json")
            with open(cfgp, "w", encoding="utf-8") as f:
                json.dump(mini(), f)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(schema.main(["validate", cfgp]), 0)
                self.assertEqual(schema.main(["export", cfgp, outp]), 0)
            with open(outp, encoding="utf-8") as f:
                self.assertEqual(json.load(f)["properties"]["NodeCap"], [2, 1, 1, 2])
            bad = mini()
            bad["edges"] = []
            with open(cfgp, "w", encoding="utf-8") as f:
                json.dump(bad, f)
            err = io.StringIO()
            with redirect_stderr(err):
                self.assertEqual(schema.main(["validate", cfgp]), 2)
                self.assertEqual(schema.main([]), 2)
            self.assertIn("edges", err.getvalue())


class SchemaInvalid(unittest.TestCase):
    """Each mutation must be refused with a problem mentioning the key word."""

    def expect(self, mutate, word):
        cfg = mini()
        mutate(cfg)
        problems = schema.validate_alife_config(cfg)
        self.assertTrue(problems, f"accepted: {word}")
        self.assertTrue(any(word in p for p in problems), f"{word!r} not in {problems}")

    def test_top_level(self):
        self.expect(lambda c: c.update(schema_version=True), "schema_version")
        self.expect(lambda c: c.update(mod_name=""), "mod_name")
        self.expect(lambda c: c.update(plugin_name="dir/Mod.esm"), "plugin_name")
        self.expect(lambda c: c.update(plugin_name="Mod.txt"), "plugin_name")
        self.expect(lambda c: c.update(plugin_name="Starfield.esm"), "plugin_name")
        self.expect(lambda c: c.update(light_master="yes"), "light_master")
        self.expect(lambda c: c.update(editor_prefix="9bad"), "editor_prefix")
        self.expect(lambda c: c.update(bogus=1), "unknown top-level key")

    def test_masters(self):
        self.expect(lambda c: c.update(masters=[]), "masters")
        self.expect(lambda c: c.update(masters=["Other.esm", "Starfield.esm"]), "masters[0]")
        self.expect(lambda c: c.update(masters=["Starfield.esm", "Starfield.esm"]), "twice")
        self.expect(lambda c: c.update(masters=["Starfield.esm", "MiniALife.esm"]), "own master")
        self.expect(lambda c: c["worldspace"].update(plugin="Missing.esm", form_id="0x000803"), "not in masters")
        self.expect(lambda c: c["factions"][0]["npc_template"].update(plugin="Missing.esm"), "not in masters")

    def test_worldspace(self):
        self.expect(lambda c: c.update(worldspace=[]), "worldspace")
        self.expect(lambda c: c["worldspace"].update(form_id="0xZZ"), "worldspace.form_id")
        self.expect(lambda c: c["worldspace"].update(form_id="0x0"), "null id")
        self.expect(lambda c: c["worldspace"].update(editor_id="has space"), "editor_id")
        self.expect(lambda c: c["worldspace"].update(merge_offset_xy=[1.0]), "merge_offset_xy")
        self.expect(lambda c: c["worldspace"].update(merge_offset_xy=[1.0, float("nan")]), "merge_offset_xy")

        def low_custom(c):
            c["masters"].append("Custom.esm")
            c["worldspace"].update(plugin="Custom.esm", form_id="0x000100")
        self.expect(low_custom, "reserved")

    def test_simulation(self):
        sim = lambda **kw: (lambda c: c["simulation"].update(**kw))  # noqa: E731
        self.expect(sim(online_spawn_radius_m=450.0, offline_despawn_radius_m=500.0), "hysteresis")
        self.expect(sim(online_spawn_radius_m=450.0, offline_despawn_radius_m=500.0), "hysteresis")
        self.expect(sim(waymarker_pool_size=3), "waymarker_pool_size")
        self.expect(sim(waymarker_pool_size=17), "waymarker_pool_size")
        self.expect(sim(waymarker_pool_size=8.0), "waymarker_pool_size")
        self.expect(sim(max_active_squads=0), "max_active_squads")
        self.expect(sim(max_active_squads=17), "max_active_squads")
        self.expect(sim(tick_real_s=0.0), "tick_real_s")
        self.expect(sim(offline_step_m_per_s="fast"), "offline_step_m_per_s")
        self.expect(sim(respawn_cooldown_s=-1.0), "respawn_cooldown_s")
        self.expect(sim(default_enabled=1), "default_enabled")
        self.expect(sim(show_notification=True), "unknown key")
        # exactly +50 is not enough; +50.01 is
        self.expect(sim(online_spawn_radius_m=450.0, offline_despawn_radius_m=500.0), "hysteresis")
        ok = mini()
        ok["simulation"].update(online_spawn_radius_m=450.0, offline_despawn_radius_m=500.01)
        self.assertEqual(schema.validate_alife_config(ok), [])

    def test_factions(self):
        self.expect(lambda c: c.update(factions=[]), "factions")

        def nine(c):
            base = c["factions"][1]
            c["factions"] += [dict(copy.deepcopy(base), id=f"f{i}", index=2 + i, relations={}) for i in range(7)]
        self.expect(nine, "1..8")
        self.expect(lambda c: c["factions"][1].update(id="a"), "used twice")
        self.expect(lambda c: c["factions"][0].update(id="Bad-Id"), "id")
        self.expect(lambda c: c["factions"][0].update(index=1), "index")
        self.expect(lambda c: c["factions"][0].update(name=""), "name")
        self.expect(lambda c: c["factions"][0].update(player_relation="friend"), "player_relation")
        self.expect(lambda c: c["factions"][0].update(squad_size=9), "squad_size")
        self.expect(lambda c: c["factions"][0].update(squad_size=0), "squad_size")
        self.expect(lambda c: c["factions"][0].update(combat_power=0), "combat_power")
        self.expect(lambda c: c["factions"][0].update(relations={"zzz": "enemy"}), "unknown faction id")
        self.expect(lambda c: c["factions"][0].update(relations={"a": "enemy"}), "itself")
        self.expect(lambda c: c["factions"][0].update(relations={"b": "hostile"}), "relations")
        self.expect(lambda c: c["factions"][1].update(relations={"a": "ally"}), "disagree")
        self.expect(lambda c: c["factions"][0].update(npc_template={"plugin": "Starfield.esm"}), "form_id")
        self.expect(lambda c: c["factions"][0].update(extra=1), "unknown key")

    def test_nodes(self):
        self.expect(lambda c: c.update(nodes=c["nodes"][:1], edges=[]), "nodes")

        def too_many(c):
            c["nodes"] = [dict(c["nodes"][1], index=i, id=f"n{i}", x=float(i)) for i in range(129)]
        self.expect(too_many, "2..128")
        self.expect(lambda c: c["nodes"][1].update(id="n0"), "used twice")
        self.expect(lambda c: c["nodes"][1].update(index=5), "index")
        self.expect(lambda c: c["nodes"][1].update(kind="town"), "kind")
        self.expect(lambda c: c["nodes"][1].update(x=float("inf")), ".x")
        self.expect(lambda c: c["nodes"][1].update(z=None), ".z")
        self.expect(lambda c: c["nodes"][1].update(capacity=17), "capacity")
        self.expect(lambda c: c["nodes"][1].update(capacity=0), "capacity >= 1")
        self.expect(lambda c: c["nodes"][1].update(kind="relay", capacity=1), "relay")
        self.expect(lambda c: c["nodes"][1].update(kind="relay", capacity=0, initial_owner="a"), "relay")
        self.expect(lambda c: c["nodes"][1].update(initial_owner="zzz"), "initial_owner")
        self.expect(lambda c: c["nodes"][1].update(spawn_faction=7), "spawn_faction")
        self.expect(lambda c: c["nodes"][3].update(spawn_faction=None), "owns no spawn base")
        self.expect(lambda c: c["nodes"][3].update(initial_owner=None), "owns no spawn base")

    def test_edges(self):
        self.expect(lambda c: c.update(edges=[]), "edges")
        self.expect(lambda c: c.update(edges=c["edges"] * 43), "1..128")
        self.expect(lambda c: c["edges"].pop(1), "not connected")
        self.expect(lambda c: c["edges"].append({"u": 1, "v": 0, "len_m": 100.0}), "duplicates")
        self.expect(lambda c: c["edges"].append({"u": 1, "v": 1, "len_m": 1.0}), "itself")
        self.expect(lambda c: c["edges"].append({"u": 0, "v": 9, "len_m": 1.0}), "node index")
        self.expect(lambda c: c["edges"][0].update(len_m=0), "len_m")
        self.expect(lambda c: c["edges"][0].update(len_m=10.0), "straight-line")
        self.expect(lambda c: c["edges"][0].update(u=True), "node index")


class Presets(unittest.TestCase):
    def test_both_presets_validate_and_export(self):
        for name in schema.PRESETS:
            cfg = schema.load_preset(name)
            self.assertEqual(schema.validate_alife_config(cfg), [], name)
            p = schema.export_writer_payload(cfg)
            for k, v in p["properties"].items():
                if isinstance(v, list):
                    self.assertLessEqual(len(v), schema.ARRAY_CAP, k)

    def test_vanilla_is_starfield_only(self):
        cfg = schema.load_preset("vanilla_new_atlantis")
        self.assertEqual(cfg["masters"], ["Starfield.esm"])
        self.assertEqual(cfg["worldspace"]["plugin"], "Starfield.esm")
        self.assertEqual(cfg["worldspace"]["merge_offset_xy"], [0.0, 0.0])
        self.assertTrue(all(f["npc_template"]["plugin"] == "Starfield.esm" for f in cfg["factions"]))
        p = schema.export_writer_payload(cfg)
        self.assertEqual(p["masters"], ["Starfield.esm"])
        self.assertEqual({f["player_relation"] for f in cfg["factions"]}, {"ally", "enemy"})
        self.assertEqual(schema.template_config(), cfg)

    def test_commonwealth_matches_nw_subgraph(self):
        with open(NW, encoding="utf-8") as f:
            g = json.load(f)
        cfg = schema.load_preset("fo4sf_commonwealth")
        self.assertEqual(len(cfg["nodes"]), 20)
        self.assertEqual(len(cfg["edges"]), 36)
        self.assertEqual(len(g["nodes"]), 20)
        self.assertEqual(len(cfg["factions"]), 3)
        self.assertEqual(cfg["worldspace"]["merge_offset_xy"], g["merge_offset"])
        self.assertEqual(cfg["worldspace"]["editor_id"], "FO4Core_Commonwealth")
        for a, b in zip(cfg["nodes"], g["nodes"]):
            self.assertEqual((a["id"], a["x"], a["y"], a["z"]), (b["edid"], b["x"], b["y"], b["z"]))
        self.assertEqual([(e["u"], e["v"], e["len_m"]) for e in cfg["edges"]],
                         [(e["u"], e["v"], e["len_m"]) for e in g["edges"]])
        norm = schema.checked(cfg)
        self.assertEqual(norm["masters"], ["Starfield.esm", "FO4TerrainCore.esm", "FO4ActorRaider.esm"])
        owners = {norm["factions"][n["initial_owner"]]["id"] for n in norm["nodes"] if n["initial_owner"] >= 0}
        self.assertEqual(owners, {"minutemen", "raiders", "scavengers"})

    def test_preset_path_unknown(self):
        with self.assertRaises(KeyError):
            schema.preset_path("nope")

    def test_cross_os_path_basename_and_error_labels(self):
        drv = "D:"
        with mock.patch("os.path.basename", side_effect=posixpath.basename):
            self.assertEqual(schema.path_basename(drv + "\\Mods\\Data\\SynthALife.esm"), "SynthALife.esm")
            self.assertEqual(schema.path_basename(drv + "\\Mods/Data\\SynthALife.esm"), "SynthALife.esm")
            self.assertEqual(schema.path_basename(drv + "\\Mods\\Data\\"), "Data")
            self.assertEqual(schema.path_basename(drv + "\\"), "")
            self.assertEqual(schema.path_basename("/opt/build/SynthALife.esm"), "SynthALife.esm")
            self.assertEqual(schema.path_basename("/opt/build/data/"), "data")
            self.assertEqual(schema.path_basename("\\\\nas\\mods\\Data\\SynthALife.esm"), "SynthALife.esm")
            self.assertEqual(schema.path_basename("\\\\nas\\mods\\"), "")
            self.assertEqual(schema.default_prefix(drv + "\\Mods\\Synth_ALife.esm"), "SynthALife")
            self.assertEqual(schema.default_prefix("/opt/mods/Synth_ALife.esm"), "SynthALife")
            with self.assertRaises(schema.AlifeConfigError) as cm:
                schema.load_alife_config(drv + "\\missing_dir\\alife_config.json")
            self.assertTrue(cm.exception.problems[0].startswith("alife_config.json:"), cm.exception.problems)
            with tempfile.TemporaryDirectory() as tmp:
                bad = os.path.join(tmp, "markers.json")
                with open(bad, "w", encoding="utf-8") as f:
                    f.write("42")
                with self.assertRaises(ValueError) as vm:
                    gb.read_marker_json(bad)
                self.assertIn("markers.json: no marker list", str(vm.exception))

    def test_no_private_paths_or_names_in_owned_files(self):
        owned = [os.path.join(REPO, "src", "fo4sf", "alife", n) for n in
                 ("__init__.py", "schema.py", "graph_builder.py", "sim_math.py",
                  os.path.join("presets", "vanilla_new_atlantis.json"),
                  os.path.join("presets", "fo4sf_commonwealth.json"))] + [os.path.abspath(__file__)]
        pat = re.compile(r"\b[A-Za-z]:[\\/]|" + "Steam" + "Library|" + "steam" + r"apps|[\\/]Users[\\/]|/ho" + "me/",
                         re.I)
        for path in owned:
            with open(path, encoding="utf-8") as f:
                self.assertIsNone(pat.search(f.read()), path)

    @unittest.skipUnless(os.environ.get("FO4SF_STARFIELD_ESM"), "set FO4SF_STARFIELD_ESM to check real FormIDs")
    def test_vanilla_formids_against_real_starfield_esm(self):
        from fo4sf.planet.esm import Plugin
        cfg = schema.checked(schema.load_preset("vanilla_new_atlantis"))
        want_npc = {int(f["npc_template"]["form_id"], 16): f["npc_template"].get("editor_id")
                    for f in schema.load_preset("vanilla_new_atlantis")["factions"]}
        wid = int(cfg["worldspace"]["form_id"], 16)
        with Plugin(os.environ["FO4SF_STARFIELD_ESM"]) as p:
            worlds = {}
            for start, end in p.groups["WRLD"]:
                for it in p.walk(start, end, groups=set()):
                    if it[0] == "REC" and it[2] == b"WRLD":
                        r = p.record_at(it[1])
                        worlds[r.formid & 0xFFFFFF] = r.edid
            self.assertEqual(worlds.get(wid), cfg["worldspace"]["editor_id"])
            found = {}
            for r in p.records("NPC_"):
                if r.formid & 0xFFFFFF in want_npc:
                    found[r.formid & 0xFFFFFF] = r.edid
        self.assertEqual(found, want_npc)


class GraphBuilder(unittest.TestCase):
    def test_coordinate_tables_csv_and_tsv(self):
        with tempfile.TemporaryDirectory() as tmp:
            csvp = os.path.join(tmp, "n.csv")
            with open(csvp, "w", encoding="utf-8", newline="") as f:
                f.write("name,pos_x,pos_y,pos_z,type,cap,owner\nA,0,0,1,settlement,,a\nB,100,0,1,road,,\n"
                        "C,200,10,1,military_or_checkpoint,1,unheld\n")
            nodes = gb.read_coordinate_table(csvp)
            self.assertEqual([n["kind"] for n in nodes], ["base", "relay", "checkpoint"])
            self.assertEqual([n["capacity"] for n in nodes], [3, 0, 1])
            self.assertEqual(nodes[0]["initial_owner"], "a")
            self.assertNotIn("initial_owner", nodes[2])
            tsvp = os.path.join(tmp, "n.tsv")
            with open(tsvp, "w", encoding="utf-8", newline="") as f:
                f.write("edid\tx_sf_m\ty_sf_m\tz_sf_m\tsmart_terrain_class\n"
                        "P\t1.5\t2.5\t3.5\tresource_industrial\n")
            self.assertEqual(gb.read_coordinate_table(tsvp)[0]["kind"], "resource")
            edp = os.path.join(tmp, "e.csv")
            with open(edp, "w", encoding="utf-8", newline="") as f:
                f.write("u,v,len_m\nA,B,120\nB,2,\n")
            edges = gb.read_edge_table(edp, nodes)
            self.assertEqual(edges[0], {"u": 0, "v": 1, "len_m": 120.0})
            self.assertAlmostEqual(edges[1]["len_m"], math.hypot(100, 10), places=2)
            with open(edp, "w", encoding="utf-8", newline="") as f:
                f.write("u,v\nA,Nope\n")
            with self.assertRaises(ValueError):
                gb.read_edge_table(edp, nodes)

    def test_marker_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "m.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"markers": [{"edid": "M1", "pos": [1, 2, 3], "kind": "base"},
                                       {"id": "M2", "x": 5, "y": 6}]}, f)
            nodes = gb.read_marker_json(p)
            self.assertEqual(nodes[0]["x"], 1.0)
            self.assertEqual(nodes[1]["kind"], "relay")
            with open(p, "w", encoding="utf-8") as f:
                json.dump([{"id": "bad", "kind": "volcano", "x": 0, "y": 0}], f)
            with self.assertRaises(ValueError):
                gb.read_marker_json(p)

    def random_points(self, n, seed=7):
        import random
        rng = random.Random(seed)
        kinds = ["relay", "relay", "base", "checkpoint", "lair", "resource"]
        return [{"id": f"p{i}", "kind": rng.choice(kinds), "x": rng.uniform(-3000, 3000),
                 "y": rng.uniform(-3000, 3000), "z": rng.uniform(0, 200), "capacity": 0} for i in range(n)]

    def test_select_anchors_caps_deterministically(self):
        pts = self.random_points(400)
        a1, a2 = gb.select_anchors(pts, 128), gb.select_anchors(pts, 128)
        self.assertEqual(len(a1), 128)
        self.assertEqual([p["id"] for p in a1], [p["id"] for p in a2])
        few = gb.select_anchors(pts, 500)
        self.assertEqual(len(few), 400)
        primary = [p for p in pts if p["kind"] != "relay"]
        if len(primary) > 128:
            self.assertTrue(all(p["kind"] != "relay" for p in a1))

    def test_knn_connects_and_caps(self):
        pts = self.random_points(128)
        edges = gb.knn_edges(pts, k=3)
        self.assertEqual(len(schema.connected_from(len(pts), edges, 0)), 128)
        capped = gb.cap_edges(pts, edges, 128)
        self.assertLessEqual(len(capped), 128)
        self.assertEqual(len(schema.connected_from(len(pts), capped, 0)), 128)
        with self.assertRaises(ValueError):
            gb.cap_edges(pts, capped, 100)                      # a tree of 128 nodes needs 127 edges

    def test_contract_sums_relay_lengths(self):
        nodes = [{"id": n, "kind": k, "x": x, "y": 0.0, "z": 0.0, "capacity": 0}
                 for n, k, x in (("A", "base", 0), ("r1", "relay", 10), ("r2", "relay", 20), ("B", "base", 30),
                                 ("C", "base", 60))]
        edges = [{"u": 0, "v": 1, "len_m": 11.0}, {"u": 1, "v": 2, "len_m": 12.0}, {"u": 2, "v": 3, "len_m": 13.0},
                 {"u": 3, "v": 4, "len_m": 31.0}]
        kept, cedges = gb.contract(nodes, edges, ["A", "B", "C"])
        self.assertEqual([n["id"] for n in kept], ["A", "B", "C"])
        self.assertIn({"u": 0, "v": 1, "len_m": 36.0}, cedges)
        self.assertIn({"u": 1, "v": 2, "len_m": 31.0}, cedges)
        self.assertNotIn(0, [e["u"] for e in cedges if e["v"] == 2])   # A-C passes through B: not a candidate
        with self.assertRaises(ValueError):
            gb.contract(nodes, edges[:1], ["A", "C"])

    def test_auto_graph_to_valid_config(self):
        pts = self.random_points(300)
        nodes, edges = gb.auto_graph(pts, max_nodes=128)
        self.assertLessEqual(len(nodes), 128)
        self.assertLessEqual(len(edges), 128)
        # owners/spawns: first base -> a, last base -> b
        bases = [i for i, n in enumerate(nodes) if n["kind"] != "relay"]
        for n in nodes:
            n["capacity"] = 0 if n["kind"] == "relay" else 2
        nodes[bases[0]].update(initial_owner="a", spawn_faction="a")
        nodes[bases[-1]].update(initial_owner="b", spawn_faction="b")
        tpl = mini()
        cfg = gb.build_config(nodes, edges, mod_name="Big", plugin_name="Big.esp",
                              worldspace=tpl["worldspace"], factions=tpl["factions"])
        self.assertEqual(schema.validate_alife_config(cfg), [])
        res = sim_math.simulate(cfg, ticks=300, seed=1)
        self.assertGreater(res["squads_spawned"], 0)

    def test_auto_graph_with_edges_contracts(self):
        pts = self.random_points(160)
        full = gb.knn_edges(pts, k=2)
        nodes, edges = gb.auto_graph(pts, full, max_nodes=60)
        self.assertEqual(len(nodes), 60)
        self.assertEqual(len(schema.connected_from(60, edges, 0)), 60)

    def test_nw_import(self):
        with open(NW, encoding="utf-8") as f:
            g = json.load(f)
        nodes, edges = gb.nodes_from_nw_subgraph(g)
        self.assertEqual(len(nodes), 20)
        self.assertEqual(len(edges), 36)
        self.assertTrue(all(n["kind"] in schema.NODE_KINDS for n in nodes))

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            tpl, pts, out = (os.path.join(tmp, n) for n in ("t.json", "p.json", "o.json"))
            with open(tpl, "w", encoding="utf-8") as f:
                json.dump(mini(), f)
            with open(pts, "w", encoding="utf-8") as f:
                json.dump([{"id": "A", "x": 0, "y": 0, "kind": "base", "initial_owner": "a", "spawn_faction": "a"},
                           {"id": "B", "x": 50, "y": 0},
                           {"id": "C", "x": 100, "y": 0, "kind": "base", "initial_owner": "b",
                            "spawn_faction": "b"}], f)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(gb.main([pts, "--template", tpl, "--out", out]), 0)
            self.assertEqual(schema.validate_alife_config(schema.load_alife_config(out)), [])


class Simulator(unittest.TestCase):
    KEYS = ("squads_spawned", "edges_traversed", "battles", "captures", "garrison_utilization", "per_faction")

    def test_graph_route_ties_and_pass_through(self):
        nodes = [{"x": 0.0, "y": 0.0}] * 4
        g = sim_math.Graph(nodes, [{"u": 0, "v": 2, "len_m": 1.0}, {"u": 2, "v": 3, "len_m": 1.0},
                                   {"u": 0, "v": 1, "len_m": 1.0}, {"u": 1, "v": 3, "len_m": 1.0}])
        self.assertEqual(g.route(0, 3), [0, 1, 3])
        self.assertEqual(g.route(3, 0), [3, 1, 0])
        g2 = sim_math.Graph(nodes[:3], [{"u": 0, "v": 1, "len_m": 5.0}])
        self.assertIsNone(g2.route(0, 2))

    def test_presets_fast_and_deterministic(self):
        for name in schema.PRESETS:
            cfg = schema.load_preset(name)
            t = time.perf_counter()
            r1 = sim_math.simulate(cfg, ticks=1000, seed=42)
            self.assertLess(time.perf_counter() - t, 1.0, name)
            r2 = sim_math.simulate(copy.deepcopy(cfg), ticks=1000, seed=42)
            self.assertEqual(r1, r2)
            for k in self.KEYS:
                self.assertIn(k, r1)
            self.assertTrue(0.0 <= r1["garrison_utilization"] <= 1.0)
            self.assertGreater(r1["squads_spawned"], 0)
            self.assertGreater(r1["edges_traversed"], 0)
            self.assertEqual(set(r1["per_faction"]), {f["id"] for f in cfg["factions"]})
            self.assertEqual(sum(d["nodes_owned"] for d in r1["per_faction"].values()),
                             sum(o is not None for o in r1["final_owners"]))

    def test_accepts_path_and_payload(self):
        path = schema.preset_path("vanilla_new_atlantis")
        payload = schema.export_writer_payload(schema.load_alife_config(path))
        self.assertEqual(sim_math.simulate(path, 200, 3), sim_math.simulate(payload, 200, 3))
        bad = mini()
        bad["edges"] = []
        with self.assertRaises(schema.AlifeConfigError):
            sim_math.simulate(bad, 10)

    def test_battles_and_losses_only_between_hostiles(self):
        hot = sim_math.simulate(mini(edge_len=60.0, relation="enemy"), ticks=1500, seed=5, record_events=True)
        self.assertGreater(hot["battles"], 0)
        self.assertGreater(sum(d["losses"] for d in hot["per_faction"].values()), 0)
        steps = [e[1] for e in hot["events"]]
        self.assertEqual(steps.count("battle"), hot["battles"])
        self.assertEqual(steps.count("squad_defeated"), sum(d["losses"] for d in hot["per_faction"].values()))
        calm = sim_math.simulate(mini(edge_len=60.0, relation="neutral"), ticks=1500, seed=5)
        self.assertEqual(calm["battles"], 0)
        self.assertEqual(sum(d["losses"] for d in calm["per_faction"].values()), 0)

    def test_capture_flips_owner(self):
        res = sim_math.simulate(mini(n_nodes=5, edge_len=80.0, relation="neutral"), ticks=1500, seed=2,
                                record_events=True)
        caps = [e for e in res["events"] if e[1] == "capture"]
        self.assertTrue(caps)
        self.assertEqual(len(caps), sum(res["captures"].values()))
        for _, _, kw in caps:
            self.assertNotEqual(kw["owner_from"], kw["owner_to"])

    def test_respawn_cooldown_and_slot_cap(self):
        cfg = mini(relation="neutral", cooldown=100.0, max_squads=16)
        res = sim_math.simulate(cfg, ticks=1000, seed=1, record_events=True)
        by_base = {}
        for tick, step, kw in res["events"]:
            if step == "squad_spawn":
                by_base.setdefault(kw["node"], []).append(tick)
        for ticks in by_base.values():
            gaps = [b - a for a, b in zip(ticks, ticks[1:])]
            self.assertTrue(all(g >= 50 for g in gaps), gaps)      # 100 s / 2 s per tick
        capped = sim_math.simulate(mini(relation="neutral", cooldown=0.0, max_squads=3), ticks=400, seed=1)
        self.assertEqual(capped["squads_spawned"], 3)
        self.assertEqual(capped["active_squads_end"], 3)

    def test_crowding_reroutes(self):
        cfg = mini(n_nodes=5, relation="neutral", cooldown=0.0, max_squads=16, edge_len=40.0)
        res = sim_math.simulate(cfg, ticks=1500, seed=4)
        self.assertGreater(res["reroutes"], 0)
        self.assertLessEqual(res["active_squads_end"], 16)

    def test_movement_speed(self):
        # one squad, one 100 m edge at 1.35 m/s x 2 s: arrival on tick ceil(100 / 2.7) after departure
        cfg = mini(n_nodes=2, edge_len=100.0, relation="neutral", cooldown=10000.0, max_squads=1)
        res = sim_math.simulate(cfg, ticks=200, seed=0, record_events=True)
        ev = res["events"]
        order = next(e for e in ev if e[1] == "order")
        arrive = next(e for e in ev if e[1] == "node_arrive")
        self.assertEqual(arrive[0] - order[0], math.ceil(100.0 / 2.7) - 1)
        self.assertTrue(math.ceil(45.0 / 2.0) <= order[0] <= math.ceil(75.0 / 2.0))   # 45 s + U(0, 30) s dwell


if __name__ == "__main__":
    unittest.main()
