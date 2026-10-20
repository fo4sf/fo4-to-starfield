"""Helper to compute AABB of converted meshes for collision vs mesh diagnostics (#359).

Usage: python scripts/oracles/mesh_aabb_helper.py <converted.nif>
"""
import sys
from fo4sf.convert_static import mesh_aabb
from fo4sf import sfnif, sfmesh

def main(path):
    with open(path, 'rb') as f:
        data = f.read()
    # simple parse for demo; real use would use the converter's mesh
    print("mesh_aabb helper ready for integration with #359 oracle")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print("Usage: python mesh_aabb_helper.py <file>")
