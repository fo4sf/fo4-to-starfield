"""A-Life slice 1: the contract between dotnet/ALife (the plugin), FO4SF_ALifeControllerQuest.psc (the controller) and
make_alife.py (the offline graph, staging and the log judge). Synthetic only; the C# writer's own self-test runs when a
dotnet SDK is on PATH (dotnet/ALife selftest: synthetic masters, write + check, refusals and mutations)."""
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts", "alife"))
import make_alife  # noqa: E402

PSC = os.path.join(ROOT, "scripts", "alife", "FO4SF_ALifeControllerQuest.psc")
CS = os.path.join(ROOT, "dotnet", "ALife", "Program.cs")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def place(nid, edid, x, y, z=10.0, cap=2, **extra):
    row = {"node_id": nid, "lctn_edid": edid, "x_sf_m": str(x), "y_sf_m": str(y), "z_sf_m": str(z),
           "max_squad_cap": str(cap), "smart_terrain_class": "settlement_base", "initial_faction": "Unheld",
           "xmrk_edid": ""}
    row.update(extra)
    return row


def edge(u, v, d):
    return {"u_id": u, "v_id": v, "dist_sf_m": str(d)}


def tiny_graph():
    """A-B-C in a line plus a relay R between A and D: A(0,0) B(10,0) C(20,0) D(0,30)."""
    places = [place("L:A", "A", 0, 0), place("L:B", "B", 10, 0, cap=1), place("L:C", "C", 20, 0),
              place("L:D", "D", 0, 30, cap=3)]
    edges = [edge("L:A", "L:B", 10), edge("L:B", "L:C", 10), edge("L:A", "T:R", 14), edge("T:R", "L:D", 17),
             edge("L:A", "L:C", 25)]
    return places, edges


