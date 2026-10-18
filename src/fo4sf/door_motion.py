"""Source door animation topology for planning faithful multi-part conversion.

This describes source motion branches; it does not generate animation graphs or
claim that independent leaves can share the vanilla single-hinge animation.
"""
import struct
import base64
from . import nif, animation_curves


def sequence_timing(source, block, count):
    at = 12 + 29 * count
    if len(block) < at + 34:
        raise nif.NifError("truncated door sequence timing")
    weight, text, cycle, frequency, start, stop, manager, root, notes = struct.unpack_from("<fiIfffiiH", block, at)
    if len(block) != at + 34 + 4 * notes:
        raise nif.NifError("invalid door sequence note-array length")
    events = []
    if text != -1:
        if not 0 <= text < len(source.blocks) or source.type_of(text) != "NiTextKeyExtraData":
            raise nif.NifError("invalid door text-key link")
        data = source.blocks[text]
        num = struct.unpack_from("<I", data, 4)[0]
        if len(data) != 8 + 8 * num:
            raise nif.NifError("invalid door text-key length")
        for i in range(num):
            time, name = struct.unpack_from("<fi", data, 8 + 8 * i)
            if not 0 <= name < len(source.strings):
                raise nif.NifError("invalid door event string")
            events.append({"time": time, "text": source.strings[name].decode("latin-1")})
    if root != -1 and not 0 <= root < len(source.strings):
        raise nif.NifError("invalid door accumulation root")
    return {"weight": weight, "cycle_type": cycle, "frequency": frequency, "start": start, "stop": stop,
            "manager_block": manager, "accumulation_root": source.strings[root].decode("latin-1") if root != -1 else None,
            "text_events": events, "animation_note_blocks": list(struct.unpack_from(f"<{notes}i", block, at + 34))}


def transform_track(source, index):
    """Retain bind values, raw keys and decoded curves without resampling.

    Decoded curves still require a target animation emitter.
    Local generated reports contain source animation data and must not be published.
    """
    if index == -1:
        return None
    if not 0 <= index < len(source.blocks):
        raise nif.NifError("invalid door interpolator link")
    kind = source.type_of(index)
    if kind != "NiTransformInterpolator":
        return {"type": kind, "status": "unsupported_interpolator"}
    block = source.blocks[index]
    if len(block) < 36:
        raise nif.NifError("truncated door transform interpolator")
    values = struct.unpack_from("<8f", block)
    data = struct.unpack_from("<i", block, 32)[0]
    result = {"type": kind, "translation": list(values[:3]), "quaternion_wxyz": list(values[3:7]),
              "scale": values[7], "data_block": data, "source_keys": None}
    if data != -1:
        if not 0 <= data < len(source.blocks) or source.type_of(data) != "NiTransformData":
            raise nif.NifError("invalid door transform-data link")
        result["source_keys"] = {"type": "NiTransformData", "encoding": "base64",
                                 "data": base64.b64encode(source.blocks[data]).decode("ascii")}
        result["decoded_keys"] = animation_curves.decode(source.blocks[data])
    return result


# Controlled blocks known not to move a node. A scan of every FO4 mesh with an Open sequence (review of PR #242) found,
# besides 1313 NiTransformController + NiTransformInterpolator blocks, only shader float, alpha-test, visibility and
# particle-emitter controllers on float / bool interpolators (VltDoorRes01A's override-box shapes:
# BSLightingShaderPropertyFloatController with NiFloatInterpolator). Only these listed kinds are left out; anything else,
# a transform interpolator this code cannot sample (B-spline, blend) or an unknown type, stays a motion track, so it is
# refused later (door_clips.sample_track) instead of silently freezing that part.
NON_TRANSFORM_CONTROLLERS = frozenset((
    "BSLightingShaderPropertyFloatController", "BSLightingShaderPropertyColorController",
    "BSLightingShaderPropertyUShortController", "BSEffectShaderPropertyFloatController",
    "BSEffectShaderPropertyColorController", "BSNiAlphaPropertyTestRefController", "NiAlphaController",
    "NiVisController", "NiMaterialColorController", "NiPSysEmitterCtlr", "NiPSysEmitterSpeedCtlr"))
NON_TRANSFORM_INTERPOLATORS = frozenset(("NiFloatInterpolator", "NiBoolInterpolator", "NiBoolTimelineInterpolator",
                                         "NiPoint3Interpolator", "NiBlendFloatInterpolator", "NiBlendBoolInterpolator",
                                         "NiBlendPoint3Interpolator"))


