"""Posed props: skinned shapes in the NIF's node pose and placed references with FO4 ragdoll data (XRGD) in their own
pose (nif.world_transforms local_overrides, ragdoll_pose.local_overrides, convert_static pose=..., placed_pose.plan,
convert_batch variants). Synthetic NIFs only, no game data.

Fixture (block: content):
  0 Root (identity; the 'rooted' variant moves it, which a placed reference ignores)
  1 BoneA  local (0, 0, 10), body 0          2 BoneB  local (0, 0, 10) under BoneA, body 1
  3 Body   skinned on BoneA / BoneB: v0 (1, 0, 5) on A, v1 (1, 0, 25) on B, v2 (0, 1, 15) half and half
  4 BSSkin::Instance   5 BSSkin::BoneData (bind = the node pose)   6 / 8 bhkNPCollisionObject   9 bhkPhysicsSystem
  7 Tag    unskinned triangle under BoneB, local (1, 0, 0) (0, 1, 0) (0, 0, 1)
Pose used below: BoneB's entry keeps its translation and turns it Rx(-90 deg) (XRGD rotation (pi/2, 0, 0), applied as
Rx(-x), row-major (1, 0, 0, 0, 0, 1, 0, -1, 0): y' = z, z' = -y). By hand: v1 -> BoneB space (1, 0, 5) -> turned (1, 5, 0)
-> + (0, 0, 20) = (1, 5, 20); v2 = half BoneA's (0, 1, 15), half BoneB's (0, 1, -5) -> (0, -5, -1) + (0, 0, 20) = (0, -5, 19),
so (0, -2, 17); the Tag's (0, 1, 0) -> (0, 0, -1) + 20 = (0, 0, 19)."""
import importlib.util
import json
import math
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from test_fo4skin import IDENT, bone_data_block, instance_block, node_block, shape_block
from fo4sf import convert_static, meshcollision, nif, placed_pose, ragdoll_pose, sfmesh, sfnif

ROOT = Path(__file__).resolve().parents[1]
HALF_PI = math.pi / 2
POSE_B = [{"index": 0, "bone_id": 0, "unused": "000000", "pos": [0, 0, 10], "rot": [0, 0, 0]},
          {"index": 1, "bone_id": 7, "unused": "ab12cd", "pos": [0, 0, 10], "rot": [HALF_PI, 0, 0]}]
NODE_POSE = [{"index": 0, "bone_id": 0, "unused": "000000", "pos": [0, 0, 10], "rot": [0, 0, 0]},
             {"index": 1, "bone_id": 0, "unused": "000000", "pos": [0, 0, 10], "rot": [0, 0, 0]}]


def colobj(target, system, body):
    return struct.pack("<iHiI", target, 0x80, system, body)


def rig_nif(root_trans=(0, 0, 0), bone_b_rot=IDENT, single_body=False):
    """single_body: only BoneA owns a body (block 8 becomes a BSXFlags), as a loose one-body item."""
    f = nif.NifFile(bs_version=130, author=b"t\x00", process_script=b"\x00", export_script=b"\x00", max_filepath=b"\x00")
    for s in (b"Root", b"BoneA", b"BoneB", b"Body", b"Tag"):
        f.string_index(s)
    f.add_block("NiNode", node_block(0, [1, 3], trans=root_trans))
    f.add_block("NiNode", node_block(1, [2], trans=(0, 0, 10)))
    f.add_block("NiNode", node_block(2, [7], trans=(0, 0, 10), rot=bone_b_rot))
    f.add_block("BSTriShape", shape_block(3, [(1.0, 0.0, 5.0), (1.0, 0.0, 25.0), (0.0, 1.0, 15.0)], 4,
                                          [(1.0, 0, 0, 0), (1.0, 0, 0, 0), (0.5, 0.5, 0, 0)],
                                          [(0, 0, 0, 0), (1, 0, 0, 0), (0, 1, 0, 0)]))
    f.add_block("BSSkin::Instance", instance_block(0, 5, [1, 2]))
    f.add_block("BSSkin::BoneData", bone_data_block([((0, 0, -5, 6), IDENT, (0, 0, -10), 1.0),
                                                     ((0, 0, 5, 6), IDENT, (0, 0, -20), 1.0)]))
    f.add_block("bhkNPCollisionObject", colobj(1, 9, 0))
    f.add_block("BSTriShape", shape_block(4, [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]))
    if single_body:
        f.add_block("BSXFlags", struct.pack("<iI", -1, 0))
    else:
        f.add_block("bhkNPCollisionObject", colobj(2, 9, 1))
    f.add_block("bhkPhysicsSystem", struct.pack("<I", 0))       # unreadable packfile: body count from the objects
    f.footer = struct.pack("<II", 1, 0)
    return nif.serialize(f)