class ContractTests(unittest.TestCase):
    def test_script_properties_are_the_ones_the_plugin_fills(self):
        self.assertEqual(tuple(make_alife.mandatory_properties(read(PSC))), make_alife.PROPERTIES)
        cs = read(CS)
        for name in make_alife.PROPERTIES:
            self.assertIn(f'"{name}"', cs, f"Program.cs never writes the property {name}")

    def test_names_and_ids_agree(self):
        psc, cs = read(PSC), read(CS)
        self.assertIn(f"Scriptname {make_alife.SCRIPT} extends Quest", psc)
        self.assertIn(f'GetFormFromFile(2048, "{make_alife.PLUGIN}")', psc)      # 2048 = QUST 0x800
        self.assertIn("QuestId = 0x800", cs)
        self.assertIn(f'Plugin = "{make_alife.PLUGIN}"', cs)
        self.assertIn(f'ScriptName = "{make_alife.SCRIPT}"', cs)
        self.assertIn('string LogName = "FO4SF_ALife"', psc)
        self.assertTrue(make_alife.LOG.endswith("FO4SF_ALife.0.log"))

    def test_script_defaults_match_the_judge(self):
        psc = read(PSC)

        def default(name):
            m = re.search(rf"^\s*(?:float|int)\s+Property\s+{name}\s*=\s*(-?[\d.]+)\s+Auto\s+Const\b", psc, re.M)
            self.assertIsNotNone(m, name)
            return float(m.group(1))
        self.assertEqual(default("OfflineSpeed"), make_alife.SPEED)
        self.assertEqual(default("OfflineStep"), make_alife.STEP)
        self.assertEqual(default("SquadSize"), make_alife.SQUAD)
        self.assertEqual(default("Rung1aTimeout"), make_alife.TIMEOUT)
        self.assertEqual(default("MaxStepSpeed"), make_alife.MAX_STEP)
        self.assertEqual(default("SpreadRadius"), make_alife.SPREAD)
        self.assertEqual(default("SpreadOkFraction"), make_alife.SPREAD_OK)
        self.assertEqual(default("MaxSnapError"), make_alife.MAX_SNAP)
        self.assertEqual(default("OfflineMinPlayerM"), make_alife.OFFLINE_MIN_PLAYER_M)
        self.assertEqual((default("MergeOffsetX"), default("MergeOffsetY")), make_alife.MERGE_OFFSET)
        self.assertEqual(default("Mode"), 0.0, "the controller must stay idle until a console command")

    def test_papyrus_rules(self):
        psc = read(PSC)
        code = "\n".join(line.split(";", 1)[0] for line in psc.splitlines())
        for word in ("guard", "protectsfunctionlogic"):
            self.assertIsNone(re.search(rf"\b{word}\b", code, re.I), f"{word} is not a safe Papyrus identifier")
        sizes = [int(n) for n in re.findall(r"new\s+\w+\[(\d+)\]", code)]
        self.assertTrue(sizes)
        self.assertLessEqual(max(sizes), make_alife.ARRAY_CAP)
        self.assertNotRegex(code, r"new\s+\w+\[[A-Za-z_]", "array sizes are literals")

    def test_every_telemetry_step_is_logged(self):
        psc = read(PSC)
        for step in ("init", "load_game", "rung1a_spawn", "rung1a_waymarker_place", "rung1a_waymarker_advance", "rung1a_progress",
                     "rung1a_stuck", "rung1a_waymarker_replace", "rung1a_arrived", "garrison_cap_check", "rung1b_start", "rung1b_route",
                     "rung1b_tick", "rung1b_edge_step", "rung1b_node_arrive", "summary", "stop"):
            self.assertIn(f'"step={step} ', psc.replace('step=" + ', "step= ") + "", step)

    def test_finish1a_requires_waymarker_reuse(self):
        psc = read(PSC)
        fin = psc[psc.index("Function Finish1a("):psc.index("EndFunction", psc.index("Function Finish1a("))]
        self.assertIn("reusedCount >= 1", fin)
        self.assertIn('" reused=" + reusedCount', fin)

    def test_occupancy_resets_on_shutdown_and_new_runs(self):
        psc = read(PSC)
        reset = psc[psc.index("Function ResetOccupancy("):psc.index("EndFunction", psc.index("Function ResetOccupancy("))]
        self.assertIn("occupancy = new int[128]", reset)
        for fn in ("Event OnQuestInit(", "Function Shutdown(", "Function StartRung1a(", "Function StartRung1b("):
            end = "EndEvent" if fn.startswith("Event ") else "EndFunction"
            body = psc[psc.index(fn):psc.index(end, psc.index(fn))]
            self.assertIn("ResetOccupancy()", body, f"{fn} must reset garrison occupancy for retries")

    def test_load_game_rebases_realtime_clock(self):
        psc = read(PSC)
        self.assertIn('RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")', psc)
        ev = psc[psc.index("Event Actor.OnPlayerLoadGame("):psc.index("EndEvent", psc.index("Event Actor.OnPlayerLoadGame("))]
        self.assertIn("RebaseTimers(", ev)
        rb = psc[psc.index("Function RebaseTimers("):psc.index("EndFunction", psc.index("Function RebaseTimers("))]
        self.assertIn("t0 = now - elapsed", rb)
        self.assertIn("lastT = now", rb)
        self.assertIn("stuckT = now - stuckAge", rb)
        samp = psc[psc.index("Function Rung1aSample("):psc.index("EndFunction", psc.index("Function Rung1aSample("))]
        self.assertIn("if now < lastT", samp)

    def test_squad_size_guarded_and_sized(self):
        psc = read(PSC)
        start = psc[psc.index("Function StartRung1a("):psc.index("EndFunction", psc.index("Function StartRung1a("))]
        self.assertIn("SquadSize < 1 || SquadSize > MAX_SQUAD", start)
        self.assertIn("reason=bad_squad_size", start)
        self.assertIn("squad = new Actor[16]", start)
        self.assertIn("while i < SquadSize && i < MAX_SQUAD", start)

    def test_doc_ascii_and_pc_card_guards(self):
        doc = read(os.path.join(ROOT, "docs", "alife", "alife-slice1.md"))
        self.assertTrue(doc.isascii(), "alife-slice1.md must stay pure ASCII (no mojibake arrows)")
        self.assertIn("450 m / 620 m", doc)
        self.assertIn("not implemented in slice 1", doc)
        self.assertIn("coc FO4Core_RedRocketSpawn", doc)
        self.assertIn("never use `player.setpos` for a jump over 200 m", doc)
        self.assertIn("--file", doc)
        self.assertGreaterEqual(doc.lower().count("reload the pre-run save before any retry"), 2)

    def test_walk_is_the_linked_ref_alone(self):
        psc = read(PSC)
        body = psc[psc.index("Function LinkSquad("):psc.index("EndFunction", psc.index("Function LinkSquad("))]
        self.assertIn("SetLinkedRef(target)", body)
        self.assertIn("EvaluatePackage()", body)
        self.assertNotIn("ForceRefTo", psc)                 # no alias package (P9: the alias package never walked)
        self.assertNotIn("PathToReference", psc)

    def test_merged_world_placement(self):
        psc = read(PSC)
        body = psc[psc.index("Function PlaceWaymarker("):psc.index("EndFunction", psc.index("Function PlaceWaymarker("))]
        self.assertIn("m.MoveTo(player, tx - player.GetPositionX(), ty - player.GetPositionY()", body)
        self.assertIn("MoveToNearestNavmeshLocation()", body)
        start = psc[psc.index("Function StartRung1a("):psc.index("EndFunction", psc.index("Function StartRung1a("))]
        self.assertIn("player.IsInInterior() || pd > PlaceRadius", start)
        self.assertIn("NodeX[Rung1aFrom] + MergeOffsetX", start)

    def test_rung1b_waits_for_rung1a(self):
        psc = read(PSC)
        body = psc[psc.index("Function StartRung1b("):psc.index("EndFunction", psc.index("Function StartRung1b("))]
        self.assertIn("if !rung1aPassed && !force", body)
        self.assertIn("reason=rung1a_not_passed", body)
        fin = psc[psc.index("Function Finish1b("):psc.index("EndFunction", psc.index("Function Finish1b("))]
        self.assertIn("&& !forced", fin)


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.g = make_alife.load_graph()

    def test_committed_graph_is_valid(self):
        self.assertEqual(make_alife.graph_problems(self.g), [])
        self.assertEqual(len(self.g["nodes"]), len(make_alife.ANCHORS))
        self.assertEqual([n["edid"] for n in self.g["nodes"]], list(make_alife.ANCHORS))
        self.assertLessEqual(len(self.g["edges"]), make_alife.ARRAY_CAP)

    def test_committed_rungs(self):
        r1a, r1b = self.g["rung1a"], self.g["rung1b"]
        self.assertEqual((r1a["from_edid"], r1a["to_edid"]), make_alife.RUNG1A)
        self.assertEqual((r1b["from_edid"], r1b["goal_edid"]), make_alife.RUNG1B)
        path, length = make_alife.route(self.g, r1b["from"], r1b["goal"])
        self.assertEqual(path, r1b["route"])
        self.assertAlmostEqual(length, r1b["length_m"], places=2)
        self.assertEqual(r1b["expected_ticks"], make_alife.expected_ticks(length))
        self.assertGreaterEqual(len(path), 3, "rung 1b crosses at least one intermediate node")
        start = self.g["nodes"][r1a["from"]]
        self.assertNotEqual(start["z"], 0.0, "rung 1a's start has a real height (its map marker), not a cell centre")
        self.assertIn("RedRocketTruckStopMapMarker", start["spot"])

    def test_committed_graph_has_no_game_text(self):
        for n in self.g["nodes"]:
            self.assertRegex(n["edid"], r"^\w+$")
            self.assertRegex(n["id"], r"^(LCTN|XMRK|TRIG):0x[0-9A-F]{8}$")

    def test_build_contracts_relays_and_keeps_anchor_spots(self):
        places, edges = tiny_graph()
        g = make_alife.build_subgraph(places, edges, anchors=("A", "B", "C", "D"), keep=1, spot_from={},
                                      rung1a=("A", "B"), rung1b=("A", "C"))
        pairs = {(e["u"], e["v"]): e["len_m"] for e in g["edges"]}
        self.assertEqual(pairs.get((0, 3)), 31.0, "A-R-D contracts to one edge of 14 + 17 m")
        self.assertNotIn((0, 2), pairs, "A-C passes B, so it is no candidate shorter than A-B-C... ")
        self.assertEqual(g["rung1b"]["route"], [0, 1, 2])
        self.assertEqual(make_alife.graph_problems(g), [])

    def test_build_bridges_to_connect(self):
        places = [place("L:A", "A", 0, 0), place("L:B", "B", 5, 0), place("L:C", "C", 100, 0),
                  place("L:D", "D", 105, 0)]
        edges = [edge("L:A", "L:B", 5), edge("L:C", "L:D", 5), edge("L:B", "L:C", 95)]
        g = make_alife.build_subgraph(places, edges, anchors=("A", "B", "C", "D"), keep=1, spot_from={},
                                      rung1a=("A", "B"), rung1b=("A", "D"))
        self.assertIn({"u": 1, "v": 2, "len_m": 95.0}, g["edges"])

    def test_build_refuses_missing_and_disconnected(self):
        places, edges = tiny_graph()
        with self.assertRaises(ValueError):
            make_alife.build_subgraph(places, edges, anchors=("A", "Z"), spot_from={}, rung1a=("A", "Z"))
        places.append(place("L:E", "E", 50, 50))
        with self.assertRaises(ValueError):
            make_alife.build_subgraph(places, edges, anchors=("A", "B", "E"), spot_from={}, rung1a=("A", "B"), rung1b=("A", "B"))

    def test_spot_override(self):
        places, edges = tiny_graph()
        places.append(place("X:1", "", 1.5, 2.5, z=7.25, xmrk_edid="AMarker"))
        g = make_alife.build_subgraph(places, edges, anchors=("A", "B", "C", "D"),
                                      spot_from={"A": ("xmrk_edid", "AMarker")},
                                      rung1a=("A", "B"), rung1b=("A", "C"))
        a = g["nodes"][0]
        self.assertEqual((a["x"], a["y"], a["z"]), (1.5, 2.5, 7.25))
        self.assertEqual(a["spot"], "xmrk_edid AMarker")

    def test_problems_catch_bad_graphs(self):
        g = json.loads(json.dumps(self.g))
        g["edges"].append({"u": 0, "v": 0, "len_m": 1.0})
        self.assertTrue(make_alife.graph_problems(g))
        g = json.loads(json.dumps(self.g))
        g["edges"][0]["len_m"] = float("nan")
        self.assertTrue(make_alife.graph_problems(g))
        g = json.loads(json.dumps(self.g))
        g["nodes"] = g["nodes"] * 7                                       # 140 nodes
        self.assertTrue(any("Papyrus array" in p for p in make_alife.graph_problems(g)))
        g = json.loads(json.dumps(self.g))
        g["rung1b"]["length_m"] += 5
        self.assertTrue(any("rung1b" in p for p in make_alife.graph_problems(g)))
        g = json.loads(json.dumps(self.g))
        lone = len(g["nodes"])
        g["nodes"].append(dict(g["nodes"][0], edid="Lonely"))
        self.assertIn("the graph is not connected", make_alife.graph_problems(g))
        self.assertEqual(lone, 20)


