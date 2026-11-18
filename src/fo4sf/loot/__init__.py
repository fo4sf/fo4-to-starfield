"""IDs-only route and Vault 111 loot mapping tables (Phase 2 Track C 2i)."""

from .tables import (
    ALLOWED_CATEGORIES,
    CREDITS_FORM_ID,
    ROUTE_LOOT_IDS_JSON,
    ROUTE_LOOT_MASTERS,
    ROUTE_LOOT_PLUGIN,
    corridor_distance_m,
    load_route_loot_spec,
    validate_route_loot_doc,
)

__all__ = [
    "ALLOWED_CATEGORIES",
    "CREDITS_FORM_ID",
    "ROUTE_LOOT_IDS_JSON",
    "ROUTE_LOOT_MASTERS",
    "ROUTE_LOOT_PLUGIN",
    "corridor_distance_m",
    "load_route_loot_spec",
    "validate_route_loot_doc",
]