def mesh_points(files, out_name):
    """Per converted shape (BSGeometry order = shape order), its vertices in game units."""
    n = nif.parse(files[f"meshes/{out_name}.nif"])
    out = []
    for k in range(len(n.blocks)):
        if n.type_of(k) == "BSGeometry":
            path = sfnif.parse_bsgeometry(n.blocks[k]).meshes[0].path.decode().replace("\\", "/")
            m = sfmesh.parse(files[f"geometries/{path}.mesh"])
            out.append([tuple(c * 70.0 for c in sfmesh.decode_position(p, m.scale)) for p in m.positions])
    return out


class Close:
    def close(self, got, want, places=2):
        self.assertEqual(len(got), len(want))
        for g, w in zip(got, want):
            for a, b in zip(g, w):
                self.assertAlmostEqual(a, b, places=places, msg=f"{got} != {want}")


class LocalOverrideTests(unittest.TestCase, Close):
    def test_override_replaces_a_nodes_local_transform_and_children_follow(self):
        n = nif.parse(rig_nif())
        turned = ((0.0, 0.0, 10.0), ragdoll_pose.euler_matrix((HALF_PI, 0, 0)), 1.0)
        plain = nif.world_transforms(n, placed=True)
        posed = nif.world_transforms(n, placed=True, local_overrides={2: turned})
        self.assertEqual(plain(2)[0], posed(2)[0])                          # same joint position
        self.close([posed(7)[0]], [(0.0, 0.0, 20.0)])
        self.close([nif.fo4_trishapes(n, placed=True, local_overrides={2: turned})[1].rotation],
                   [ragdoll_pose.euler_matrix((HALF_PI, 0, 0))])
        self.assertEqual(nif.world_transforms(n, placed=True, local_overrides={})(7), plain(7))

    def test_placed_root_stays_identity_unless_overridden(self):
        n = nif.parse(rig_nif(root_trans=(0, 0, 100)))
        self.assertEqual(nif.world_transforms(n, placed=True)(1)[0], (0.0, 0.0, 10.0))
        self.assertEqual(nif.world_transforms(n)(1)[0], (0.0, 0.0, 110.0))      # the file's own composition
        moved = nif.world_transforms(n, placed=True, local_overrides={0: ((5.0, 0.0, 0.0), IDENT, 1.0)})
        self.assertEqual(moved(1)[0], (5.0, 0.0, 10.0))

    def test_ragdoll_entries_become_bone_local_transforms(self):
        n = nif.parse(rig_nif())
        over = ragdoll_pose.local_overrides(n, POSE_B)
        self.assertEqual(sorted(over), [1, 2])                              # body k -> its collision object's node
        self.close([over[2][0]], [(0.0, 0.0, 10.0)])
        self.close([over[2][1]], [(1, 0, 0, 0, 0, 1, 0, -1, 0)])            # Rx(-90 deg), row-major
        bones = ragdoll_pose.pose_bones(n, POSE_B)                          # the same pose as world transforms
        world = nif.world_transforms(n, placed=True, local_overrides=over)
        for b in (1, 2):
            self.close([world(b)[0]], [bones[b].translation])
        with self.assertRaisesRegex(ragdoll_pose.RagdollPoseError, "3 ragdoll entries for 2 bodies"):
            ragdoll_pose.local_overrides(n, POSE_B + [dict(POSE_B[1], index=2)])


