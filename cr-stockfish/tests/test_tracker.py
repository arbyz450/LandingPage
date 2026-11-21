from crsf.tracker import CycleTracker, ElixirEstimator, OpponentTracker


def test_cycle_prediction():
    t = CycleTracker()
    t.set_deck(["a", "b", "c", "d", "e", "f", "g", "h"])
    for i, c in enumerate(["a", "b", "c", "d"]):
        t.record_play(c, i)
    assert t.out_of_hand() == ["a", "b", "c", "d"]
    assert t.predicted_hand() == ["e", "f", "g", "h"]
    assert t.next_card() == "a"
    t.record_play("e", 5)
    # a is back in hand, b is next
    assert "a" in t.predicted_hand()
    assert t.next_card() == "b"
    assert t.out_of_hand() == ["b", "c", "d", "e"]


def test_cycle_learns_deck_from_plays():
    t = CycleTracker()
    for i, c in enumerate(["hog_rider", "ice_spirit", "hog_rider", "log"]):
        t.record_play(c, i)
    assert t.known_deck == ["hog_rider", "ice_spirit", "log"]
    assert t.unknown_slots == 5
    assert t.out_of_hand() == ["ice_spirit", "hog_rider", "log"]
    assert t.next_card() is None   # fewer than four distinct plays


def test_elixir_estimator_regen_and_spend():
    e = ElixirEstimator()
    e.tick(0.0, 2.8)
    e.spend(4)
    assert e.elixir == 1.0
    e.tick(2.8 * 3, 2.8)
    assert abs(e.elixir - 4.0) < 1e-6
    e.tick(1000, 2.8)
    assert e.elixir == 10.0
    e.tick(0.0, 2.8)          # clock went backwards -> new match
    assert e.elixir == 5.0


def test_opponent_tracker_undo():
    o = OpponentTracker()
    o.record_play("giant", 0)
    assert o.elixir.elixir == 0.0
    assert o.info().known_deck == ["giant"]
    assert o.undo_last() == "giant"
    assert o.elixir.elixir == 5.0
    assert o.info().known_deck == ["giant"]   # still known to be in the deck


def test_plays_until_and_status():
    t = CycleTracker()
    t.set_deck(["a", "b", "c", "d", "e", "f", "g"])          # one unknown slot
    for i, c in enumerate(["a", "b", "c"]):
        t.record_play(c, i)
    assert t.plays_until("d") == 0 and t.plays_until("a") == 1 and t.plays_until("c") == 3
    assert t.plays_until("zzz") is None
    rows = t.status()
    assert [r["state"] for r in rows].count("unknown") == 1
    assert rows[0]["state"] == "hand"
    back = [r for r in rows if r["state"] == "back"]
    assert [r["card"] for r in back] == ["a", "b", "c"]


def test_elixir_uncertainty_and_leak():
    e = ElixirEstimator()
    e.tick(0.0, 2.8)
    e.spend(3)
    assert e.uncertainty == 0.5
    e.tick(30.0, 2.8)
    assert e.elixir == 10.0 and e.uncertainty > 2.0
    e.tick(35.0, 2.8)
    assert e.leaking_for() >= 4.9 and e.leaked > 0
    e.spend(4)
    assert e.leaking_for() == 0.0 and len(e.history) >= 2


def test_trade_ledger():
    from crsf.tracker import TradeLedger
    l = TradeLedger()
    l.add("opp", "skeleton_army", 3, 10.0)
    l.add("me", "log", 2, 12.0)
    l.add("me", "hog_rider", 4, 40.0)
    assert l.lead() == -3.0 and l.lead(since=30) == -4.0
    tr = l.trades()
    assert len(tr) == 1 and tr[0]["net"] == 1.0 and tr[0]["opp_card"] == "skeleton_army"
