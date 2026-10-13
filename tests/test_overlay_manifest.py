"""scripts/overlay_manifest.py: a partial re-conversion swapped into a pinned manifest (synthetic manifests)."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("overlay_manifest", Path(__file__).resolve().parents[1] / "scripts/overlay_manifest.py")
om = importlib.util.module_from_spec(spec)
spec.loader.exec_module(om)


def item(source, eid, index, door=None):
    return {"editor_id": eid, "model": source.lower(), "source": source, "form_index": index,
            **({"door": door} if door else {})}


PINNED = {"items": [item("meshes\\A.nif", "FO4Port_A", 0, {"rig": None, "origin_offset": [1, 2, 3]}),
                    item("meshes\\B.nif", "FO4Port_B", 1, {"origin_offset": [0, 0, 0]}),
                    item("meshes\\C.nif", "FO4Port_C", 2)],
          "failures": [], "stats": {"assets": 3}}


class OverlayManifestTests(unittest.TestCase):
    def test_native_doors_are_swapped_in_and_keep_their_form_index(self):
        partial = {"items": [item("meshes\\a.nif", "FO4Port_A", 0, {"rig": "native", "origin_offset": [0, 0, 0]}),
                             item("meshes\\B.nif", "FO4Port_B", 1, {"origin_offset": [0, 0, 0]})]}
        merged, swapped = om.overlay(PINNED, partial, native_doors_only=True)
        self.assertEqual(swapped, ["meshes\\A.nif"])
        self.assertEqual(merged["items"][0]["door"]["rig"], "native")
        self.assertEqual([i["form_index"] for i in merged["items"]], [0, 1, 2])
        self.assertEqual(merged["items"][1:], PINNED["items"][1:])
        self.assertEqual(merged["stats"], PINNED["stats"])
        merged, swapped = om.overlay(PINNED, partial)
        self.assertEqual(swapped, ["meshes\\A.nif", "meshes\\B.nif"])

    def test_renamed_or_unknown_items_stop_the_overlay(self):
        for partial in ({"items": [item("meshes\\A.nif", "FO4Port_Other", 5)]},
                        {"items": [item("meshes\\D.nif", "FO4Port_D", 5)]}):
            with self.assertRaises(ValueError):
                om.overlay(PINNED, partial)


if __name__ == "__main__":
    unittest.main()
