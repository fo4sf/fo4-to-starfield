"""fo4sf.creature_race: records, events, left / right pairs, manifests (synthetic; no game data)."""
import math
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fo4sf import creature_race as cr  # noqa: E402
from fo4sf import handy_race as hr  # noqa: E402
from fo4sf.planet import esm  # noqa: E402

Z = esm.zbytes
TEMPLATE_CLIPS = "Actors\\HexapodA\\Animations"


def template_race():
    subs = [(b"EDID", Z("HexapodARace")), (b"FULL", b"\x01\x00\x00\x00"), (b"DESC", b"\x02\x00\x00\x00"),
            (b"WNAM", struct.pack("<I", 0x111)), (b"GNAM", struct.pack("<I", 0x222)),
            (b"ANAM", Z("Actors\\HexapodA\\CharacterAssets\\skeleton.nif")),
            (b"NAM5", Z("actors\\hexapoda\\characterassets\\skeleton.rig")),
            (b"NAM6", Z(cr.GRAPH_DIR + "Creature_Root.agx")), (b"DNAM", Z(TEMPLATE_CLIPS)),
            (b"ATKD", b"\x00" * 48), (b"ATKE", Z("MeleeAttack01")), (b"ATKW", struct.pack("<I", 7)),
            (b"ATKD", b"\x01" * 48), (b"ATKE", Z("MeleeAttack_Tail01")), (b"ATKW", struct.pack("<I", 8)),
            (b"ATKD", b"\x02" * 48), (b"ATKE", Z("MeleeAttack_Bite01")), (b"ATKW", struct.pack("<I", 9)),
            (b"QNAM", struct.pack("<I", 5)), (b"ZNAM", Z("C_spine4")), (b"QNAM", struct.pack("<I", 6)),
            (b"ZNAM", Z("C_Tail")), (b"UNWP", struct.pack("<I", 0x333)),
            (b"SGNM", Z(cr.STRAFING_GRAPH)), (b"SAPT", Z(TEMPLATE_CLIPS)), (b"SRAF", struct.pack("<I", 1)),
            (b"SGNM", Z(cr.FURNITURE_GRAPH)), (b"SAPT", Z("actors\\hexapoda\\animations\\furniture\\wallow")),
            (b"SRAF", struct.pack("<I", 2)), (b"PTOP", b"\x00\x00\x40\x40")]
    return esm.Record(b"RACE", 0x2CCAAA, subs)


BONES = {"C_spine4": "Head", "C_Tail": "Tail1"}


