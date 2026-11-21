from crsf.cards import default_db

REQUIRED = {"key", "name", "cost", "rarity", "kind", "transport", "targets", "hp", "damage",
            "hit_speed", "range", "speed", "count", "splash", "roles", "lifetime", "notes"}


def test_db_loads_many_cards():
    db = default_db()
    assert len(db) >= 100


def test_lookup_variants():
    db = default_db()
    assert db.get("P.E.K.K.A").key == "pekka"
    assert db.get("The Log").key == "log"
    assert db.get("mini pekka").key == "mini_pekka"
    assert db.get("Hog Rider").key == "hog_rider"
    assert db.find("not_a_card") is None
    assert db.search("musk")[0].key == "musketeer"


def test_targeting_rules():
    db = default_db()
    assert db.get("musketeer").can_target(db.get("balloon"))
    assert not db.get("knight").can_target(db.get("balloon"))
    assert not db.get("giant").can_target(db.get("knight"))
    assert db.get("giant").can_target(db.get("cannon"))
    assert db.get("arrows").can_target(db.get("minions"))
    assert not db.get("log").can_target(db.get("minions"))


def test_sane_costs():
    db = default_db()
    assert db.get("skeletons").cost == 1
    assert db.get("golem").cost == 8
    assert db.get("three_musketeers").cost == 9
    for c in db:
        assert 0 <= c.cost <= 10
        assert c.kind in ("troop", "spell", "building")
        if c.kind == "spell":
            assert c.hp == 0
