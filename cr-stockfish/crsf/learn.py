"""Learning from gameplay: deploy events -> placement priors.

Run ``python -m crsf learn`` while a pro's match plays on your screen (a
YouTube replay in a window works). The advisor reads the pro's hand and
elixir like it reads yours, sees each card leave the hand, and finds where
the new friendly health bar appeared. Every deploy becomes an event with its
context (lane, enemy presence, elixir, phase). ``python -m crsf priors``
turns thousands of events into ``knowledge/priors.json``: for each card, the
positions pros actually use, split by situation, which the engine then adds
as candidate placements with a bonus.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional

GRID = 1.0       # tile bin size


def situation_of(ev: dict) -> str:
    if ev.get("enemy_on_my_side", 0) > 0 and ev.get("enemy_same_lane", 0) > 0:
        return "defense"
    if ev.get("enemy_units", 0) > 0:
        return "counter_push"
    return "offense"


def _mirror_x(x: float) -> float:
    return 18.0 - x


def load_events(paths: Iterable[Path]) -> List[dict]:
    events: List[dict] = []
    for p in paths:
        p = Path(p)
        files = sorted(p.glob("*.jsonl")) if p.is_dir() else [p]
        for f in files:
            with open(f, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
    return events


def build_priors(events: List[dict], min_count: int = 2, side: str = "me") -> dict:
    """Aggregate deploy events into per-card, per-situation placement clusters.

    Placements are normalised to the LEFT lane (mirrored when x > 9) so both
    lanes share statistics; the engine mirrors them back.
    """
    bins: Dict[str, Dict[str, Dict[tuple, int]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    totals: Dict[str, int] = defaultdict(int)
    for ev in events:
        if ev.get("side", "me") != side or not ev.get("card") or ev["card"] == "unknown":
            continue
        x, y = float(ev["x"]), float(ev["y"])
        if x > 9.0:
            x = _mirror_x(x)
        bx, by = round(x / GRID) * GRID, round(y / GRID) * GRID
        bins[ev["card"]][situation_of(ev)][(bx, by)] += 1
        totals[ev["card"]] += 1
    out = {"grid": GRID, "cards": {}}
    for card, sits in bins.items():
        entry = {"n": totals[card], "situations": {}}
        for sit, cells in sits.items():
            n_sit = sum(cells.values())
            clusters = []
            for (bx, by), c in sorted(cells.items(), key=lambda kv: -kv[1]):
                if c < min_count:
                    continue
                clusters.append({"x": bx, "y": by, "count": c, "share": round(c / n_sit, 3)})
            if clusters:
                entry["situations"][sit] = {"n": n_sit, "clusters": clusters[:6]}
        if entry["situations"]:
            out["cards"][card] = entry
    return out


class PlacementPriors:
    """Engine-side view of priors.json."""

    def __init__(self, data: Optional[dict] = None):
        self.data = data or {"cards": {}}

    @classmethod
    def load(cls, path: Path) -> "PlacementPriors":
        path = Path(path)
        if not path.exists():
            return cls()
        with open(path, "r", encoding="utf-8") as fh:
            return cls(json.load(fh))

    def __len__(self) -> int:
        return len(self.data.get("cards", {}))

    def candidates(self, card: str, situation: str, lane: str = "either", top: int = 3) -> List[dict]:
        entry = self.data.get("cards", {}).get(card)
        if not entry:
            return []
        sit = entry["situations"].get(situation) or next(iter(entry["situations"].values()), None)
        if not sit:
            return []
        out = []
        for c in sit["clusters"][:top]:
            # strength: log-scaled count times share, capped
            strength = min(1.0, math.log1p(c["count"]) / math.log1p(25)) * (0.5 + 0.5 * c["share"])
            if lane in ("left", "either", "center"):
                out.append({"x": c["x"], "y": c["y"], "strength": strength, "lane": "left"})
            if lane in ("right", "either") and c["x"] < 8.9:
                out.append({"x": _mirror_x(c["x"]), "y": c["y"], "strength": strength, "lane": "right"})
        return out
