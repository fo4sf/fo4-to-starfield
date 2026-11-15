"""Relayer the layer-55 bodies of an already converted Starfield NIF to L_STATIC (S2 yellow gates, FAL-976).

The converter does this at write time (meshcollision.static_filter): a frozen FO4 leaf on layer 55 (L_CLUTTER_NOCUT) is
written as 1 L_STATIC, because Starfield's character controller passes through a static body on layer 55 (the New
Atlantis turnstile leaves; research log 2026-10-17, a supported hypothesis, not a proven engine fact). A model converted
before that fix, like the Vault 111 gear-room gate (V111GearRoomGate01) in the owner's installed port, still carries the
0x8037 word. This module rewrites that one word in the model's own bytes, so the PC does not have to rebuild an
interior to try the fix: nothing but the 4-byte collisionFilterInfo of each such body changes, every size stays.
Offline and synthetic-testable: the bytes are the caller's (a model read from the game on the PC); nothing from the game
is stored here.
"""
import struct
from typing import List, Tuple

from . import hktagfile, meshcollision, nif as nifmod

BODY = "hknpPhysicsSystemData::bodyCinfoWithAttachment"


class RelayerError(ValueError):
    pass


def relayer_blob(blob: bytes) -> Tuple[bytes, List[str]]:
    """(blob with every layer-55 body's collisionFilterInfo as static_filter writes it, [one note per body changed])."""
    try:
        tf = hktagfile.Tagfile(blob)
    except (hktagfile.TagfileError, KeyError, IndexError, struct.error) as e:
        raise RelayerError(f"not a readable tagfile: {e}") from e
    out, notes = bytearray(blob), []
    for k, it in enumerate(tf.items):
        if not k or tf.type_name(it.type) != BODY:
            continue
        fields = [f for f in tf.all_fields(it.type) if f.name == "collisionFilterInfo"]
        if len(fields) != 1:
            raise RelayerError(f"body cinfo type has {len(fields)} collisionFilterInfo fields")
        size = tf.size_of(it.type)
        for j in range(it.count):
            at = tf.data_start + it.offset + size * j + fields[0].offset
            if at + 4 > len(blob):
                raise RelayerError(f"body {j} of item {k} lies beyond the blob")
            word, = struct.unpack_from("<I", blob, at)
            new, note = meshcollision.static_filter(word)
            if note is not None and new != word:
                struct.pack_into("<I", out, at, new)
                notes.append(f"item {k} body {j}: {note}")
    return bytes(out), notes


def relayer_nif(raw: bytes) -> Tuple[bytes, List[str]]:
    """(NIF bytes with every collision system relayered, notes); the same bytes and [] when nothing is on layer 55."""
    f = nifmod.parse(raw)
    notes = []
    for i in range(len(f.blocks)):
        if f.type_of(i) != "bhkNPCollisionObject":
            continue
        _target, _flags, data = struct.unpack_from("<iHi", f.blocks[i], 0)
        if not (0 <= data < len(f.blocks)) or f.type_of(data) != "bhkPhysicsSystem":
            raise RelayerError(f"collision object {i}: data block {data} is not a bhkPhysicsSystem")
        if len(f.blocks[data]) < 4:
            raise RelayerError(f"collision object {i}: physics system block is {len(f.blocks[data])} bytes")
        n, = struct.unpack_from("<I", f.blocks[data], 0)
        if 4 + n > len(f.blocks[data]):
            raise RelayerError(f"collision object {i}: physics system says {n} bytes, block holds {len(f.blocks[data]) - 4}")
        blob = f.blocks[data][4:4 + n]
        new, got = relayer_blob(blob)
        if got:
            f.blocks[data] = f.blocks[data][:4] + new + f.blocks[data][4 + n:]
            notes += [f"collision object {i}: {g}" for g in got]
    return (nifmod.serialize(f) if notes else raw), notes
