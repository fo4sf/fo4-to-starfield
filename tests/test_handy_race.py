"""Robot animation task D: the Handy RACE/BPTD clone, the manifest key hash, the manifest writers and the clip map
(fo4sf.handy_race). Synthetic tests always run; the game-data tests run when the installed games are present."""
import os
import struct
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import handy_race as hr  # noqa: E402
from fo4sf.planet import esm  # noqa: E402

SF_DATA = r"D:\SteamLibrary\steamapps\common\Starfield\Data"
FO4_DATA = r"D:\SteamLibrary\steamapps\common\Fallout 4\Data"
SF_ANIM = os.path.join(SF_DATA, "Starfield - Animations.ba2")
SF_ESM = os.path.join(SF_DATA, "Starfield.esm")
FO4_ANIM = os.path.join(FO4_DATA, "Fallout4 - Animations.ba2")
MINI = "Actors\\MiniBotA\\Animations"


class HashTests(unittest.TestCase):
    def test_bs_crc32_is_zlib_crc_with_init0_no_xor(self):
        for s in (b"", b"a", b"animtextdata\\tables\\graphs\\furniture.agx"):
            self.assertEqual(hr.bs_crc32(s), zlib.crc32(s, 0xFFFFFFFF) ^ 0xFFFFFFFF)

    def test_measured_minibot_keys(self):
        # file names measured in Starfield - Animations.ba2 (animationfiledata / animationoffsets)
        self.assertEqual(hr.manifest_key(hr.STRAFING_GRAPH, [MINI]), 15280412852093574592)
        self.assertEqual(hr.manifest_key(hr.FURNITURE_GRAPH, [MINI + "\\Furniture", MINI]), 4101133081575975552)
        self.assertEqual(hr.manifest_key(hr.FURNITURE_GRAPH, ["actors\\minibota\\animations\\furniture\\ambush", MINI]),
                         10432078471184280192)
        self.assertEqual(hr.manifest_key(hr.ROOT_GRAPH, []), 2256628916)      # root graphs: high word 0

    def test_key_ignores_case_and_slashes_but_not_order(self):
        a = hr.manifest_key(hr.FURNITURE_GRAPH, ["A\\B", "C"])
        self.assertEqual(a, hr.manifest_key(hr.FURNITURE_GRAPH.upper(), ["a/b", "c"]))
        self.assertNotEqual(a, hr.manifest_key(hr.FURNITURE_GRAPH, ["C", "A\\B"]))


