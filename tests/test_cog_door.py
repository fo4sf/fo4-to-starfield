"""The Vault 111 cog door (VltGearDoor01): an Activator FO4 opens with its Stage2 sequence, converted as a door with its own
rig (pipeline.OWN_RIG_ALIASES): Stage2 becomes Open, Stage2 backwards becomes Close, skinned shapes are left out."""
import dataclasses
import struct
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fo4sf import convert_static, door_clips, door_motion, door_rig, nif  # noqa: E402
from test_collision import fake_template  # noqa: E402
from test_door_two_panels import door_nif, donor, fake_clip_files, sequences, sliding_panels  # noqa: E402
import test_sliding_doors  # noqa: E402

ALIASES = {"Stage2": "Open"}
COG = "meshes/Interiors/Vault/VltGearDoor01.nif"


def cog_nif(parts=None, particles=()):
    """door_nif with FO4's activator clip names: Open renamed Stage2, Close renamed Stage0 (not a door clip); particles:
    extra Stage2 targets that are particle systems (NiParticleSystem blocks, not nodes), as the cog door's emitters."""
    f = door_nif(parts or sliding_panels(), extra_targets=particles)
    for i in range(len(f.blocks)):
        if f.type_of(i) == "NiNode" and f.strings[struct.unpack_from("<i", f.blocks[i])[0]].decode() in particles:
            if "NiParticleSystem" not in f.block_types:
                f.block_types.append("NiParticleSystem")
            f.block_type_index[i] = f.block_types.index("NiParticleSystem")
    for name, new in ((b"Open", b"Stage2"), (b"Close", b"Stage0")):
        i = sequences(f)[name]
        block = bytearray(f.blocks[i])
        struct.pack_into("<i", block, 0, f.string_index(new))
        f.blocks[i] = bytes(block)
    return f


def convert(f, **kw):
    count = len([s for s in nif.fo4_trishapes(f) if s.positions and s.triangles])
    return convert_static.convert_multipart_door(nif.serialize(f), "fo4port/interiors/vault/vltgeardoor01", ["x.mat"] * count,
                                                 fake_clip_files, collision_template=fake_template(),
                                                 leaf_physics_donor=donor(), rest_pose_check=True, **kw)


class CogDoorPlanTests(unittest.TestCase):
    def test_the_aliased_sequence_is_the_only_door_clip(self):
        f = cog_nif()
        self.assertEqual([s["name"] for s in door_motion.inspect(f)["sequences"]], [])
        self.assertEqual([s["name"] for s in door_motion.inspect(f, ALIASES)["sequences"]], ["Open"])

    def test_particle_emitters_in_the_aliased_clip_are_left_out_and_listed(self):
        # PC build 1449688: Stage2 also drives 27 particle-system targets, refused as unbound before
        f = cog_nif(particles=("p_Dust Door", "p_Sparks Track"))
        report = door_motion.inspect(f, ALIASES)
        self.assertEqual(report["issues"], [])
        self.assertEqual(sorted((t["target"], t["reason"]) for t in report["ignored_targets"]),
                         [("p_Dust Door", "particle system"), ("p_Sparks Track", "particle system")])
        self.assertEqual(convert(f, aliases=ALIASES)[1]["rig"], "native")
        door = door_nif(sliding_panels(), extra_targets=("p_Dust Door",))           # a real door is unchanged
        door.block_types.append("NiParticleSystem")
        door.block_type_index[[i for i in range(len(door.blocks)) if door.type_of(i) == "NiNode"][-1]] = len(door.block_types) - 1
        self.assertTrue(door_motion.inspect(door)["issues"])

    def test_close_is_open_played_backwards(self):
        plan = door_rig.plan(cog_nif(), placed=True, aliases=ALIASES)
        opening, closing = plan["clips"]
        self.assertEqual((opening["name"], closing["name"], closing["reversed_from"]), ("Open", "Close", "Open"))
        for a, b in zip(opening["tracks"], closing["tracks"]):
            self.assertEqual(b["samples"][0]["translation_source_units"], a["samples"][-1]["translation_source_units"])
            self.assertEqual(b["samples"][-1]["translation_source_units"], a["samples"][0]["translation_source_units"])
            self.assertEqual([s["elapsed"] for s in b["samples"]], sorted(s["elapsed"] for s in b["samples"]))
        self.assertIsNone(door_rig.rest_pose_issue(plan))

    def test_a_real_door_with_its_own_close_is_unchanged(self):
        plan = door_rig.plan(door_nif(sliding_panels()), placed=True)
        self.assertNotIn("reversed_from", plan["clips"][1])
        self.assertEqual(door_clips.reversed_clip(plan["clips"][0])["events"], [])


