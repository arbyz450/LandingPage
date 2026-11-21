import json

import cv2
import numpy as np

from crsf.cards import default_db
from crsf.engine import Engine, Move
from crsf.knowledge import Knowledge
from crsf.learn import PlacementPriors, build_priors, situation_of
from crsf.state import GameState, OpponentInfo, Unit
from crsf.vision.healthbars import HealthbarDetector, detect_bars
from crsf.vision.layout import Layout
from crsf.vision.unit_classifier import UnitClassifier

from crsf.vision.synth import make_frame

layout = Layout.load()
db = default_db()


def _draw_bar(frame, layout, tx, ty, side, frac=1.0, full_w=22):
    h, w = frame.shape[:2]
    ax0, ay0, ax1, ay1 = layout.pixels("arena", w, h)
    px = int(ax0 + tx / 18 * (ax1 - ax0))
    py = int(ay0 + (1 - ty / 32) * (ay1 - ay0))
    x0, y0 = px - full_w // 2, py - 16
    cv2.rectangle(frame, (x0, y0), (x0 + full_w, y0 + 4), (20, 20, 20), -1)          # dark trough
    color = (40, 40, 230) if side == "opp" else (230, 120, 30)
    cv2.rectangle(frame, (x0, y0), (x0 + int(full_w * frac), y0 + 4), color, -1)
    # a blob of "sprite" under the bar
    cv2.circle(frame, (px, py + 4), 9, (200, 200, 200) if side == "opp" else (90, 90, 90), -1)


def test_healthbar_detection_positions_sides_and_hp():
    frame = make_frame(layout, elixir=5.0)
    _draw_bar(frame, layout, 3.5, 12.0, "opp", frac=1.0)
    _draw_bar(frame, layout, 14.5, 20.0, "me", frac=0.5)
    det = HealthbarDetector(classifier=None)
    units = det.detect(frame, layout)
    assert len(units) == 2
    opp = next(u for u in units if u.side == "opp")
    me = next(u for u in units if u.side == "me")
    assert abs(opp.x - 3.5) < 1.2 and abs(opp.y - 12.0) < 1.5
    assert abs(me.x - 14.5) < 1.2 and abs(me.y - 20.0) < 1.5
    assert 0.35 <= me.hp_frac <= 0.65 and opp.hp_frac > 0.9
    assert all(u.card == "unknown" for u in units)


def test_healthbar_ignores_elixir_bar_and_cards():
    frame = make_frame(layout, elixir=9.0)        # purple bar + coloured cards, no units
    assert HealthbarDetector().detect(frame, layout) == []


def test_unit_classifier_learns_and_identifies(tmp_path):
    clf = UnitClassifier(tmp_path)
    a = np.zeros((40, 32, 3), np.uint8); cv2.circle(a, (16, 20), 10, (0, 0, 255), -1)
    b = np.zeros((40, 32, 3), np.uint8); cv2.rectangle(b, (6, 6), (26, 34), (255, 0, 0), -1)
    assert clf.add("hog_rider", a) is not None
    clf.add("knight", b)
    assert clf.identify(a)[0] == "hog_rider"
    assert clf.identify(b)[0] == "knight"
    clf2 = UnitClassifier(tmp_path)              # reloads from disk
    assert clf2.identify(a)[0] == "hog_rider"


def test_engine_treats_unknown_unit_as_threat():
    st = GameState(my_elixir=6, hand=["knight", "zap", "giant", "mini_pekka"], units=[Unit("unknown", "opp", 3.5, 11)])
    an = Engine(db, knowledge=Knowledge()).analyse(st)
    assert an.threats and an.best.move.card in ("knight", "mini_pekka")
    assert an.best.move.lane == "left"


def test_priors_build_and_candidates():
    events = []
    for i in range(6):
        events.append({"card": "hog_rider", "side": "me", "x": 3.6 + 0.1 * (i % 2), "y": 15.0, "enemy_units": 0, "enemy_on_my_side": 0, "enemy_same_lane": 0})
    for i in range(4):
        events.append({"card": "hog_rider", "side": "me", "x": 14.4, "y": 15.2, "enemy_units": 0, "enemy_on_my_side": 0, "enemy_same_lane": 0})
    events.append({"card": "knight", "side": "me", "x": 5.0, "y": 10.0, "enemy_units": 1, "enemy_on_my_side": 1, "enemy_same_lane": 1})
    assert situation_of(events[-1]) == "defense"
    pri = build_priors(events, min_count=2)
    assert "hog_rider" in pri["cards"] and "knight" not in pri["cards"]
    hog = pri["cards"]["hog_rider"]["situations"]["offense"]
    assert hog["n"] == 10 and hog["clusters"][0]["x"] == 4.0   # right-lane plays mirrored onto the left
    pp = PlacementPriors(pri)
    cands = pp.candidates("hog_rider", "offense", "either")
    assert any(c["lane"] == "right" and abs(c["x"] - 14.0) < 0.01 for c in cands)


