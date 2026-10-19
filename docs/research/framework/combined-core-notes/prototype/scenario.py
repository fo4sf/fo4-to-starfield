"""Synthetic packs for the prototype. Placeholder names only: not game facts.

Region R1 stands in for a first world (the Commonwealth pack later), R2 for a second
world reached through a gateway, to prove the systems need no second game and break
nothing when one arrives.
"""

REGION_1 = {
    "places": [
        {"id": "farm_a", "region": "R1", "kind": "settlement", "holder": "settlers", "defence": 2},
        {"id": "farm_b", "region": "R1", "kind": "settlement", "holder": "settlers", "defence": 1},
        {"id": "market", "region": "R1", "kind": "settlement", "holder": "settlers", "defence": 3},
        {"id": "story_vault", "region": "R1", "kind": "landmark", "holder": "settlers",
         "story_lock": "main_story_1"},
        {"id": "raider_camp", "region": "R1", "kind": "base", "holder": "raiders", "defence": 4},
        {"id": "ruins", "region": "R1", "kind": "landmark"},
        {"id": "order_fort", "region": "R1", "kind": "base", "holder": "order", "defence": 8},
        {"id": "gate_1", "region": "R1", "kind": "gateway"},
    ],
    "settlements": [
        {"place": "farm_a", "population": 5, "roles": {"farmer": 3, "guard": 1, "trader": 1,
         "crafter": 0, "scavenger": 0, "doctor": 0}, "stock": {"food": 20, "water": 20,
         "scrap": 0, "ammo": 10, "medicine": 0}},
        {"place": "farm_b", "population": 3, "roles": {"farmer": 1, "guard": 1, "trader": 0,
         "crafter": 0, "scavenger": 1, "doctor": 0}, "stock": {"food": 6, "water": 6,
         "scrap": 4, "ammo": 0, "medicine": 0}},
        {"place": "market", "population": 6, "roles": {"farmer": 2, "guard": 2, "trader": 1,
         "crafter": 1, "scavenger": 0, "doctor": 0}, "stock": {"food": 12, "water": 12,
         "scrap": 10, "ammo": 20, "medicine": 2}},
    ],
    "factions": [
        {"id": "settlers", "strength": 6, "home": "market", "aggression": 30,
         "relations": {"raiders": -80, "order": 20}},
        {"id": "raiders", "strength": 18, "home": "raider_camp", "aggression": 90,
         "relations": {"settlers": -80, "order": -60}},
        {"id": "order", "strength": 24, "home": "order_fort", "aggression": 40,
         "relations": {"raiders": -60, "settlers": 20}},
    ],
    "routes": [
        {"a": "farm_a", "b": "market", "hours": 6},
        {"a": "farm_b", "b": "market", "hours": 6},
        {"a": "farm_b", "b": "ruins", "hours": 6},
        {"a": "ruins", "b": "raider_camp", "hours": 6},
        {"a": "raider_camp", "b": "farm_a", "hours": 12},
        {"a": "market", "b": "story_vault", "hours": 6},
        {"a": "story_vault", "b": "raider_camp", "hours": 6},
        {"a": "order_fort", "b": "ruins", "hours": 12},
        {"a": "market", "b": "gate_1", "hours": 12},
    ],
}

REGION_2 = {
    "places": [
        {"id": "gate_2", "region": "R2", "kind": "gateway"},
        {"id": "river_town", "region": "R2", "kind": "settlement", "holder": "traders", "defence": 2},
        {"id": "slaver_pit", "region": "R2", "kind": "base", "holder": "slavers", "defence": 5},
    ],
    "settlements": [
        {"place": "river_town", "population": 4, "roles": {"farmer": 2, "guard": 1, "trader": 1,
         "crafter": 0, "scavenger": 0, "doctor": 0}, "stock": {"food": 10, "water": 10,
         "scrap": 0, "ammo": 5, "medicine": 0}},
    ],
    "factions": [
        {"id": "traders", "strength": 8, "home": "river_town", "aggression": 5,
         "relations": {"slavers": -70}},
        {"id": "slavers", "strength": 16, "home": "slaver_pit", "aggression": 70,
         "relations": {"traders": -70, "settlers": -50}},
    ],
    "routes": [
        {"a": "gate_2", "b": "river_town", "hours": 6},
        {"a": "river_town", "b": "slaver_pit", "hours": 6},
        {"a": "gate_1", "b": "gate_2", "hours": 48},
    ],
}