def _non_transform(source, interpolator, controller_type):
    """Reason a controlled block does not move a node (a known shader / visibility / particle kind), or None.

    ControlledBlock layout (FO4): interpolator, controller, priority, node name, property type, controller type,
    controller id, interpolator id. A block is left out only when its interpolator (if any) is a known non-transform kind
    and its controller type is a known non-transform kind, or, with no controller type, when the interpolator is."""
    kind = source.type_of(interpolator) if 0 <= interpolator < len(source.blocks) else None
    if kind is not None and kind not in NON_TRANSFORM_INTERPOLATORS:
        return None                     # a transform interpolator, or one nobody has checked: motion
    if controller_type is None:
        return f"interpolator {kind}" if kind is not None else None
    return f"controller {controller_type}" if controller_type in NON_TRANSFORM_CONTROLLERS else None


def inspect(source):
    nodes = {}
    for i, block in enumerate(source.blocks):
        if source.type_of(i) == "NiNode":
            name = struct.unpack_from("<i", block)[0]
            nodes.setdefault(name, []).append(i)
    shapes = {s.block for s in nif.fo4_trishapes(source) if s.positions and s.triangles}
    world = nif.world_transforms(source)
    sequences, issues, ignored = [], [], []
    for i, block in enumerate(source.blocks):
        if source.type_of(i) != "NiControllerSequence":
            continue
        name, count = struct.unpack_from("<iI", block)
        if not 0 <= name < len(source.strings):
            raise nif.NifError("invalid sequence name")
        if source.strings[name] not in (b"Open", b"Close"):
            continue
        if 12 + 29 * count > len(block):
            raise nif.NifError("truncated door controlled-block list")
        targets = []
        for k in range(count):
            at = 12 + 29 * k
            interpolator, controller = struct.unpack_from("<ii", block, at)
            target_name, _property_type, controller_type = struct.unpack_from("<iii", block, at + 9)
            if not 0 <= target_name < len(source.strings):
                raise nif.NifError("invalid controlled node name")
            reason = _non_transform(source, interpolator, source.strings[controller_type].decode("latin-1")
                                    if 0 <= controller_type < len(source.strings) else None)
            if reason:                 # not motion: kept out of the rig and listed, never a binding issue
                ignored.append({"sequence": i, "target": source.strings[target_name].decode("latin-1"), "reason": reason})
                continue
            matches = nodes.get(target_name, [])
            if len(matches) != 1:
                issues.append({"sequence": i, "target": source.strings[target_name].decode("latin-1"),
                               "reason": "node binding absent or ambiguous"})
                continue
            node = matches[0]
            translation, rotation, scale = world(node)
            targets.append({"node": node, "name": source.strings[target_name].decode("latin-1"),
                            "interpolator": interpolator, "controller": controller,
                            "transform_track": transform_track(source, interpolator),
                            "pivot_source_units": list(translation), "rotation": list(rotation), "scale": scale,
                            "shape_blocks": sorted(shapes & nif.descendants(source, node))})
        sequences.append({"block": i, "name": source.strings[name].decode("latin-1"), "targets": targets,
                          "timing": sequence_timing(source, block, count)})
    hinge = nif.door_hinge(source)
    hinge_descendants = nif.descendants(source, hinge[0]) if hinge else set()
    selected = shapes & hinge_descendants
    animated = {shape for seq in sequences if seq["name"] == "Open" for target in seq["targets"] for shape in target["shape_blocks"]}
    # Subtree membership proves attachment, not rigid motion. An explicitly
    # controlled child replaces its own local channels, which a parent-only
    # hinge cannot retain. Include Close: an Open parent still covers these
    # shapes in the legacy frozen_door_parts caller.
    # Be conservative even for constant/unsupported interpolators: no bind-
    # equivalence proof exists here. Null interpolators retain the node bind.
    nested = {shape for seq in sequences for target in seq["targets"]
              if hinge and target["node"] != hinge[0]
              and target["node"] in hinge_descendants
              and target["transform_track"] is not None
              for shape in target["shape_blocks"]}
    unsupported = (animated - selected) | nested
    return {"sequences": sequences, "issues": issues, "ignored_targets": ignored,
            "single_hinge_node": hinge[0] if hinge else None,
            "single_hinge_shape_blocks": sorted(selected), "all_animated_shape_blocks": sorted(animated),
            "nested_controlled_shape_blocks": sorted(nested),
            # Historical key means outside the hinge's motion coverage, not
            # strictly outside its descendant set. Retain it for callers.
            "animated_shapes_outside_single_hinge": sorted(unsupported),
            "requires_additional_motion_support": bool(unsupported)}