class ConvertPoseTests(unittest.TestCase, Close):
    def test_node_pose_differs_from_bind_pose(self):
        # BoneB turned 90 degrees about z in the NIF itself (the bind data is unturned): the skin follows the node pose
        files = convert_static.convert_static(rig_nif(bone_b_rot=(0, -1, 0, 1, 0, 0, 0, 0, 1)), "fo4port/t/node",
                                              include_skinned=True, report={})
        body, tag = mesh_points(files, "fo4port/t/node")
        self.close(body, [(1, 0, 5), (0, 1, 25), (-0.5, 0.5, 15)])          # v1: (1, 0, 5) turned onto +y, + 20
        self.close(tag, [(0, 1, 20), (-1, 0, 20), (0, 0, 21)])

    def test_skinned_shapes_use_the_placed_frame_like_collision(self):
        # a moved scene root is not applied to a placed reference: skinned and unskinned shapes both leave it out
        files = convert_static.convert_static(rig_nif(root_trans=(0, 0, 100)), "fo4port/t/rooted", include_skinned=True)
        body, tag = mesh_points(files, "fo4port/t/rooted")
        self.close(body, [(1, 0, 5), (1, 0, 25), (0, 1, 15)])
        self.close(tag, [(1, 0, 20), (0, 1, 20), (0, 0, 21)])

    def test_reference_pose_moves_skin_child_shapes_and_bodies(self):
        raw = rig_nif()
        over = ragdoll_pose.local_overrides(raw, POSE_B)
        report = {}
        files = convert_static.convert_static(raw, "fo4port/t/posed", include_skinned=True, pose=over, report=report)
        body, tag = mesh_points(files, "fo4port/t/posed")
        self.close(body, [(1, 0, 5), (1, 5, 20), (0, -2, 17)])
        self.close(tag, [(1, 0, 20), (0, 0, 19), (0, 1, 20)])
        self.assertEqual(report["skinned_posed"], 1)
        seen = {}

        def fake(blob, template, placements, motion):                       # the merged ragdoll body's parts
            seen.update(placements)
            motion["dynamic"], motion["rigid_bodies"] = 10.0, len(placements)
            return b"RIGID"
        with patch.object(meshcollision, "rigid_dynamic_body", side_effect=fake):
            convert_static.fo4_native_collision(nif.parse(raw), b"tmpl", {}, dynamic_template=b"dyn", pose=over)
        rot1, t1 = seen[1]
        self.close([t1], [(0.0, 0.0, 20.0 / 70.0)], places=6)
        self.close([rot1], [(1, 0, 0, 0, 0, 1, 0, -1, 0)])

    def test_no_pose_keeps_the_shared_model(self):
        raw = rig_nif()
        plain = convert_static.convert_static(raw, "fo4port/t/same", include_skinned=True)
        posed = convert_static.convert_static(raw, "fo4port/t/same", include_skinned=True,
                                              pose=ragdoll_pose.local_overrides(raw, NODE_POSE))
        self.assertEqual(plain, posed)                                      # entries equal to the node pose: same bytes


class PlanTests(unittest.TestCase):
    MODEL = "SetDressing\\Skel.nif"
    SOURCE = "meshes\\SetDressing\\Skel.nif"

    def plan(self, refs, items=None, raw=None):
        items = items if items is not None else {self.SOURCE.lower(): {"source": self.SOURCE, "editor_id": "FO4Port_Skel"}}
        raw = raw or rig_nif()
        return placed_pose.plan(refs, items, lambda source: raw if source.lower() == self.SOURCE.lower() else None)

    def ref(self, formkey, ragdoll, model=MODEL):
        return {"formkey": formkey, "model": model, "type": "Activator", "ragdoll": ragdoll}

    def test_pose_key_ignores_the_uninitialised_bytes_and_order(self):
        noisy = [dict(e, bone_id=99, unused="ffffff") for e in reversed(POSE_B)]
        self.assertEqual(placed_pose.pose_key(noisy), placed_pose.pose_key(POSE_B))
        self.assertNotEqual(placed_pose.pose_key(NODE_POSE), placed_pose.pose_key(POSE_B))
        self.assertRegex(placed_pose.pose_key(POSE_B), r"^[0-9a-f]{10}$")

    def test_each_reference_is_counted_once(self):
        stale = POSE_B + [dict(POSE_B[1], index=2)]
        refs = [self.ref("01:Fallout4.esm", POSE_B), self.ref("02:Fallout4.esm", POSE_B),     # one shared variant
                self.ref("03:Fallout4.esm", NODE_POSE),                                    # the node pose: no variant
                self.ref("04:Fallout4.esm", stale),                                        # XRGD for another model
                self.ref("05:Fallout4.esm", POSE_B, model="Other\\NotConverted.nif"),
                self.ref("06:Fallout4.esm", None)]                                         # no ragdoll data
        variants, stats = self.plan(refs)
        self.assertEqual(len(variants), 1)
        v = variants[0]
        self.assertEqual((v.source, v.refs, v.suffix), (self.SOURCE, ["01:Fallout4.esm", "02:Fallout4.esm"],
                                                        "_xrgd_" + placed_pose.pose_key(POSE_B)))
        self.assertAlmostEqual(v.shift, math.sqrt(50.0), places=4)         # v1 (1, 0, 25) -> (1, 5, 20)
        self.assertEqual(sorted(v.overrides), [1, 2])
        self.assertEqual(stats, {"refs_with_ragdoll": 5, "posed_refs": 2, "variants": 1, "unchanged": 1, "single_body": 0,
                                 "not_converted": 1, "door": 0,
                                 "rejected": {"N ragdoll entries for N bodies": 1}})

    def test_single_body_items_keep_the_shared_model(self):
        # one body (a loose bottle): its entry would turn the whole item against its reference; not posed, but counted
        turned = [{"index": 0, "bone_id": 0, "unused": "000000", "pos": [0, 0, 10], "rot": [HALF_PI, 0, 0]}]
        raw = rig_nif(single_body=True)
        self.assertEqual(sorted(ragdoll_pose.local_overrides(raw, turned)), [1])
        variants, stats = self.plan([self.ref("01:Fallout4.esm", turned), self.ref("02:Fallout4.esm", turned)], raw=raw)
        self.assertEqual((variants, stats["single_body"], stats["posed_refs"]), ([], 2, 0))
        variants, _ = placed_pose.plan([self.ref("01:Fallout4.esm", turned)],
                                       {self.SOURCE.lower(): {"source": self.SOURCE}}, lambda s: raw, min_bodies=1)
        self.assertEqual(len(variants), 1)                                  # the switch is the body count, nothing else

    def test_doors_are_never_posed(self):
        items = {self.SOURCE.lower(): {"source": self.SOURCE, "editor_id": "FO4Port_Skel", "door": {}}}
        variants, stats = self.plan([self.ref("01:Fallout4.esm", POSE_B)], items)
        self.assertEqual((variants, stats["door"], stats["posed_refs"]), ([], 1, 0))