class OfflineTests(unittest.TestCase):
    def line_graph(self, lengths, caps=None):
        n = len(lengths) + 1
        caps = caps or [2] * n
        return {"nodes": [{"edid": f"N{i}", "x": float(i * 10), "y": 0.0, "z": 0.0, "cap": caps[i]} for i in range(n)],
                "edges": [{"u": i, "v": i + 1, "len_m": L} for i, L in enumerate(lengths)]}

    def test_arrival_tick_is_the_analytic_one(self):
        g = make_alife.load_graph()
        r = g["rung1b"]
        events, tick = make_alife.offline_walk(g, r["route"])
        self.assertEqual(tick, r["expected_ticks"])
        self.assertEqual(tick, math.ceil(r["length_m"] / 1.35 - 1e-4))
        arrivals = [d for t, k, d in events if k == "node_arrive"]
        self.assertEqual(arrivals, r["route"][1:])

    def test_progress_is_monotonic_at_speed(self):
        g = self.line_graph([10.0, 3.0, 20.0])
        events, tick = make_alife.offline_walk(g, [0, 1, 2, 3])
        prog = [d for t, k, d in events if k == "tick"]
        for a, b in zip(prog, prog[1:-1]):
            self.assertAlmostEqual(b - a, 1.35, places=6)
        self.assertEqual(prog[-1], 33.0)
        self.assertEqual(tick, make_alife.expected_ticks(33.0))

    def test_several_nodes_in_one_tick_carry_the_remainder(self):
        g = self.line_graph([0.5, 0.5, 5.0])
        events, tick = make_alife.offline_walk(g, [0, 1, 2, 3])
        first = [(k, d) for t, k, d in events if t == 1]
        self.assertEqual([k for k, _ in first], ["node_arrive", "edge_step", "node_arrive", "edge_step", "tick"])
        self.assertAlmostEqual(first[-1][1], 1.35)

    def test_garrison_rule_and_reroute(self):
        self.assertTrue(make_alife.admit(1, 0))
        self.assertFalse(make_alife.admit(1, 1))
        self.assertFalse(make_alife.admit(0, 0), "a relay never garrisons")
        g = self.line_graph([10.0, 10.0, 10.0], caps=[2, 0, 1, 2])
        self.assertEqual(make_alife.plan_offline(g, 0, 2)[0], [0, 1, 2])
        path, length = make_alife.plan_offline(g, 0, 2, {2: 1})
        self.assertEqual(path, [0, 1, 2, 3], "a full goal reroutes to the nearest node with room")
        with self.assertRaises(ValueError):
            make_alife.plan_offline(g, 0, 2, {2: 1, 3: 2})

    def test_dijkstra_ties_take_the_lower_index(self):
        g = {"nodes": [{"cap": 1}] * 4,
             "edges": [{"u": 0, "v": 2, "len_m": 5.0}, {"u": 0, "v": 1, "len_m": 5.0},
                       {"u": 1, "v": 3, "len_m": 5.0}, {"u": 2, "v": 3, "len_m": 5.0}]}
        self.assertEqual(make_alife.route(g, 0, 3)[0], [0, 1, 3])

    def test_waypoints_and_pool_reuse(self):
        g = make_alife.load_graph()
        a = make_alife.merged(g["nodes"][g["rung1a"]["from"]])
        b = make_alife.merged(g["nodes"][g["rung1a"]["to"]])
        pts = make_alife.waypoints(a, b)
        self.assertEqual(len(pts), math.ceil(g["rung1a"]["straight_m"] / 40.0))
        self.assertEqual(tuple(round(v, 6) for v in pts[-1]), tuple(round(v, 6) for v in b))
        gaps = [math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip([a] + pts, pts)]
        self.assertLessEqual(max(gaps), 40.0 + 1e-9)
        slots = [make_alife.pool_slot(i, 4) for i in range(len(pts))]
        self.assertEqual(slots[:5], [0, 1, 2, 3, 0], "the fifth waypoint reuses the first marker")
        self.assertEqual(len(make_alife.waypoints((0, 0, 0), (10000, 0, 0))), 16)
        self.assertEqual(len(make_alife.waypoints((0, 0, 0), (1, 0, 0))), 1)


