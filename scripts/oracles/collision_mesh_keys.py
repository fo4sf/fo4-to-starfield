"""Oracle: Starfield compressed-mesh decoder simulation over converted NIFs (loose files, folders or BA2 archives).

usage: python scripts/oracles/collision_mesh_keys.py <build>/Data/meshes [--json out.json] [--filter text] [--quiet]
       python scripts/oracles/collision_mesh_keys.py "<build>/FO4Port - Main.ba2"
Exit 1 on any violation (see src/fo4sf/meshcheck.py for the rules and the vanilla evidence behind them)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "src"))
from fo4sf import meshcheck  # noqa: E402

if __name__ == "__main__":
    sys.exit(meshcheck.main())
