"""Autoplay policy: decide when the engine's best move should actually be played.

The engine ranks moves every frame; a bot must not spam the best card every
200 ms. This policy plays only when the recommendation is clearly positive,
stable across consecutive frames, affordable with a margin for elixir-read
error, and not a repeat of something just played.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional

from .engine import Analysis, Recommendation
from .state import GameState


@dataclass
class AutoplayConfig:
    min_score: float = 0.6         # never play a move the engine values below this
    urgent_score: float = 2.5      # play immediately (no stability wait) above this
    stable_frames: int = 2         # otherwise require the same move N frames in a row
    elixir_margin: float = 0.3     # require elixir >= cost + margin (bar read jitter)
    cooldown: float = 0.7          # seconds between any two plays
    same_card_cooldown: float = 2.5
    max_plays_per_10s: int = 6
    deploy_y_limit: float = 15.5   # troops can only go on my half (unless a tower fell)


@dataclass
class AutoPlayer:
    config: AutoplayConfig = field(default_factory=AutoplayConfig)
    paused: bool = False
    history: List[dict] = field(default_factory=list)
    _last_key: Optional[str] = None
    _streak: int = 0

    def _key(self, r: Recommendation) -> str:
        return f"{r.move.card}@{r.move.zone}"

    def decide(self, state: GameState, an: Analysis) -> Optional[Recommendation]:
        """Return the recommendation to execute now, or None."""
        best = an.best
        if self.paused or best is None or best.move.is_wait:
            self._last_key, self._streak = None, 0
            return None
        now = time.time()
        recent = [h for h in self.history if now - h["t"] < 10]
        if recent and now - recent[-1]["t"] < self.config.cooldown:
            return None
        if len(recent) >= self.config.max_plays_per_10s:
            return None
        if any(h["card"] == best.move.card and now - h["t"] < self.config.same_card_cooldown for h in recent):
            return None
        key = self._key(best)
        self._streak = self._streak + 1 if key == self._last_key else 1
        self._last_key = key
        if best.score < self.config.min_score:
            return None
        if best.score < self.config.urgent_score and self._streak < self.config.stable_frames:
            return None
        from .cards import default_db
        card = default_db().get(best.move.card)
        if state.my_elixir < card.cost + self.config.elixir_margin:
            return None
        if best.move.card not in state.hand:
            return None
        return best

    def record(self, rec: Recommendation, entry: dict) -> None:
        self.history.append({"t": time.time(), "card": rec.move.card, "zone": rec.move.zone, "score": rec.score, **entry})
        self._last_key, self._streak = None, 0