class ManifestTests(unittest.TestCase):
    def test_animation_file_data_shape(self):
        b = hr.animation_file_data(4101133081575975552, [MINI + "\\relaxed_idle_flavor02.af", MINI + "\\Idle.af",
                                                         MINI + "\\relaxed_idle_flavor01.af"])
        self.assertEqual(b, ("3\n1\n4101133081575975552\n3\n" + MINI + "\\Idle.af\n" + MINI +
                             "\\relaxed_idle_flavor01.af\n" + MINI + "\\relaxed_idle_flavor02.af\n").encode())

    def test_minimal_offsets_is_53_bytes_for_furniture(self):
        b = hr.animation_offsets(hr.FURNITURE_GRAPH)
        self.assertEqual(len(b), 53)
        self.assertEqual(b, b"V5\n" + bytes([41]) + hr.FURNITURE_GRAPH.encode() + b"\0" + bytes(8))

    def test_offsets_round_trip(self):
        clips = [hr.OffsetClip("A\\Melee", 1.5, [(0.25, "weaponSwing"), (0.5, "HitFrame")]),
                 hr.OffsetClip("A\\Turn", 1.0, [], [(0.5, 0.0, 0.0, 0.1, 0.99)], flags=0x20)]
        b = hr.animation_offsets(hr.STRAFING_GRAPH, [("MeleeAttack01", "A\\Melee")], clips)
        g, tags, back = hr.parse_animation_offsets(b)
        self.assertEqual((g, tags), (hr.STRAFING_GRAPH, [("MeleeAttack01", "A\\Melee")]))
        self.assertEqual(back[0].flags, 0x400000)
        self.assertEqual([n for _, n in back[0].events], ["weaponSwing", "HitFrame"])
        self.assertEqual(len(back[1].keys), 1)
        self.assertEqual(hr.animation_offsets(g, tags, back), b)

    def test_stance_round_trip(self):
        bones = [(2, (1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5)), (5, (0.0, 0.7071, 0.0, 0.7071, 0.0, 0.1, 0.3))]
        b = hr.stance_data(bones)
        self.assertEqual(len(b), 54 + 16 + 2 * 32 + 16)
        head, back, trailer = hr.parse_stance_data(b)
        self.assertEqual(head, (2, 1, 0))
        self.assertEqual([i for i, _ in back], [2, 5])
        self.assertEqual(trailer, struct.pack("<IIiI", 2, 0, -1, 0))

    def test_afx_shape(self):
        root = ET.fromstring(hr.afx_bytes("Idle", "Idle.af", 1, [(8, "HitFrame")], [(0, "Foley")]))
        self.assertEqual(root.findtext("tag"), "Idle")
        self.assertEqual(root.find("events/event/name").text, "HitFrame")
        self.assertEqual(root.find("audios/audio/foley").text, "Foley")

    def test_generated_subgraph_data(self):
        b = hr.generated_subgraph_data([("Furniture", "3rd", "", "AnimFurnAmbush", hr.FURNITURE_GRAPH, ["a\\b", "C"])])
        lines = b.decode().splitlines()
        self.assertEqual(lines[0].split("\t")[-1], "Animation Path(s)")
        self.assertEqual(lines[1].split("\t")[-1], "a\\b, C")

    def test_race_manifests_names_and_lists(self):
        paths = hr.HandyPaths()
        info = {"Claw\\Attack_1.hkx": {"duration": 1.6, "annotations": [(0.43, "preHitFrame"), (0.6, "HitFrame"),
                                                                         (0.1, "SoundPlay.X")]}}
        files = hr.race_manifests(hr.HANDY_EDID, paths, fo4_info=info)
        key = hr.manifest_key(hr.STRAFING_GRAPH, [paths.clips])
        fd = files[f"Meshes\\AnimTextData\\AnimationFileData\\{key}.txt"].decode().splitlines()
        self.assertEqual(int(fd[3]), len(fd) - 4)
        self.assertIn(paths.clips + "\\MeleeAttack01.af", fd)
        self.assertNotIn(paths.clips + "\\LookDirections.af", fd)        # how == "none" left out
        g, tags, clips = hr.parse_animation_offsets(files[f"Meshes\\AnimTextData\\AnimationOffsets\\{key}.txt"])
        self.assertEqual(tags, [("MeleeAttack01", paths.clips + "\\MeleeAttack01")])
        self.assertEqual([n for _, n in clips[0].events], ["preHitFrame", "HitFrame"])
        self.assertIn("Meshes\\AnimTextData\\GeneratedSubgraphData\\fo4sf_handyrace.txt", files)

    def test_clip_map_tags_unique_and_sources_named(self):
        tags = [c.tag for c in hr.HANDY_CLIP_MAP]
        self.assertEqual(len(tags), len(set(tags)))
        for c in hr.HANDY_CLIP_MAP:
            self.assertEqual(c.fo4 is None, c.how == "none", c.tag)
        self.assertEqual(hr.sf_event("weaponFire.3"), "WeaponFire")
        self.assertIsNone(hr.sf_event("SoundPlay.NPCRobotMrHandyTurn180"))


