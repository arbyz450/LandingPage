"""Opponent (and own) card-cycle and elixir tracking.

Clash Royale decks are an 8-card queue: 4 in hand, 4 waiting. When a card is
played it goes to the back of the queue, so the four most recently played
*distinct* cards are guaranteed not to be in hand. Everything else known in
the deck is in hand. Exactly what Stockfish does with move ordering, we do
with card ordering.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .cards import CardDB, default_db
from .state import OpponentInfo

DECK_SIZE = 8
HAND_SIZE = 4
MAX_ELIXIR = 10.0


@dataclass
class CycleTracker:
    """Tracks one player's 8-card cycle from the order cards were played."""

    known_deck: List[str] = field(default_factory=list)
    history: List[Tuple[float, str]] = field(default_factory=list)   # (match_clock_seconds, card)

    def record_play(self, card: str, t: float = 0.0) -> None:
        if card not in self.known_deck:
            if len(self.known_deck) >= DECK_SIZE:
                # Deck "changed" (mirror / misread). Drop the oldest-seen card.
                self.known_deck.pop(0)
            self.known_deck.append(card)
        self.history.append((t, card))

    def set_deck(self, deck: List[str]) -> None:
        self.known_deck = list(deck)[:DECK_SIZE]

    def out_of_hand(self) -> List[str]:
        """Last four distinct cards played, most recent last."""
        seen: List[str] = []
        for _, c in reversed(self.history):
            if c not in seen:
                seen.append(c)
            if len(seen) == HAND_SIZE:
                break
        seen.reverse()
        return seen

    def predicted_hand(self) -> List[str]:
        out = set(self.out_of_hand())
        return [c for c in self.known_deck if c not in out]

    def next_card(self) -> Optional[str]:
        """The card that comes back into hand next (oldest of the out-of-hand four)."""
        out = self.out_of_hand()
        return out[0] if len(out) == HAND_SIZE else None

    @property
    def unknown_slots(self) -> int:
        return max(0, DECK_SIZE - len(self.known_deck))

    def reset(self) -> None:
        self.known_deck.clear()
        self.history.clear()


@dataclass
class ElixirEstimator:
    """Estimates a player's elixir from their plays and the regen rate."""

    elixir: float = 5.0
    last_t: Optional[float] = None    # match clock in *elapsed* seconds

    def tick(self, elapsed: float, seconds_per_elixir: float) -> None:
        """Advance to ``elapsed`` seconds since match start."""
        if self.last_t is None:
            self.last_t = elapsed
            return
        dt = elapsed - self.last_t
        if dt < 0:            # clock reset -> new match
            self.reset()
            self.last_t = elapsed
            return
        self.elixir = min(MAX_ELIXIR, self.elixir + dt / seconds_per_elixir)
        self.last_t = elapsed

    def spend(self, cost: float) -> None:
        self.elixir = max(0.0, self.elixir - cost)

    def reset(self) -> None:
        self.elixir = 5.0
        self.last_t = None


class OpponentTracker:
    """Combines cycle tracking and elixir estimation for the opponent."""

    def __init__(self, db: Optional[CardDB] = None):
        self.db = db or default_db()
        self.cycle = CycleTracker()
        self.elixir = ElixirEstimator()

    def record_play(self, card: str, elapsed: float = 0.0) -> None:
        c = self.db.get(card)
        self.cycle.record_play(c.key, elapsed)
        self.elixir.spend(c.cost)

    def undo_last(self) -> Optional[str]:
        if not self.cycle.history:
            return None
        _, card = self.cycle.history.pop()
        self.elixir.elixir = min(MAX_ELIXIR, self.elixir.elixir + self.db.get(card).cost)
        return card

    def tick(self, elapsed: float, seconds_per_elixir: float) -> None:
        self.elixir.tick(elapsed, seconds_per_elixir)

    def reset(self) -> None:
        self.cycle.reset()
        self.elixir.reset()

    def info(self) -> OpponentInfo:
        return OpponentInfo(
            elixir=round(self.elixir.elixir, 1),
            known_deck=list(self.cycle.known_deck),
            predicted_hand=self.cycle.predicted_hand(),
            out_of_hand=self.cycle.out_of_hand(),
            unknown_slots=self.cycle.unknown_slots,
        )
