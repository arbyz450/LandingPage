import numpy as np
import pytest

from crsf.advisor import Advisor
from crsf.vision.capture import find_game_frame, crop_game_frame
from crsf.vision.elixir import read_elixir
from crsf.vision.hand import CardMatcher, is_greyed, read_hand
from crsf.vision.layout import Layout

from crsf.vision.synth import CARD_STYLES, draw_card, make_frame

layout = Layout.load()


@pytest.mark.parametrize("elixir", [0.0, 1.0, 3.7, 6.4, 9.0, 10.0])
def test_elixir_reading(elixir):
    frame = make_frame(layout, elixir=elixir)
    got = read_elixir(frame, layout)
    assert got is not None
    assert abs(got - elixir) <= 0.25


def test_elixir_none_when_no_hud():
    frame = np.full((960, 540, 3), 200, dtype=np.uint8)
    assert read_elixir(frame, layout) is None


def test_find_game_frame_with_letterbox():
    frame = make_frame(layout, letterbox=370)
    x, y, w, h = find_game_frame(frame)
    assert abs(x - 370) <= 2 and abs(w - 540) <= 3 and h == 960
    cropped = crop_game_frame(frame)
    assert cropped.shape[1] in (538, 539, 540, 541, 542)


def test_find_game_frame_on_desktop_with_sidebar():
    frame = make_frame(layout, elixir=6.0, desktop=120)
    x, y, w, h = find_game_frame(frame)
    assert abs(x - 240) <= 6 and abs(y - 120) <= 8 and abs(w - 540) <= 8 and abs(h - 960) <= 12
    cropped = crop_game_frame(frame)
    assert abs((read_elixir(cropped, layout) or 0) - 6.0) <= 0.3


def test_tile_mapping_roundtrip():
    shape = (960, 540)
    for tx, ty in ((3.5, 6.5), (9.0, 16.0), (14.5, 25.5), (0.0, 0.0), (18.0, 32.0)):
        px, py = layout.tiles_to_pixel(shape, tx, ty)
        bx, by = layout.arena_to_tiles(shape, px, py)
        assert abs(bx - tx) < 0.1 and abs(by - ty) < 0.15


def test_find_game_frame_fallback_centres_portrait():
    img = np.full((900, 1600, 3), 180, dtype=np.uint8)      # no bars at all
    x, y, w, h = find_game_frame(img)
    assert h == 900 and abs(w - 506) <= 1 and abs(x - 547) <= 1


def _matcher():
    m = CardMatcher()
    for key in CARD_STYLES:
        m.add(key, draw_card(80, 100, key))        # different size than the live slot
    return m


def test_hand_matching():
    m = _matcher()
    hand = ["hog_rider", "zap", "giant", "log"]
    frame = make_frame(layout, hand=hand, next_card="knight", greyed=[False, False, True, False])
    slots, nxt = read_hand(frame, layout, m)
    assert [s[0] for s in slots] == hand
    assert slots[2][2] is True and slots[0][2] is False
    assert nxt[0] == "knight"


def test_unknown_card_rejected():
    m = CardMatcher()
    m.add("knight", draw_card(key="knight"))
    key, conf = m.identify(np.random.default_rng(0).integers(0, 255, (120, 96, 3), dtype=np.uint8))
    assert key is None


def test_greyed_detection():
    assert is_greyed(draw_card(key="knight", greyed=True))
    assert not is_greyed(draw_card(key="knight"))


def test_advisor_pipeline_on_synthetic_frames():
    adv = Advisor(layout=layout, matcher=_matcher(), use_ocr=False)
    f1 = make_frame(layout, elixir=7.0, hand=["hog_rider", "zap", "giant", "log"], next_card="knight", letterbox=200)
    st, an = adv.step(f1)
    assert abs(st.my_elixir - 7.0) <= 0.25
    assert st.hand == ["hog_rider", "zap", "giant", "log"]
    assert an.best is not None
    # Opponent plays something: tracker + engine notes react.
    assert "Giant" in adv.command("o giant")
    st, an = adv.step(f1)
    assert st.opp.known_deck == ["giant"]
    assert st.opp.elixir < 5.0
    # My hand changes: the played card is recorded in my cycle.
    f2 = make_frame(layout, elixir=3.0, hand=["knight", "zap", "giant", "log"], next_card="musketeer", letterbox=200)
    st, an = adv.step(f2)
    assert adv.me.history and adv.me.history[-1][1] == "hog_rider"
    assert "musketeer" in st.my_deck
    # Manual unit placement feeds the engine.
    adv.command("x balloon opp right")
    st, an = adv.step(f2)
    assert an.threats and an.threats[0][0].card == "balloon"
    assert "reset" in adv.command("r")


def test_video_source_and_learn_clock(tmp_path):
    import cv2
    from crsf.vision.capture import VideoSource
    from crsf.vision.synth import CARD_STYLES, draw_card
    path = tmp_path / "match.avi"
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 8.0, (540, 960))
    assert w.isOpened()
    for i in range(40):                      # 5 seconds of video at 8 fps
        hand = ["hog_rider", "zap", "giant", "log"] if i < 24 else ["knight", "zap", "giant", "log"]
        w.write(make_frame(layout, elixir=min(10.0, 2.0 + i * 0.2), hand=hand, next_card="musketeer"))
    w.release()
    src = VideoSource(path, sample_fps=4.0)
    frames = list(src.frames())
    assert 18 <= len(frames) <= 21 and 4.5 <= src.pos_seconds <= 5.1
    m = CardMatcher()
    for key in CARD_STYLES:
        m.add(key, draw_card(80, 100, key))
    adv = Advisor(layout=layout, matcher=m, use_ocr=False)
    src2 = VideoSource(path, sample_fps=4.0)
    for raw in src2.frames():
        adv.clock.external_elapsed = src2.pos_seconds
        st, an = adv.step(raw)
    assert abs((180 - st.time_left) - src2.pos_seconds) < 0.6     # clock follows the video
    assert adv.me.history and adv.me.history[-1][1] == "hog_rider"  # the deploy was logged with video time
    assert 2.5 <= adv.me.history[-1][0] <= 3.6


def test_frame_redetected_after_loading_screen():
    """A loading screen gives a wrong frame; once the HUD appears the frame must be re-detected."""
    adv = Advisor(layout=layout, matcher=_matcher(), use_ocr=False)
    loading = np.full((1032, 624, 3), (30, 30, 30), dtype=np.uint8)          # dark splash, no arena, no elixir bar
    loading[200:400, 100:500] = (200, 180, 160)
    st, _ = adv.step(loading)
    first = adv.frame_bbox
    assert first is not None and st.my_elixir == 5.0                            # default, nothing readable
    live = make_frame(layout, elixir=6.0, hand=["hog_rider", "zap", "giant", "log"], desktop=120)
    st, _ = adv.step(live)
    assert adv.frame_bbox != first
    assert abs(adv.frame_bbox[0] - 240) <= 6 and abs(adv.frame_bbox[2] - 540) <= 8
    assert abs(st.my_elixir - 6.0) <= 0.3
    assert st.hand == ["hog_rider", "zap", "giant", "log"]
