Scriptname FOCC_P5_Array129 Hidden
{Compile-only test of the Papyrus array cap (fo4-to-starfield, docs/spikes/combined-core-probes.md P5): FO4's compiler
 refuses "new float[129]" (arrays are capped at 128 entries there; Starfield unchecked, engine-feasibility.md).
 scripts/combined_probes/make_combined_probe.py compiles this script on its own and records the compiler's output in
 compile_p5_array129.txt; the .pex, if one is produced, is never packed.}

float[] Function Make() global
    return new float[129]
EndFunction
