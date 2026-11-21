from crsf.cards import default_db
from crsf.decks import deck_pool, random_deck
from crsf.sim import Match, play_match
import random

db = default_db()
HOG = ["hog_rider", "ice_spirit", "skeletons", "log", "musketeer", "cannon", "fireball", "ice_golem"]
GOLEM = ["golem", "night_witch", "baby_dragon", "lightning", "tornado", "lumberjack", "mega_minion", "barbarian_barrel"]


def test_match_runs_to_a_result_and_both_sides_play():
    r = play_match(HOG, GOLEM, seed=4)
    assert r["winner"] in (0, 1, None)
    assert r["plays"][0] > 5 and r["plays"][1] > 5
    assert 30 <= r["t"] <= 300.5


def test_graveyard_spawns_and_golem_leaves_golemites():
    m = Match(HOG, GOLEM, db, seed=1)
    m.p[1].queue = ["golem"] + [c for c in m.p[1].queue if c != "golem"]
    m.p[1].elixir = 10
    assert m.deploy(1, "golem", "left", 3.0)
    g = next(u for u in m.units if u.card.key == "golem")
    g.hp = 0
    m.step()
    assert sum(u.alive_count for u in m.units if u.card.key == "golemite") == 2
    m2 = Match(["graveyard"] + HOG[1:], GOLEM, db, seed=2)
    m2.p[0].queue = ["graveyard"] + [c for c in m2.p[0].queue if c != "graveyard"]
    m2.p[0].elixir = 10
    assert m2.deploy(0, "graveyard", "left", 25.0)
    for _ in range(6):
        m2.step()
    assert any(u.card.key == "skeletons" and u.side == 0 for u in m2.units)


def test_deploy_rules():
    m = Match(HOG, GOLEM, db, seed=3)
    m.p[0].queue = ["hog_rider"] + [c for c in m.p[0].queue if c != "hog_rider"]
    m.p[0].elixir = 10
    assert not m.deploy(0, "hog_rider", "left", 20.0)       # enemy half while their tower stands
    assert m.deploy(0, "hog_rider", "left", 15.0)
    assert m.p[0].elixir == 6 and m.p[0].queue[-1] == "hog_rider"


def test_deck_pool_is_finite_and_valid():
    pool = deck_pool(n_random=15, seed=9)
    assert len(pool) >= 15
    for d in pool:
        assert len(d["cards"]) == 8 and len(set(d["cards"])) == 8
        assert all(db.find(c) for c in d["cards"])
    d = random_deck(random.Random(1), db)
    assert 2.6 <= sum(db.get(c).cost for c in d["cards"]) / 8 <= 4.6
