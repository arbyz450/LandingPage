import time

from crsf.gui import GuiApp


def test_gui_app_demo_loop_and_commands(tmp_path):
    app = GuiApp(tmp_path / "cards", tmp_path / "units")
    assert app.start({"source": "demo", "input": "none"}) == "started"
    try:
        deadline = time.time() + 8
        snap = {}
        while time.time() < deadline:
            with app.lock:
                snap = dict(app.snapshot)
            if snap.get("running") and snap.get("recs"):
                break
            time.sleep(0.2)
        assert snap.get("running") and snap.get("recs"), snap.get("status")
        assert [h["name"] for h in snap["hand"]] == ["Hog Rider", "Zap", "Giant", "The Log"]
        assert "Golem" in app.command("o golem")
        assert "deck set" in app.command("d golem, night witch, baby dragon, lightning, tornado, lumberjack, mega minion, barbarian barrel")
        assert "deck set" in app.command("m hog rider, zap, giant, log, knight, musketeer, fireball, skeletons")
        assert app.plan is not None and app.plan.opp_archetype == "beatdown"
        assert app.control({"action": "arm"})["msg"] == "armed"
        time.sleep(1.5)
        with app.lock:
            snap = dict(app.snapshot)
        assert snap["autoplay"]["armed"] and snap["autoplay"]["dry_run"]
        assert snap["opp"]["known"][0] == "Golem"
    finally:
        app.stop()