def fake_minibot():
    race = esm.Record(b"RACE", hr.MINIBOT_RACE, [
        (b"EDID", esm.zbytes("MiniBotARace")), (b"FULL", struct.pack("<I", 0x1ED1)), (b"DESC", struct.pack("<I", 0x1ECF)),
        (b"GNAM", struct.pack("<I", hr.MINIBOT_BPTD)), (b"ANAM", esm.zbytes("Actors\\minibota\\CharacterAssets\\skeleton.nif")),
        (b"NAM5", esm.zbytes("actors\\minibota\\characterassets\\skeleton.rig")), (b"NAM6", esm.zbytes(hr.ROOT_GRAPH)),
        (b"DNAM", esm.zbytes(MINI)), (b"PNAM", struct.pack("<f", 5.0)), (b"ZNAM", esm.zbytes("C_Chassis")),
        (b"SGNM", esm.zbytes(hr.STRAFING_GRAPH)), (b"SAPT", esm.zbytes(MINI)), (b"SRAF", struct.pack("<I", 1)),
        (b"SGNM", esm.zbytes(hr.FURNITURE_GRAPH)), (b"SAPT", esm.zbytes(MINI + "\\Furniture")), (b"SAPT", esm.zbytes(MINI)),
        (b"SNAM", struct.pack("<I", 0x1ED0))], version=581)
    ref = "BASE Meshes\\Actors\\minibota\\CharacterAssets\\skeleton_ref.nif"
    bptd_subs = [(b"EDID", esm.zbytes("MiniBotABodyPartData")),
                 (b"MODL", esm.zbytes("Actors\\minibota\\CharacterAssets\\skeleton_ref.nif"))]
    for part, enam, fnam in (("C_Chassis", ref, ref), ("C_Base", "C_Base", "C_Axle"), ("C_Arm1", ref, ref)):
        bptd_subs += [(b"BPTN", struct.pack("<I", 0x64E3)), (b"BPNN", esm.zbytes(part)), (b"BPNT", esm.zbytes(part)),
                      (b"BPD2", bytes(34)), (b"NAM4", esm.zbytes(ref)), (b"ENAM", esm.zbytes(enam)),
                      (b"FNAM", esm.zbytes(fnam)), (b"DNAM", b"\0")]
    return race, esm.Record(b"BPTD", hr.MINIBOT_BPTD, bptd_subs, version=581)


class RecordTests(unittest.TestCase):
    def test_build_race_changes_only_named_fields(self):
        race, _ = fake_minibot()
        paths = hr.HandyPaths()
        new = hr.build_race(race, 0x01000800, 0x01000801, paths)
        d = dict((s, x) for s, x in new.subs)
        self.assertEqual(esm.zstring(d[b"EDID"]), hr.HANDY_EDID)
        self.assertEqual(esm.zstring(d[b"FULL"]), "Mr. Handy")
        self.assertEqual(struct.unpack("<I", d[b"GNAM"])[0], 0x01000801)
        self.assertEqual(esm.zstring(d[b"NAM5"]), paths.skeleton_rig)
        self.assertEqual(esm.zstring(d[b"ZNAM"]), "Chest")
        self.assertEqual([esm.zstring(x) for x in new.all(b"SAPT")], [paths.clips, paths.furniture_clips, paths.clips])
        self.assertEqual(d[b"PNAM"], race.get(b"PNAM"))
        self.assertEqual(d[b"NAM6"], race.get(b"NAM6"))
        self.assertEqual([s for s, _ in new.subs], [s for s, _ in race.subs])
        self.assertEqual(hr.race_subgraph_sets(new)[1:], paths.subgraphs())

    def test_build_bptd_bones_and_paths(self):
        _, bptd = fake_minibot()
        paths = hr.HandyPaths()
        new = hr.build_bptd(bptd, 0x01000801, paths, extra_parts=(("C_Arm1", "Arm1|1"),))
        self.assertEqual([esm.zstring(x) for x in new.all(b"BPNN")], ["Chest", "Pelvis", "Arm1|0", "Arm1|1"])
        self.assertEqual([esm.zstring(x) for x in new.all(b"BPTN")], ["Chest", "Pelvis", "Arm1|0", "Arm1|1"])
        self.assertEqual(esm.zstring(new.get(b"MODL")), paths.skeleton_ref)
        enams = [esm.zstring(x) for x in new.all(b"ENAM")]
        self.assertEqual(enams[1], "Pelvis")
        self.assertEqual(enams[0], "BASE Meshes\\" + paths.skeleton_ref)
        self.assertEqual([esm.zstring(x) for x in new.all(b"FNAM")][1], "Pelvis")

    def test_plugin_round_trip(self):
        race, bptd = fake_minibot()
        w = esm.PluginWriter(["Starfield.esm"])
        b = w.add(hr.build_bptd(bptd, w.own(0x801), hr.HandyPaths()))
        w.add(hr.build_race(race, w.own(0x800), b.formid, hr.HandyPaths()))
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "t.esm")
            w.write(p)
            with esm.Plugin(p) as pl:
                self.assertEqual([r.edid for r in pl.records("RACE")], [hr.HANDY_EDID])
                self.assertEqual([r.edid for r in pl.records("BPTD")], [hr.HANDY_BPTD_EDID])