class CogDoorConversionTests(unittest.TestCase):
    def test_the_cog_door_gets_its_own_rig_and_says_which_clip_it_used(self):
        files, door = convert(cog_nif(), aliases=ALIASES)
        self.assertEqual(door["rig"], "native")
        self.assertEqual(door["sequence_aliases"], ALIASES)
        self.assertIn("meshes/fo4port/interiors/vault/vltgeardoor01/animations/Close.af", files)
        with self.assertRaisesRegex(nif.NifError, "exactly one Open and one Close"):
            convert(cog_nif())                                   # without the alias it is no door

    def test_skinned_shapes_are_left_out_and_listed_or_refused(self):
        f = cog_nif()
        real = nif.fo4_trishapes

        def one_skinned(source):
            shapes = real(source)
            return [dataclasses.replace(s, skinned=True, name=b"CogCable") if k == len(shapes) - 1 else s
                    for k, s in enumerate(shapes)]
        with patch.object(convert_static.nifmod, "fo4_trishapes", one_skinned):
            with self.assertRaisesRegex(nif.NifError, "skinned door shapes cannot be rigged"):
                convert(f, aliases=ALIASES)
            _, door = convert(f, aliases=ALIASES, drop_skinned=True)
        self.assertEqual(door["dropped_skinned_shapes"], ["CogCable"])
        self.assertEqual(door["rig"], "native")


class CogDoorRoutingTests(unittest.TestCase):
    convert = test_sliding_doors.NonHingedRoutingTests.convert

    def route(self, name, dll, multipart=None):
        with patch("test_sliding_doors.door_nif", lambda parts: cog_nif(parts)):
            with tempfile.TemporaryDirectory() as staging:
                return self.convert(staging, name, sliding_panels(), dll, multipart)

    def test_the_cog_door_takes_the_own_rig_path_with_its_alias(self):
        result, single, multi, static = self.route(COG, "calumi.dll")
        self.assertTrue(result["ok"], result)
        single.assert_not_called()
        static.assert_not_called()
        self.assertEqual(multi.call_args.kwargs["aliases"], ALIASES)
        self.assertTrue(multi.call_args.kwargs["drop_skinned"])
        self.assertTrue(multi.call_args.kwargs["rest_pose_check"])
        self.assertEqual(result["door"]["rig"], "native")

    def test_a_failed_rig_or_no_library_leaves_it_solid_not_passable(self):
        def fail(*a, **k):
            raise nif.NifError("synthetic failure")
        for dll, multipart in (("calumi.dll", fail), (None, None)):
            result, _, _, static = self.route(COG, dll, multipart)
            self.assertTrue(result["ok"], result)
            self.assertNotIn("door_not_opening", result)
            self.assertNotIn("door", result)
            self.assertIsNotNone(static.call_args.kwargs["collision_template"])   # keeps its collision

    def test_another_activator_with_a_stage2_clip_is_not_a_door(self):
        result, single, multi, static = self.route("meshes/Interiors/Vault/VltElevator.nif", "calumi.dll")
        multi.assert_not_called()
        single.assert_not_called()
        static.assert_called_once()
        self.assertNotIn("door", result)


if __name__ == "__main__":
    unittest.main()