def log_1a(teleport=False, spread=3.0, members=4, arrive=True, snap=0.2, forced_cells=2):
    rt = 100.0
    out = []

    def line(msg):
        nonlocal rt
        rt += 0.1
        out.append(f"[11/16/2026 - 01:00:00AM] FO4SF_ALIFE rt={rt:.6f} {msg}")
    line("step=init nodes=20 edges=36 pool=4 squad_size=4 mode=0 offset=-1200.000000,-2700.000000")
    line("step=rung1a_waymarker_place waypoint=-1 marker=33558544 slot=0 target=-2191.1,-1555.0 pos=1 snapped_dz=-0.2 cell=1")
    for i in range(4):
        line(f"step=rung1a_spawn member={i} id={4278190080 + i} pos=1,2,3 z_snap_m={snap:.6f} loaded=True cell=5 world=6")
    line("step=rung1a_waymarker_place waypoint=0 marker=33558544 slot=0 target=1,2 pos=1 snapped_dz=0.0 cell=1")
    line("step=rung1a_start from=2 to=3 route_m=165.4 waypoints=5 pool=4 members=4 dest=-2061.2,-1657.5 player_m=20.0")
    for k in range(60):
        step = 9.0 if teleport and k == 30 else 1.2
        line(f"step=rung1a_progress t={2.0 * (k + 1):.6f} wp={min(4, k // 12)}/5 leader_wp_m=20.0 leader_dest_m={165 - 2.4 * k:.6f} "
             f"leader_3d_wp_m=20.5 spread_m={spread:.6f} step_mps={step:.6f} alive=4 loaded=4 arrived=0 cell=7 "
             f"cells_crossed={min(forced_cells, k // 20)} player_m=40.0 package=197059")
        if k in (12, 24, 36, 48):
            line(f"step=rung1a_waymarker_advance t={2.0 * (k + 1):.6f} wp={k // 12}/5 marker=1 reused={'True' if k == 48 else 'False'} leader_dest_m=50")
    if arrive:
        line(f"step=rung1a_arrived t=122.000000 members={members} alive={members} cells_crossed={forced_cells}")
        line("step=garrison_cap_check who=rung1a node=3 cap=1 occupied=0 admitted=True")
        line(f"step=summary rung=1a result=PASS why=arrived t=122.0 members={members}/4")
    return out


