"""Combined-core L3 news (news.py) on the synthetic REGION_1/REGION_2 packs: placeholder names, not game facts."""
import copy
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.combined import fixtures, model, news, sim  # noqa: E402
from fo4sf.combined.model import WorldState  # noqa: E402

SEEDS = range(8)
DAYS = 12
KINDS_WRITTEN = ("place_taken", "attack_launched", "attack_failed", "caravan_raided", "caravan_arrived",
                 "caravan_lost", "stage_changed", "settler_left", "settler_arrived", "player_defended",
                 "player_traded")


def world(seed=1):
    ws = WorldState(seed=seed)
    model.load_pack(ws, copy.deepcopy(fixtures.REGION_1))
    model.load_pack(ws, copy.deepcopy(fixtures.REGION_2))
    return ws


def ran(seed, days=DAYS):
    ws = world(seed)
    sim.run(ws, days * 24)
    return ws


def ev(kind, place="farm_a", hour=0, **info):
    return {"hour": hour, "kind": kind, "place": place, "region": "R1", **info}


class TemplateTests(unittest.TestCase):
    def test_every_simulation_event_kind_has_a_line(self):
        samples = {
            "place_taken": ev("place_taken", faction="raiders", previous="settlers", retaken=False),
            "attack_launched": ev("attack_launched", faction="raiders", target="farm_a", size=3, retake=False),
            "attack_failed": ev("attack_failed", faction="raiders", defender="settlers"),
            "caravan_raided": ev("caravan_raided", faction="settlers", raider="raiders", origin="market",
                                 cargo={"food": 4}),
            "caravan_arrived": ev("caravan_arrived", faction="settlers", cargo={"food": 4}),
            "caravan_lost": ev("caravan_lost", faction="settlers"),
            "stage_changed": ev("stage_changed", old=0, new=1),
            "settler_left": ev("settler_left"),
            "settler_arrived": ev("settler_arrived"),
            "player_defended": ev("player_defended", holder="settlers", bonus=10),
            "player_traded": ev("player_traded", goods={"food": 10}),
        }
        self.assertEqual(set(samples), set(KINDS_WRITTEN))
        for kind, e in samples.items():
            line = news.headline(e)
            self.assertIsInstance(line, str, kind)
            self.assertTrue(line.endswith("."), line)
            self.assertEqual(line[0], line[0].upper(), line)
            self.assertNotIn("{", line)
            self.assertNotIn("_", line)                       # ids shown as names

    def test_variants_pick_the_right_words(self):
        self.assertEqual(news.headline(ev("place_taken", faction="raiders", previous="settlers", retaken=False)),
                         "Raiders took farm a from settlers.")
        self.assertEqual(news.headline(ev("place_taken", faction="raiders", previous="settlers", retaken=True)),
                         "Raiders took back farm a from settlers.")
        self.assertEqual(news.headline(ev("place_taken", faction="order", previous=None, retaken=False)),
                         "Order moved into farm a.")
        self.assertEqual(news.headline(ev("stage_changed", old=1, new=2)), "Farm a has grown.")
        self.assertEqual(news.headline(ev("stage_changed", old=2, new=1)), "Farm a has shrunk.")
        self.assertEqual(news.headline(ev("player_traded", goods={"food": 5})),
                         "A traveller brought supplies to farm a.")
        self.assertEqual(news.headline(ev("player_traded", goods={"food": -5})),
                         "A traveller bought supplies at farm a.")
        self.assertEqual(news.headline(ev("caravan_arrived", faction="settlers", cargo={"water": 2, "food": 4})),
                         "A caravan reached farm a carrying 4 food, 2 water.")
        self.assertEqual(news.headline(ev("caravan_arrived", faction="settlers", cargo={})),
                         "A caravan reached farm a carrying nothing.")

    def test_unknown_kind_is_skipped(self):
        self.assertIsNone(news.headline(ev("meteor_strike")))
        self.assertIsNone(news.headline({"hour": 0, "kind": None, "place": "farm_a"}))

    def test_display_names_from_a_table_or_underscores(self):
        self.assertEqual(news.display_name("river_town"), "river town")
        self.assertEqual(news.display_name("river_town", {"river_town": "Riverside"}), "Riverside")
        self.assertEqual(news.display_name(None), "no one")
        line = news.headline(ev("settler_left", place="river_town"), {"river_town": "Riverside"})
        self.assertEqual(line, "A settler left Riverside.")

    def test_templates_are_short_and_contain_no_ids(self):
        for key, t in news.TEMPLATES.items():
            self.assertLess(len(t), 80, key)
            self.assertTrue(t.endswith("."), key)


