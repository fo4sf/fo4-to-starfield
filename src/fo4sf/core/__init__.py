"""Leader core: the state model, the ledger and the importers (docs/ai/leader-core.md).

Pure Python, no numpy, no game or engine imports: everything here runs on Linux CI. Engine-specific behaviour
(console strings, HUD boxes, Plugins.txt) belongs in adapters outside this package, never here.
"""