class TestRace(unittest.TestCase):
    def setUp(self):
        self.paths = cr.CreaturePaths("Radroach")

    def test_paths(self):
        p = self.paths
        self.assertEqual(p.clips, "Actors\\FO4SF\\Radroach\\Animations")
        self.assertEqual(p.skeleton_rig, "FO4SF\\Actors\\Radroach\\CharacterAssets\\skeleton.rig")
        self.assertEqual(p.mesh, "FO4SF\\Actors\\Radroach\\radroach.nif")
        self.assertEqual(p.data_rel(p.mesh), "Meshes/FO4SF/Actors/Radroach/radroach.nif")
        for bad in ("Rad roach", "1Roach", "Roach|"):
            with self.assertRaises(cr.CreatureError):
                cr.CreaturePaths(bad)

    def test_rewrite_folder_ignores_case(self):
        self.assertEqual(cr.rewrite_folder("actors\\hexapoda\\animations\\furniture", TEMPLATE_CLIPS, "X\\Y"),
                         "X\\Y\\furniture")

    def test_attack_groups(self):
        groups = cr.attack_groups(template_race().subs)
        self.assertEqual([g[2] for g in groups], ["MeleeAttack01", "MeleeAttack_Tail01", "MeleeAttack_Bite01"])
        self.assertTrue(all(b - a == 3 for a, b, _t in groups))

    def test_build_race(self):
        t = template_race()
        rec, rep = cr.build_creature_race(t, 0x1000800, 0x1000801, 0x1000803, self.paths, "Radroach",
                                          "FO4SF_RadroachRace", BONES, attack_tags={"MeleeAttack01", "MeleeAttack_Bite01"},
                                          main_folder_for_empty_sets=[self.paths.clips.lower() + "\\furniture\\wallow"])
        self.assertEqual(rec.edid, "FO4SF_RadroachRace")
        self.assertEqual(esm.zstring(rec.get(b"FULL")), "Radroach")
        self.assertEqual(esm.zstring(rec.get(b"DESC")), "")
        self.assertEqual(struct.unpack("<I", rec.get(b"GNAM"))[0], 0x1000801)
        self.assertEqual(struct.unpack("<I", rec.get(b"WNAM"))[0], 0x1000803)
        self.assertEqual(esm.zstring(rec.get(b"NAM5")), self.paths.skeleton_rig)
        self.assertEqual(esm.zstring(rec.get(b"ANAM")), self.paths.skeleton_nif)
        self.assertEqual(esm.zstring(rec.get(b"DNAM")), self.paths.clips)
        self.assertEqual([esm.zstring(d) for d in rec.all(b"ATKE")], ["MeleeAttack01", "MeleeAttack_Bite01"])
        self.assertEqual(len(rec.all(b"ATKD")), 2)
        self.assertEqual([struct.unpack("<I", d)[0] for d in rec.all(b"ATKW")], [7, 9])
        self.assertEqual(rep["dropped_attacks"], ["MeleeAttack_Tail01"])
        self.assertEqual(cr.race_bone_names(rec), ["Head", "Tail1"])
        sets = hr.race_subgraph_sets(rec)
        self.assertEqual(sets[1], (cr.STRAFING_GRAPH, [self.paths.clips]))
        self.assertEqual(sets[2], (cr.FURNITURE_GRAPH, [self.paths.clips + "\\furniture\\wallow", self.paths.clips]))
        # everything else byte for byte
        changed = {b"EDID", b"FULL", b"DESC", b"GNAM", b"WNAM", b"ANAM", b"NAM5", b"DNAM", b"ZNAM", b"SAPT"}
        keep_t = [(s, d) for s, d in t.subs if s not in changed and not s.startswith(b"ATK")]
        keep_n = [(s, d) for s, d in rec.subs if s not in changed and not s.startswith(b"ATK")]
        self.assertEqual(keep_t, keep_n)

    def test_build_race_refusals(self):
        t = template_race()
        with self.assertRaises(cr.CreatureError):          # an attack bone without a partner
            cr.build_creature_race(t, 1, 2, 3, self.paths, "R", "E", {"C_spine4": "Head"})
        with self.assertRaises(cr.CreatureError):          # no attack left
            cr.build_creature_race(t, 1, 2, 3, self.paths, "R", "E", BONES, attack_tags={"Nothing"})
        rec, rep = cr.build_creature_race(t, 1, 2, 3, self.paths, "R", "E", BONES)   # no filter: all kept
        self.assertEqual(len(rec.all(b"ATKD")), 3)
        self.assertEqual(rep["appended_main_folder"], [])

    def test_build_bptd(self):
        part = [(b"BPTN", b"\x77\x65\x00\x00"), (b"BPNN", Z("C_Head")), (b"BPNT", Z("C_Head")),
                (b"BPD2", b"\x00" * 34), (b"NAM4", Z("BASE Meshes\\Actors\\HexapodA\\CharacterAssets\\skeleton_ref.nif")),
                (b"ENAM", Z("C_Head")), (b"FNAM", Z("C_Head2")), (b"DNAM", b"\x00")]
        root = [(b"BPTN", b"\x78\x65\x00\x00"), (b"BPNN", Z("Root")), (b"BPNT", Z("Root")), (b"BPD2", b"\x00" * 34)]
        t = esm.Record(b"BPTD", 0x2CCAAB, [(b"EDID", Z("HexapodABodyPartData")),
                                          (b"MODL", Z("Actors\\HexapodA\\CharacterAssets\\skeleton_ref.nif"))] + part + root)
        self.assertEqual(cr.bptd_bones(t), ["C_Head", "C_Head2", "Root"])
        m = {"C_Head": "Head", "C_Head2": "Jaw", "Root": "Root"}
        rec = cr.build_creature_bptd(t, 0x1000801, "FO4SF_X", self.paths, m, ["Root", "COM", "Head", "Jaw"])
        self.assertEqual(cr.bptd_bones(rec), ["Head", "Jaw", "Root"])
        self.assertEqual(esm.zstring(rec.get(b"MODL")), self.paths.skeleton_ref)
        self.assertIn("Meshes\\" + self.paths.skeleton_ref, esm.zstring(rec.get(b"NAM4")))
        with self.assertRaises(cr.CreatureError):
            cr.build_creature_bptd(t, 1, "E", self.paths, {"C_Head": "Head", "Root": "Root"}, ["Root", "Head"])
        with self.assertRaises(cr.CreatureError):
            cr.build_creature_bptd(t, 1, "E", self.paths, m, ["Root", "Head"])      # Jaw not in the rig


