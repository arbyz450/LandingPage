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
