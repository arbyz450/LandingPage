import pytest

from crsf.cards import default_db
from crsf.engine import Engine, counter_score, generate_moves
from crsf.state import GameState, OpponentInfo, Unit

db = default_db()
eng = Engine(db)


def cs(defender, attacker, hp=1.0):
    return counter_score(db, db.get(defender), Unit(attacker, "opp", 3.5, 12.0, hp_frac=hp))


@pytest.mark.parametrize("good,bad,attacker", [
    ("skeleton_army", "skeletons", "giant"),
    ("inferno_tower", "skeleton_army", "golem"),
    ("log", "fireball", "skeleton_army"),   # both kill it, log is at least as good per cost here (both 1.0)
    ("musketeer", "knight", "balloon"),
    ("valkyrie", "musketeer", "goblin_gang"),
    ("arrows", "zap", "minion_horde"),
    ("mega_knight", "skeletons", "skeleton_army"),
    ("zap", "arrows", "inferno_dragon"),
])
def test_counter_ordering(good, bad, attacker):
    assert cs(good, attacker) >= cs(bad, attacker)


def test_cannot_hit_air():
    assert cs("knight", "balloon") == 0.0
    assert cs("log", "minions") == 0.0


def test_swarm_melts_to_splash():
    assert cs("skeleton_army", "valkyrie") < 0.2
    assert cs("skeleton_army", "pekka") > 0.7


def test_building_pulls_building_targeters():
    assert cs("cannon", "hog_rider") >= 0.6
    assert cs("tombstone", "giant") >= 0.6


def test_generate_moves_respects_elixir():
    st = GameState(my_elixir=3, hand=["giant", "knight", "fireball", "zap"])
    cards = {m.card for m in generate_moves(db, st)}
    assert "giant" not in cards and "fireball" not in cards
    assert "knight" in cards and "zap" in cards and None in cards


def test_defends_tank_push_with_inferno():
    st = GameState(my_elixir=8, hand=["skeleton_army", "log", "inferno_tower", "hog_rider"],
                   units=[Unit("giant", "opp", 3.5, 13), Unit("witch", "opp", 3.5, 15)])
    best = eng.analyse(st).best
    assert best.move.card == "inferno_tower"
    assert best.move.lane in ("left", "center") and best.move.x <= 9.0


def test_air_threat_picks_anti_air_not_bridge():
    st = GameState(my_elixir=6, hand=["musketeer", "zap", "giant", "mini_pekka"],
                   units=[Unit("balloon", "opp", 14.5, 16.5)])
    best = eng.analyse(st).best
    assert best.move.card == "musketeer"
    assert best.move.lane == "right"
    assert best.move.zone not in ("bridge_right", "bridge_left")


def test_punishes_low_elixir_opponent():
    st = GameState(my_elixir=10, hand=["hog_rider", "ice_spirit", "fireball", "skeleton_army"],
                   opp=OpponentInfo(elixir=2, known_deck=["giant", "witch", "zap", "musketeer"],
                                    predicted_hand=["giant", "witch"], out_of_hand=["zap", "musketeer"], unknown_slots=4))
    best = eng.analyse(st).best
    assert best.move.card == "hog_rider"
    assert best.move.cls == "bridge"


def test_waits_against_loaded_opponent():
    st = GameState(my_elixir=4, hand=["hog_rider", "ice_spirit", "inferno_tower", "skeleton_army"],
                   opp=OpponentInfo(elixir=9, known_deck=["golem", "night_witch", "baby_dragon", "lightning"],
                                    predicted_hand=["golem", "night_witch", "baby_dragon", "lightning"], unknown_slots=4))
    assert eng.analyse(st).best.move.is_wait


def test_never_leaks():
    st = GameState(my_elixir=10, hand=["ice_spirit", "skeletons", "knight", "log"],
                   opp=OpponentInfo(elixir=10))
    an = eng.analyse(st)
    assert not an.best.move.is_wait


def test_rocket_finishes_tower():
    st = GameState(time_left=20, my_elixir=7, hand=["rocket", "ice_spirit", "knight", "skeleton_army"])
    st.towers["opp_left"].hp = 300
    best = eng.analyse(st).best
    assert best.move.card == "rocket" and best.move.zone == "tower:left"


def test_keeps_counter_in_reserve():
    # Opponent has Balloon in hand with elixir; our only answer is Musketeer (4).
    st = GameState(my_elixir=6, hand=["musketeer", "giant", "knight", "zap"],
                   opp=OpponentInfo(elixir=7, known_deck=["balloon"], predicted_hand=["balloon"], unknown_slots=7))
    an = eng.analyse(st, top_n=60)
    giant_moves = [r for r in an.recommendations if r.move.card == "giant"]
    assert giant_moves and any("Balloon" in x for x in giant_moves[0].reasons)


def test_eval_sign():
    st = GameState(my_elixir=8, opp=OpponentInfo(elixir=2))
    st.towers["opp_left"].alive = False
    ev, _ = eng.evaluate_position(st)
    assert ev > 5
    st2 = GameState(my_elixir=2, opp=OpponentInfo(elixir=8), units=[Unit("golem", "opp", 3.5, 12)])
    ev2, _ = eng.evaluate_position(st2)
    assert ev2 < -5


def test_state_roundtrip():
    st = GameState(my_elixir=7.3, hand=["knight", "", "zap", "log"], units=[Unit("giant", "opp", 3.5, 13, 0.5)])
    st.towers["my_left"].hp = 1000
    d = st.to_dict()
    back = GameState.from_dict(d)
    assert back.my_elixir == 7.3 and back.hand == st.hand
    assert back.towers["my_left"].hp == 1000
    assert back.units[0].card == "giant" and back.units[0].hp_frac == 0.5


def test_opening_does_not_hog_at_bridge():
    st = GameState(time_left=178, my_elixir=5, hand=["hog_rider", "ice_spirit", "fireball", "musketeer"])
    best = eng.analyse(st).best
    assert best.move.card != "hog_rider"


def test_punish_opposite_lane_when_golem_in_back():
    st = GameState(my_elixir=8, hand=["hog_rider", "ice_spirit", "fireball", "musketeer"],
                   opp=OpponentInfo(elixir=1), units=[Unit("golem", "opp", 3.5, 29)])
    best = eng.analyse(st).best
    assert best.move.card == "hog_rider" and best.move.lane == "right"
    assert any("punish" in r for r in best.reasons)


def test_overtime_behind_on_tiebreak_is_aggressive():
    st = GameState(time_left=60, overtime=True, my_elixir=9, hand=["fireball", "ice_spirit", "knight", "skeletons"], opp=OpponentInfo(elixir=9))
    st.towers["my_left"].hp = 800
    st.towers["opp_left"].hp = 1500
    an = eng.analyse(st, top_n=10)
    fire = next(r for r in an.recommendations if r.move.card == "fireball" and r.move.zone == "tower:left")
    assert fire.score > 0