def test_knowledge_counters_and_placements_blend(tmp_path):
    (tmp_path / "counters.json").write_text(json.dumps({
        "golem": {"countered_by": [{"card": "inferno_tower", "quality": 1.0, "note": "melts"}], "counters": [{"card": "skeletons", "quality": 0.1}], "placement_tips": []}
    }))
    (tmp_path / "placements.json").write_text(json.dumps({"mechanics": [], "placements": [
        {"card": "tesla", "situation": "defense", "label": "4-3 tesla", "x": 7.5, "y": 12.0, "lane": "either", "vs": ["hog_rider"], "note": ""}
    ]}))
    (tmp_path / "strategy.json").write_text(json.dumps({
        "principles": [], "phase_policy": {"single": "play cheap"},
        "archetypes": [{"id": "beatdown", "signature_cards": ["golem", "night_witch"], "how_to_beat": "punish opposite lane"}],
        "matchups": [{"me": "cycle", "opp": "beatdown", "plan": "out-cycle"}],
    }))
    k = Knowledge.load(tmp_path, valid_keys=set(c.key for c in db))
    assert k.curated_counter("inferno_tower", "golem")[0] == 1.0
    assert k.curated_counter("golem", "skeletons")[0] == 0.1        # reverse relation imported
    eng = Engine(db, knowledge=k)
    # Hog on the left: the knowledge placement (mirrored to the right as well) should be offered and win.
    st = GameState(my_elixir=6, hand=["tesla", "knight", "zap", "musketeer"], units=[Unit("hog_rider", "opp", 3.5, 14.5)],
                   opp=OpponentInfo(known_deck=["golem", "night_witch"]))
    an = eng.analyse(st, top_n=5)
    best = an.best
    assert best.move.card == "tesla" and best.move.source == "knowledge" and abs(best.move.x - 7.5) < 0.01
    assert any("Opp archetype: beatdown" in n for n in an.notes)
    mv = Move("tesla", "kp:4-3 tesla", 7.5, 12.0, label="4-3 tesla", source="knowledge")
    assert "4-3 tesla" in mv.describe(db, st)


def test_technique_timing_gate_and_hints(tmp_path):
    (tmp_path / "techniques.json").write_text(json.dumps({"techniques": [
        {"id": "ice_spirit_hog", "family": "deploy_timing", "name": "Ice Spirit on Hog at the bridge", "when": "Hog crosses",
         "do": "Drop Ice Spirit in front of the tower as the Hog reaches y=12", "cards": ["ice_spirit"], "vs": ["hog_rider"],
         "x": 4.5, "y": 9.0, "timing": {"type": "distance", "value": "attacker at y=12"}, "priority": 5, "sources": ["knowledge"]}
    ]}))
    k = Knowledge.load(tmp_path, valid_keys=set(c.key for c in db))
    assert k.techniques and k.techniques[0].trigger_y == 12.0
    eng = Engine(db, knowledge=k)
    far = GameState(my_elixir=4, hand=["ice_spirit", "zap", "giant", "mini_pekka"], units=[Unit("hog_rider", "opp", 3.5, 17.5)])
    near = GameState(my_elixir=4, hand=["ice_spirit", "zap", "giant", "mini_pekka"], units=[Unit("hog_rider", "opp", 3.5, 12.0)])
    def ice_score(st):
        an = eng.analyse(st, top_n=30)
        return max(r.score for r in an.recommendations if r.move.card == "ice_spirit" and r.move.lane == "left")
    assert ice_score(near) > ice_score(far) + 0.5
    an = eng.analyse(near)
    assert any(n.startswith("Technique: Ice Spirit on Hog") for n in an.notes)


def test_mechanics_file_loads_and_surfaces():
    from crsf.knowledge import default_knowledge
    k = default_knowledge()
    if "mechanics_verified.json" not in k.loaded:
        pytest.skip("mechanics file not present")
    assert "archer_queen" in k.champions and k.card_mechanics("archer_queen")
    assert k.card_mechanics("knight", "evo") and k.card_mechanics("knight", "hero")
    eng = Engine(db)
    st = GameState(my_elixir=6, hand=["knight", "zap", "giant", "mini_pekka"],
                   opp=OpponentInfo(known_deck=["archer_queen", "golem"], predicted_hand=["archer_queen", "golem"], unknown_slots=6))
    an = eng.analyse(st)
    assert any(n.startswith("Archer Queen:") for n in an.notes)