class TestEvents(unittest.TestCase):
    def test_feet_sync_and_melee(self):
        c = cr.CreatureClip("WalkForward", "WalkForward", "W.hkx", is_state=1, sync=True)
        ev = cr.creature_events(c, [(0.5, "FootLeft"), (0.25, "FootRight"), (0.9, "FootLeft"), (0.1, "SoundPlay.X"),
                                    (0.3, "startAllowRotation")], 31)
        self.assertEqual([(f, n) for f, n, _ in ev], [(8, "FootRight"), (8, "SyncRightFoot"), (15, "FootLeft"),
                                                     (15, "SyncLeftFoot"), (27, "FootLeft")])
        m = cr.CreatureClip("MeleeAttack01", "MeleeAttack01", "A.hkx")
        ev = cr.creature_events(m, [(0.2, "weaponSwing"), (0.3, "preHitFrame"), (0.5, "HitFrame")], 31)
        self.assertEqual([n for _f, n, _p in ev], ["weaponSwing", "preHitFrame", "HitFrame"])

    def test_ragdoll_fire_drop_and_map(self):
        d = cr.CreatureClip("Death_Left01", "Death_Left01", "D.hkx", is_state=1, add_events=cr.DEATH)
        self.assertEqual({f for f, _n, _p in cr.creature_events(d, [(0.4, "Ragdoll")], 21)}, {12})
        self.assertEqual({f for f, _n, _p in cr.creature_events(d, [], 21)}, {20})
        now = cr.CreatureClip("Death_Backward01", "Death_Backward01", "I.hkx", add_events=cr.DEATH_AT_ONCE)
        self.assertEqual({f for f, _n, _p in cr.creature_events(now, [], 2)}, {0})
        spit = cr.CreatureClip("MeleeAttack01", "MeleeAttack01", "R.hkx", add_events=cr.FIRE_AS_MELEE,
                               drop_events=("WeaponFire",))
        ev = cr.creature_events(spit, [(0.4, "weaponFire")], 21)
        self.assertEqual(sorted(n for _f, n, _p in ev), ["HitFrame", "preHitFrame", "weaponSwing"])
        self.assertEqual({f for f, _n, _p in ev}, {12})
        walk = cr.CreatureClip("WalkForward", "WalkForward", "W.hkx", sync=True)
        ev = cr.creature_events(walk, [(0.1, "FootFront"), (0.2, "FootBack")], 11,
                                event_map={"FootFront": "FootLeft", "FootBack": "FootRight"})
        self.assertIn((3, "SyncLeftFoot", ""), ev)
        self.assertIn((6, "SyncRightFoot", ""), ev)
        with self.assertRaises(cr.CreatureError):
            cr.creature_events(cr.CreatureClip("X", "X", "X", add_events=(("middle", "E"),)), [], 3)

    def test_mirror_event_name(self):
        self.assertEqual(cr.mirror_event_name("FootLeft"), "FootRight")
        self.assertEqual(cr.mirror_event_name("SyncRightFoot"), "SyncLeftFoot")
        self.assertEqual(cr.mirror_event_name("HitFrame"), "HitFrame")