@unittest.skipUnless(os.path.exists(SF_ANIM), "Starfield animations archive not installed")
class StarfieldDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fo4sf.ba2 import Ba2
        cls.ba2 = Ba2(SF_ANIM)

    def test_writer_reproduces_shipped_minibot_files(self):
        for key in (15280412852093574592, 4101133081575975552, 10432078471184280192):
            raw = self.ba2.read(f"meshes/animtextdata/animationoffsets/{key}.txt")
            g, tags, clips = hr.parse_animation_offsets(raw)
            self.assertEqual(hr.animation_offsets(g, tags, clips), raw, key)
            fd = self.ba2.read(f"meshes/animtextdata/animationfiledata/{key}.txt").decode().splitlines()
            self.assertEqual(hr.animation_file_data(key, fd[4:]), ("\n".join(fd) + "\n").encode())
            self.assertEqual(self.ba2.read(f"meshes/animtextdata/dynamicidledata/{key}.txt"), hr.dynamic_idle_data())
        raw = self.ba2.read("meshes/animtextdata/animationstancedata/4101133081575975552.txt")
        head, bones, trailer = hr.parse_stance_data(raw)
        self.assertEqual(hr.stance_data(bones, head, struct.unpack_from("<I", trailer)[0]), raw)

    @unittest.skipUnless(os.path.exists(SF_ESM), "Starfield.esm not installed")
    def test_minibot_race_keys_exist_and_clone(self):
        race, bptd = hr.load_minibot(SF_ESM)
        names = {n.lower() for n in self.ba2.names}
        for graph, folders in hr.race_subgraph_sets(race):
            key = hr.manifest_key(graph, folders)
            self.assertIn(f"meshes/animtextdata/animationoffsets/{key}.txt", names, graph)
        new = hr.build_race(race, 0x01000800, 0x01000801, hr.HandyPaths())
        changed = [i for i, (a, b) in enumerate(zip(race.subs, new.subs)) if a != b]
        self.assertEqual(len(new.subs), len(race.subs))
        self.assertEqual({race.subs[i][0] for i in changed},
                         {b"EDID", b"FULL", b"DESC", b"GNAM", b"ANAM", b"NAM5", b"DNAM", b"ZNAM", b"SAPT", b"SNAM"})
        nb = hr.build_bptd(bptd, 0x01000801, hr.HandyPaths())
        self.assertEqual(len(nb.all(b"BPTN")), 6 + len(hr.EXTRA_PARTS))


@unittest.skipUnless(os.path.exists(FO4_ANIM), "Fallout 4 animations archive not installed")
class Fallout4DataTests(unittest.TestCase):
    def test_handy_clip_headers_and_coverage(self):
        from fo4sf.ba2 import Ba2
        a = Ba2(FO4_ANIM)
        pre = "meshes/actors/robot/animations/"
        clips = {n.replace("\\", "/").lower()[len(pre):]: n for n in a.names
                 if n.replace("\\", "/").lower().startswith(pre) and n.lower().endswith(".hkx")}
        self.assertEqual(len(clips), 84)
        info = hr.fo4_clip_info(a.read(clips["claw/attack_1.hkx"]))
        self.assertEqual(info["class"], "hkaSplineCompressedAnimation")
        self.assertAlmostEqual((info["frames"] - 1) * info["frame_duration"], info["duration"], places=3)
        self.assertEqual(info["transform_tracks"], 111)
        self.assertIn("HitFrame", [n for _, n in info["annotations"]])
        known = {c.fo4.lower().replace("\\", "/") for c in hr.HANDY_CLIP_MAP if c.fo4}
        known |= {k.lower().replace("\\", "/") for k in hr.FO4_NOT_EXPRESSIBLE}
        self.assertEqual(set(clips) - known, set())
        self.assertEqual(known - set(clips), set())


if __name__ == "__main__":
    unittest.main()