def log_1b(ticks=None, forced=False, player_m=3200.0, live=0, skip_tick=None, route_m=823.38):
    out = []
    rt = 500.0
    want = make_alife.expected_ticks(route_m) if ticks is None else ticks

    def line(msg):
        nonlocal rt
        rt += 0.01
        out.append(f"FO4SF_ALIFE rt={rt:.6f} {msg}")
    line(f"step=rung1b_start from=2 goal=12 hops=3 route_m={route_m:.6f} expected_m=823.380005 speed=1.350000 "
         f"step_s=1.000000 ticks_per_timer=10 live_actors={live} removed=4 player_m={player_m:.6f} forced={forced}")
    line("step=rung1b_route nodes=2>4>11>12 route_m=823.38")
    p = 0.0
    for t in range(1, want + 1):
        if t == skip_tick:
            continue
        p = min(route_m, 1.35 * t) if t < want else route_m
        line(f"step=rung1b_tick tick={t} hop=0/3 from=2 to=4 walked_m=1 edge_m=202 progress_m={p:.6f} pos=1,2 live_actors={live}")
    line("step=rung1b_node_arrive tick=610 node=12 hop=3/3 done_m=823.38 cap=3")
    line("step=garrison_cap_check who=rung1b node=12 cap=3 occupied=0 admitted=True")
    line("step=summary rung=1b result=PASS reached=True")
    return out