class BatchVariantTests(unittest.TestCase):
    """convert_batch.py with --cell-json: the posed reference gets an extra manifest item; the converter is a stand-in."""

    def run_batch(self, staging, cell_path, collision, extra=()):
        spec = importlib.util.spec_from_file_location("convert_batch_posed", ROOT / "scripts" / "convert_batch.py")
        batch = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(batch)
        calls = []

        def convert(name, pose=None, out_suffix=""):
            calls.append((name, None if pose is None else sorted(pose), out_suffix))
            out = "fo4port/setdressing/skel" + out_suffix
            return {"ok": True, "out_name": out, "shapes": 2, "fallback_materials": 0,
                    "collision_report": {"skinned_posed": 1}, "movable": {"mass_kg": 10.0}}
        converter = SimpleNamespace(stats={}, material_errors={}, convert_nif=Mock(side_effect=convert))
        src = SimpleNamespace(mesh=lambda name: rig_nif() if name.lower() == "meshes\\setdressing\\skel.nif" else None)
        argv = ["convert_batch.py", "--fo4-data", "unused", "--staging", str(staging), "--content-resources", "unused",
                "--texconv", "unused", "--collision-template", str(collision), "--cell-json", str(cell_path), *extra]
        with patch.object(sys, "argv", argv), \
                patch.object(batch.pipeline, "Fo4Archives", return_value=src), \
                patch.object(batch.pipeline, "Converter", return_value=converter), \
                patch.object(batch.convert_static, "collision_template_from_nif", return_value=b"template"), \
                patch("builtins.print"):
            batch.main()
        return json.loads((staging / "manifest.json").read_text()), calls

    def test_posed_reference_gets_its_own_item_and_reruns_keep_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "collision.nif").write_bytes(b"synthetic")
            cell = {"cell": "C", "refs": [
                {"formkey": "01:Fallout4.esm", "type": "Activator", "model": "SetDressing\\Skel.nif", "ragdoll": POSE_B},
                {"formkey": "02:Fallout4.esm", "type": "Activator", "model": "SetDressing\\Skel.nif", "ragdoll": None}]}
            (tmp / "cell.json").write_text(json.dumps(cell))
            manifest, calls = self.run_batch(tmp / "staging", tmp / "cell.json", tmp / "collision.nif")
            key = placed_pose.pose_key(POSE_B)
            self.assertEqual(calls, [("meshes\\SetDressing\\Skel.nif", None, ""),
                                     ("meshes\\SetDressing\\Skel.nif", [1, 2], "_xrgd_" + key)])
            base, posed = manifest["items"]
            self.assertNotIn("pose", base)
            self.assertEqual(posed["editor_id"], base["editor_id"] + "_xrgd_" + key)
            self.assertEqual(posed["model"], "fo4port\\setdressing\\skel_xrgd_" + key + ".nif")
            self.assertEqual(posed["source"], base["source"])
            self.assertEqual(posed["pose"]["refs"], ["01:Fallout4.esm"])
            self.assertEqual(posed["movable"], {"mass_kg": 10.0})
            self.assertEqual(manifest["poses"]["posed_refs"], 1)
            again, _ = self.run_batch(tmp / "staging", tmp / "cell.json", tmp / "collision.nif")   # adopts the manifest
            self.assertEqual([i["editor_id"] for i in again["items"]], [base["editor_id"], posed["editor_id"]])
            off, calls = self.run_batch(tmp / "off", tmp / "cell.json", tmp / "collision.nif", ["--no-ref-poses"])
            self.assertEqual(len(off["items"]), 1)
            self.assertNotIn("poses", off)


if __name__ == "__main__":
    unittest.main()
