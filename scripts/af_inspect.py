"""Read-only inspector for Starfield .af animations in the user's own archive (nothing is copied or written).

usage: python scripts/af_inspect.py "<Starfield Data dir>" <rig folder fragment> [...]
           per family: rig bones, then every animated bone of open.af / close.af with its decoded motion
       python scripts/af_inspect.py "<Starfield Data dir>" --scan
           parse every .af in "Starfield - Animations.ba2" and report how many consume exactly their byte length

Example fragments: architecture\\city\\akila\\animated\\doors\\ak_ext_bld_walla_doora_01
                   architecture\\generic\\animated\\doors\\genintrmsmwallmid_doora00a
"""
import collections
import math
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import af  # noqa: E402
from fo4sf.ba2 import Ba2  # noqa: E402

ARCHIVE = "Starfield - Animations.ba2"


def qdeg(a, b):
    return math.degrees(2 * math.acos(min(1.0, abs(sum(p * q for p, q in zip(a, b))))))


def family(archive, names, fragment):
    fragment = fragment.lower().replace("/", "\\")
    rigs = [n for n in names if fragment in n and n.endswith("skeleton.rig")]
    if not rigs:
        print("== %s: no skeleton.rig" % fragment)
        return
    rig = af.parse_rig(archive.read(rigs[0]))
    print("== %s: %d bones (%d animated), precision %s" % (fragment, len(rig.bones), rig.animated_count,
                                                           tuple(round(p, 6) for p in rig.precision)))
    for b in rig.bones:
        print("   bone %2d parent %2d %-30s bind t (%7.3f %7.3f %7.3f) rot %5.1f deg" % (
            b.index, b.parent, b.name, *b.translation, qdeg(b.rotation, af.IDENTITY)))
    for n in [n for n in names if fragment in n and n.endswith(".af")]:
        raw = archive.read(n)
        try:
            anim = af.parse(raw, precision=rig.precision)
        except af.AfError as e:
            print("  -- %s %d B: %s" % (os.path.basename(n), len(raw), e))
            continue
        h = anim.header
        print("  -- %s %d B: flags 0x%02x bones %d frames %d atlas %s preamble %d suffix %d" % (
            os.path.basename(n), len(raw), h.flags, h.bone_count, h.frame_count, anim.atlas, h.preamble_size,
            h.suffix_count))
        for t in anim.bones:
            if not t.animated:
                continue
            line = "     bone %2d %-26s" % (t.bone, rig.bones[t.bone].name if t.bone < len(rig.bones) else "?")
            if t.rotation:
                ax, ang = af.axis_angle(t.rotation.values[-1])
                line += " | rot %2d keys first %5.1f deg last %6.1f deg about (%5.2f %5.2f %5.2f)" % (
                    len(t.rotation), qdeg(t.rotation.values[0], af.IDENTITY), ang, *ax)
            if t.translation:
                line += " | trans %2d keys first (%6.3f %6.3f %6.3f) last (%6.3f %6.3f %6.3f)" % (
                    len(t.translation), *t.translation.values[0], *t.translation.values[-1])
            if t.scalar or t.priority:
                line += " | scalar %d priority %d" % (len(t.scalar), len(t.priority))
            print(line)


def scan(archive, names):
    t0 = time.time()
    afs = [i for i, n in enumerate(names) if n.endswith(".af")]
    ok = 0
    errors = collections.Counter()
    flags = collections.Counter()
    preamble_decoded = collections.Counter()
    for i in afs:
        raw = archive.read(i)
        try:
            anim = af.parse(raw)
        except af.AfError as e:
            errors[str(e).split(":")[0][:40]] += 1
            continue
        ok += 1
        flags[anim.header.flags] += 1
        if anim.header.preamble_size:
            preamble_decoded[anim.preamble_parsed] += 1
    print("%d .af files, %d parse to exactly their byte length (%.1f s)" % (len(afs), ok, time.time() - t0))
    print("flags:", dict(sorted(flags.items())))
    print("files with a preamble whose inner structure decoded (True) or not (False):", dict(preamble_decoded))
    if errors:
        print("errors:", dict(errors))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    archive = Ba2(os.path.join(argv[0], ARCHIVE))
    names = [n.replace("/", "\\").lower() for n in archive.names]
    if argv[1] == "--scan":
        scan(archive, names)
    else:
        for fragment in argv[1:]:
            family(archive, names, fragment)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