class JudgeTests(unittest.TestCase):
    def test_good_rung1a(self):
        r = make_alife.judge(log_1a())["rung1a"]
        self.assertTrue(r["pass"], r["criteria"])
        self.assertEqual(r["samples"], 60)

    def test_rung1a_failures(self):
        self.assertFalse(make_alife.judge(log_1a(teleport=True))["rung1a"]["criteria"]["no_teleport"])
        self.assertFalse(make_alife.judge(log_1a(spread=30.0))["rung1a"]["criteria"]["cohesion"])
        self.assertFalse(make_alife.judge(log_1a(members=3))["rung1a"]["criteria"]["arrived_all"])
        self.assertFalse(make_alife.judge(log_1a(arrive=False))["rung1a"]["pass"])
        self.assertFalse(make_alife.judge(log_1a(snap=0.8))["rung1a"]["criteria"]["z_snap"])
        self.assertFalse(make_alife.judge(log_1a(forced_cells=0))["rung1a"]["criteria"]["cells_crossed"])

    def test_script_summary_is_not_trusted(self):
        lines = [x for x in log_1a(teleport=True)]
        self.assertIn("result=PASS", lines[-1])
        self.assertFalse(make_alife.judge(lines)["rung1a"]["pass"])

    def test_good_rung1b_after_rung1a(self):
        res = make_alife.judge(log_1a() + log_1b())
        self.assertTrue(res["rung1a"]["pass"])
        self.assertTrue(res["rung1b"]["pass"], res["rung1b"]["criteria"])
        self.assertEqual(res["rung1b"]["expected_ticks"], 610)

    def test_rung1b_own_session(self):
        r = make_alife.judge(log_1b())["rung1b"]
        self.assertTrue(r["pass"], r["criteria"])

    def test_rung1b_failures(self):
        self.assertFalse(make_alife.judge(log_1b(forced=True))["rung1b"]["pass"])
        self.assertFalse(make_alife.judge(log_1b(player_m=200.0))["rung1b"]["criteria"]["player_far"])
        self.assertFalse(make_alife.judge(log_1b(live=4))["rung1b"]["criteria"]["no_live_actors"])
        self.assertFalse(make_alife.judge(log_1b(ticks=600))["rung1b"]["criteria"]["arrival_tick"])
        self.assertTrue(make_alife.judge(log_1b(ticks=611))["rung1b"]["criteria"]["arrival_tick"], "within one tick")
        self.assertFalse(make_alife.judge(log_1b(skip_tick=100))["rung1b"]["criteria"]["step_per_tick"])
        self.assertFalse(make_alife.judge(log_1b(route_m=830.0))["rung1b"]["criteria"]["route_matches_plan"])

    def test_forced_rung1b_before_rung1a_is_not_loaded_first(self):
        res = make_alife.judge(log_1b(forced=True) + log_1a())
        self.assertFalse(res["rung1b"]["criteria"]["loaded_first"])

    def test_other_lines_ignored(self):
        res = make_alife.judge(["FO4SF_MISSION rt=1 stage 10", "garbage"] + log_1a())
        self.assertTrue(res["rung1a"]["pass"])
        self.assertIsNone(res["rung1b"])
        self.assertEqual(make_alife.judge([]), {"rung1a": None, "rung1b": None})


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write(self, rel, data):
        p = os.path.join(self.tmp, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
        return p

    def plan(self):
        stage = os.path.join(self.tmp, "stage")
        plugin = self.write("stage/FO4SFALife.esm", b"plugin")
        pex = self.write("stage/Data/Scripts/FO4SF_ALifeControllerQuest.pex", b"pex")
        core = self.write("core/FO4TerrainCore.esm", b"core")
        raider = self.write("raider/FO4ActorRaider.esm", b"raider")
        plan = {"kind": "alife", "plugin": "FO4SFALife.esm", "plugin_sha256": make_alife.sha256(plugin),
                "script": make_alife.SCRIPT, "script_sha256": make_alife.sha256(pex),
                "masters_sha256": {"Starfield.esm": "x", "FO4TerrainCore.esm": make_alife.sha256(core),
                                   "FO4ActorRaider.esm": make_alife.sha256(raider)}}
        with open(os.path.join(stage, "plan.json"), "w", encoding="utf-8") as f:
            json.dump(plan, f)
        return stage, raider, plan

    def test_fold_then_verify(self):
        stage, raider, plan = self.plan()
        out = os.path.join(self.tmp, "folded")
        args = make_alife.main.__globals__["argparse"].Namespace(stage=stage, core_dir=os.path.join(self.tmp, "core"),
                                                                  out=out, raider=raider)
        self.assertEqual(make_alife.fold(args), 0)
        self.assertEqual(make_alife.verify_dir(out, plan, raider), [])
        self.write("folded/FO4TerrainCore.esm", b"rebuilt core")
        self.assertTrue(any("FO4TerrainCore" in p for p in make_alife.verify_dir(out, plan, raider)))
        with self.assertRaises(SystemExit):
            make_alife.fold(args)                                       # an existing out is refused

    def test_verify_missing_script(self):
        stage, raider, plan = self.plan()
        os.remove(os.path.join(stage, "Data", "Scripts", make_alife.SCRIPT + ".pex"))
        self.write("stage/FO4TerrainCore.esm", b"core")
        self.assertTrue(any(p.startswith("script") for p in make_alife.verify_dir(stage, plan, raider)))

    def test_load_plan_refuses_other_kinds(self):
        p = self.write("plan.json", json.dumps({"kind": "mission"}).encode())
        with self.assertRaises(SystemExit):
            make_alife.load_plan(p)


@unittest.skipUnless(shutil.which("dotnet") and os.environ.get("FO4SF_DOTNET_TESTS") == "1",
                     "set FO4SF_DOTNET_TESTS=1 with a dotnet SDK on PATH to run the C# self-test")
class DotnetSelfTest(unittest.TestCase):
    def test_selftest(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run(["dotnet", "run", "-c", "Release", "--project", os.path.join(ROOT, "dotnet", "ALife"), "--",
                                "selftest", d], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-2000:])
            self.assertIn("selftest ok", r.stdout)


if __name__ == "__main__":
    unittest.main()