class FeedTests(unittest.TestCase):
    def test_lines_follow_news_for_and_are_newest_first(self):
        for seed in SEEDS:
            ws = ran(seed)
            for place in sorted(ws.places):
                items = news.items(ws, place, limit=10_000)
                reachable = [e for e in sim.news_for(ws, place) if news.headline(e) is not None]
                self.assertEqual(len(items), len({news.headline(e) for e in reachable}))
                hours = [i["hour"] for i in items]
                self.assertEqual(hours, sorted(hours, reverse=True))
                self.assertEqual(news.headlines(ws, place, limit=10_000), [i["text"] for i in items])

    def test_only_what_has_reached_the_place(self):
        ws = ran(1, 1)
        self.assertTrue(news.headlines(ws, "market"))
        far = [i for i in news.items(ws, "slaver_pit", limit=10_000) if i["place"] in fixtures_r1_places()]
        self.assertEqual(far, [])

    def test_since_and_limit(self):
        ws = ran(2)
        every = news.items(ws, "market", limit=10_000)
        self.assertGreater(len(every), 3)
        self.assertEqual(len(news.headlines(ws, "market", limit=3)), 3)
        self.assertEqual(news.headlines(ws, "market", limit=3), news.headlines(ws, "market", limit=10_000)[:3])
        cut = every[len(every) // 2]["hour"]
        later = news.items(ws, "market", since=cut, limit=10_000)
        self.assertTrue(later)
        self.assertTrue(all(i["hour"] >= cut for i in later))

    def test_same_hour_ties_keep_event_order(self):
        ws = world(1)
        ws.events.append(ev("settler_left", place="market", hour=6))
        ws.events.append(ev("settler_arrived", place="market", hour=6))
        ws.hour = 6
        self.assertEqual(news.headlines(ws, "market"), ["A settler left market.", "A new settler arrived at market."])

    def test_limit_zero_gives_nothing(self):
        ws = ran(2)
        self.assertEqual(news.items(ws, "market", limit=0), [])
        self.assertEqual(news.headlines(ws, "market", limit=0), [])
        self.assertIn("No news has reached", news.terminal_page(ws, "market", limit=0))

    def test_repeats_collapse_keeping_the_newest(self):
        ws = world(1)
        for h in (0, 6, 12):
            ws.events.append(ev("settler_arrived", place="market", hour=h))
        ws.events.append(ev("settler_left", place="market", hour=6))
        ws.hour = 24
        items = news.items(ws, "market")
        self.assertEqual([i["text"] for i in items], ["A new settler arrived at market.", "A settler left market."])
        self.assertEqual(items[0]["hour"], 12)

    def test_unknown_kinds_in_the_log_are_skipped(self):
        ws = world(1)
        ws.events.append(ev("meteor_strike", place="market"))
        ws.events.append(ev("settler_left", place="market"))
        ws.hour = 6
        self.assertEqual(news.headlines(ws, "market"), ["A settler left market."])

    def test_deterministic_and_read_only(self):
        for seed in SEEDS:
            ws = ran(seed)
            before = ws.to_json()
            a = news.headlines(ws, "market")
            b = news.headlines(WorldState.from_json(before), "market")
            news.terminal_page(ws, "market")
            self.assertEqual(a, b)
            self.assertEqual(ws.to_json(), before)

    def test_player_hooks_show_up(self):
        ws = world(1)
        sim.player_defended(ws, "market")
        sim.player_traded(ws, "market", {"food": 10})
        sim.run(ws, 6)
        lines = news.headlines(ws, "market")
        self.assertIn("A traveller stood guard at market.", lines)
        self.assertIn("A traveller brought supplies to market.", lines)


class TerminalPageTests(unittest.TestCase):
    def test_page_is_width_limited_plain_text(self):
        for seed in SEEDS:
            ws = ran(seed)
            for width in (32, 60):
                page = news.terminal_page(ws, "market", width=width)
                lines = page.split("\n")
                self.assertTrue(all(len(l) <= width for l in lines), (width, max(lines, key=len)))
                self.assertTrue(page.isprintable() or "\n" in page)
                self.assertTrue(lines[0].startswith("market news, Day"))
                self.assertTrue(set(lines[1]) == {"-"})
                self.assertLessEqual(sum(1 for l in lines[2:] if l.startswith("Day ")), news.HEADLINE_LIMIT)

    def test_empty_page_says_so(self):
        ws = world(1)
        page = news.terminal_page(ws, "gate_2")
        self.assertEqual(page.split("\n")[2], "No news has reached gate 2.")
        self.assertIn("Day 1, 00:00", page)

    def test_entries_are_stamped_and_wrapped(self):
        ws = world(1)
        ws.events.append(ev("caravan_raided", place="market", hour=30, faction="settlers", raider="raiders",
                            origin="farm_a", cargo={"food": 4}))
        ws.hour = 36
        page = news.terminal_page(ws, "market", width=40, names={"market": "Market Square"})
        lines = page.split("\n")
        self.assertEqual(lines[0], "Market Square news, Day 2, 12:00")
        self.assertEqual(lines[2], "Day 2, 06:00: A caravan from farm a to")
        self.assertEqual(lines[3], "  Market Square was raided by raiders.")

    def test_page_is_deterministic(self):
        a, b = ran(3), ran(3)
        self.assertEqual(news.terminal_page(a, "farm_a"), news.terminal_page(b, "farm_a"))


def fixtures_r1_places():
    return {p["id"] for p in fixtures.REGION_1["places"]}


if __name__ == "__main__":
    unittest.main()
