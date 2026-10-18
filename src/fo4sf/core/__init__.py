"""Leader core: the state model, the ledger and the importers (docs/ai/leader-core.md).

Pure Python, no numpy, no game or engine imports: everything here runs on Linux CI. Engine-specific behaviour
(console strings, HUD boxes, Plugins.txt) belongs in the adapters, never in the state model: the pure ones live in
fo4sf.core.adapters (the Transform of section 9), the ones that read the PC live outside this package
(scripts/game/testqueue.py's PreflightProbe, section 7).
"""