class TestPairs(unittest.TestCase):
    def test_names_and_positions(self):
        names = ["Root", "COM", "1LLeg1", "1RLeg1", "LWing", "RWing", "Head", "RArmHand", "LArmHand", "Weapon",
                 "WeaponLeft"]
        parents = [-1, 0, 1, 1, 1, 1, 1, 1, 1, 7, 8]
        world = [(0, 0, 0), (0, 0, 1), (-1, 0, 1), (1.02, 0, 1), (-0.5, 1, 1), (0.5, 1, 1), (0, 2, 1),
                 (2, 1, 1), (-2, 1, 1), (2.1, 1.2, 1), (-2.1, 1.2, 1)]
        pairs, rep = cr.mirror_pairs(names, parents, world, tol=0.05)
        idx = {n: i for i, n in enumerate(names)}
        self.assertEqual(pairs[idx["1LLeg1"]], idx["1RLeg1"])
        self.assertEqual(pairs[idx["LWing"]], idx["RWing"])
        self.assertEqual(pairs[idx["RArmHand"]], idx["LArmHand"])
        self.assertEqual(pairs[idx["Weapon"]], idx["WeaponLeft"])
        self.assertEqual(pairs[idx["Head"]], idx["Head"])
        self.assertEqual(rep["paired_by_position"], ["Weapon<->WeaponLeft"])
        self.assertAlmostEqual(rep["largest_rest_asymmetry"], 0.02, places=6)
        self.assertEqual(rep["off_centre_without_partner"], [])

    def test_parent_mismatch_raises(self):
        names = ["Root", "LArm", "RArm", "LHand"]
        parents = [-1, 0, 0, 2]                     # LHand hangs under RArm: its partner set is inconsistent
        world = [(0, 0, 0), (-1, 0, 0), (1, 0, 0), (-1.5, 0, 0)]
        with self.assertRaises(cr.CreatureError):
            cr.mirror_pairs(names, parents, world, tol=0.05)


