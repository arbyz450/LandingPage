import time

from crsf.autoplay import AutoPlayer, AutoplayConfig
from crsf.cards import default_db
from crsf.engine import Engine
from crsf.knowledge import Knowledge
from crsf.state import GameState, OpponentInfo, Unit

db = default_db()
eng = Engine(db, knowledge=Knowledge())


def test_autoplay_waits_for_stability_then_plays_and_cools_down():
    bot = AutoPlayer(AutoplayConfig(stable_frames=2, urgent_score=50, cooldown=0.2, same_card_cooldown=0.5))
    st = GameState(my_elixir=10, hand=["hog_rider", "ice_spirit", "fireball", "skeleton_army"],
                   opp=OpponentInfo(elixir=2, known_deck=["giant", "witch"], predicted_hand=["giant", "witch"], unknown_slots=6))
    an = eng.analyse(st)
    assert an.best.move.card == "hog_rider"
    assert bot.decide(st, an) is None                 # first sighting: not stable yet
    rec = bot.decide(st, an)
    assert rec is not None and rec.move.card == "hog_rider"
    bot.record(rec, {"tile_px": (0, 0)})
    assert bot.decide(st, an) is None                 # cooldown
    time.sleep(0.25)
    assert bot.decide(st, an) is None                 # same-card cooldown
    assert len(bot.history) == 1


def test_autoplay_urgent_defense_is_immediate_and_respects_elixir():
    bot = AutoPlayer(AutoplayConfig())
    st = GameState(my_elixir=8, hand=["skeleton_army", "log", "inferno_tower", "hog_rider"],
                   units=[Unit("giant", "opp", 3.5, 13), Unit("witch", "opp", 3.5, 15)])
    an = eng.analyse(st)
    rec = bot.decide(st, an)
    assert rec is not None and rec.move.card == "inferno_tower"
    st.my_elixir = 5.1                                # bar read says 5.1: too close to the cost
    bot2 = AutoPlayer(AutoplayConfig())
    an2 = eng.analyse(st)
    assert an2.best.move.card != "inferno_tower" or bot2.decide(st, an2) is None


def test_autoplay_never_plays_wait_or_negative():
    bot = AutoPlayer(AutoplayConfig())
    st = GameState(my_elixir=4, hand=["hog_rider", "ice_spirit", "inferno_tower", "skeleton_army"],
                   opp=OpponentInfo(elixir=9, known_deck=["golem"], predicted_hand=["golem"], unknown_slots=7))
    an = eng.analyse(st)
    assert an.best.move.is_wait
    assert bot.decide(st, an) is None
    bot.paused = True
    assert bot.decide(st, an) is None
