"""Refuse a stage whose terrain artifact publication is active or needs recovery."""
import os

PENDING = "FO4SF.terrain-output.pending.jsonl"
LEASE = "FO4SF.terrain-output.lock"


def require_ready_stage(directory):
    for name in (PENDING, LEASE):
        path = os.path.join(directory, name)
        if os.path.lexists(path):
            raise ValueError(f"terrain output publication is pending; preserve and review {path}")