class TestManifests(unittest.TestCase):
    def setUp(self):
        self.paths = cr.CreaturePaths("Radroach")
        self.race, _ = cr.build_creature_race(
            template_race(), 1, 2, 3, self.paths, "Radroach", "FO4SF_RadroachRace", BONES,
            main_folder_for_empty_sets=[self.paths.clips.lower() + "\\furniture\\wallow"])
        self.clips = [cr.WrittenClip(self.paths.clips, "Idle.af", "Idle", 6.0),
                      cr.WrittenClip(self.paths.clips, "MeleeAttack01.af", "MeleeAttack01", 1.0,
                                     [(8, "weaponSwing"), (15, "HitFrame"), (20, "FootLeft")]),
                      cr.WrittenClip(self.paths.clips, "Threat_Assess01.af", "Threat_Assess01", 1.8)]
        self.tags = {cr.STRAFING_GRAPH.lower(): {"Idle", "MeleeAttack01"}, cr.FURNITURE_GRAPH.lower(): {"Idle"}}

    def test_files_and_keys(self):
        files, rep = cr.creature_manifests(self.race, self.clips, self.tags)
        k1 = hr.manifest_key(cr.STRAFING_GRAPH, [self.paths.clips])
        k2 = hr.manifest_key(cr.FURNITURE_GRAPH, [self.paths.clips + "\\furniture\\wallow", self.paths.clips])
        self.assertEqual(sorted(rep["keys"]), sorted([str(k1), str(k2)]))
        key, listed = cr.parse_file_data(files[f"Meshes\\AnimTextData\\AnimationFileData\\{k1}.txt"])
        self.assertEqual(key, k1)
        self.assertEqual(listed, [self.paths.clips + "\\Idle.af", self.paths.clips + "\\MeleeAttack01.af"])
        self.assertEqual(rep["keys"][str(k1)]["tags_not_played"], ["Threat_Assess01"])
        graph, tags, recs = hr.parse_animation_offsets(files[f"Meshes\\AnimTextData\\AnimationOffsets\\{k1}.txt"])
        self.assertEqual(graph, cr.STRAFING_GRAPH)
        self.assertEqual(tags, [("MeleeAttack01", self.paths.clips + "\\MeleeAttack01")])
        self.assertEqual([n for _t, n in recs[0].events], ["weaponSwing", "HitFrame"])
        self.assertAlmostEqual(recs[0].events[1][0], 0.5)
        self.assertEqual(cr.parse_file_data(files[f"Meshes\\AnimTextData\\AnimationFileData\\{k2}.txt"])[1],
                         [self.paths.clips + "\\Idle.af"])
        self.assertIn("Meshes\\AnimTextData\\GeneratedSubgraphData\\fo4sf_radroachrace.txt", files)
        self.assertEqual(files[f"Meshes\\AnimTextData\\DynamicIdleData\\{k1}.txt"], b"Version 1\n")

    def test_unknown_graph_refused(self):
        with self.assertRaises(cr.CreatureError):
            cr.creature_manifests(self.race, self.clips, {cr.STRAFING_GRAPH.lower(): {"Idle"}})

    def test_keys_and_collisions(self):
        names = ["meshes/animtextdata/animationfiledata/12.txt", "meshes\\animtextdata\\animationoffsets\\12.txt",
                 "meshes/animtextdata/dynamicidledata/7.txt", "meshes/animtextdata/tables/graphs/x.agx",
                 "meshes/actors/a/b.af"]
        v = cr.vanilla_manifest_keys(names)
        self.assertEqual(v["animationfiledata"], {12})
        self.assertEqual(v["animationoffsets"], {12})
        self.assertEqual(v["dynamicidledata"], {7})
        self.assertEqual(cr.key_collisions([12, 99], v)["animationfiledata"], [12])
        self.assertFalse(any(cr.key_collisions([99], v).values()))

    def test_graph_tag_sets(self):
        r = template_race()
        k = hr.manifest_key(cr.STRAFING_GRAPH, [TEMPLATE_CLIPS])
        lists = {k: hr.animation_file_data(k, [TEMPLATE_CLIPS + "\\walkforward.af", TEMPLATE_CLIPS + "\\idle.af"])}
        tags = {"walkforward.af": "WalkForward", "idle.af": "Idle"}
        out = cr.graph_tag_sets([r], lists.get, lambda p: tags[p.split("\\")[-1]], [cr.STRAFING_GRAPH])
        self.assertEqual(out, {cr.STRAFING_GRAPH.lower(): {"WalkForward", "Idle"}})
        with self.assertRaises(cr.CreatureError):
            cr.parse_file_data(b"3\n1\n5\n2\nonly_one\n")


class TestSpecs(unittest.TestCase):
    def test_every_spec(self):
        for key, spec in cr.CREATURES.items():
            with self.subTest(key):
                self.assertEqual(spec.key, key)
                cr.CreaturePaths(spec.name)
                tags = [c.tag for c in spec.clips]
                files = [c.filename.lower() for c in spec.clips]
                self.assertEqual(len(tags), len(set(tags)), "a tag twice")
                self.assertEqual(len(files), len(set(files)), "a file name twice")
                for c in spec.clips:
                    self.assertIn(c.how, ("direct", "reuse", "mirror"))
                    self.assertTrue(c.fo4, c.tag)
                    self.assertTrue(c.fo4.lower().endswith(".hkx"))
                    self.assertTrue(all(ch.isalnum() or ch == "_" for ch in c.filename), c.filename)
                for t in ("Idle", "WalkForward", "TurnInPlace_Left90", "TurnInPlace_Right90", "Death_Backward01"):
                    self.assertIn(t, tags)
                self.assertFalse(set(spec.bat.split(".")[0]) & set("mnvMNV"), spec.bat)
                self.assertTrue(all(isinstance(v, str) and v for v in spec.bone_map.values()))


if __name__ == "__main__":
    unittest.main()
