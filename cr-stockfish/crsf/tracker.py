"""Opponent (and own) card-cycle and elixir tracking.

Clash Royale decks are an 8-card queue: 4 in hand, 4 waiting. When a card is
played it goes to the back of the queue, so the four most recently played
*distinct* cards are guaranteed not to be in hand. Everything else known in
the deck is in hand. Exactly what Stockfish does with move ordering, we do
with card ordering.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

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

    def plays_until(self, card: str) -> Optional[int]:
        """0 = in hand now; N = back in hand after N more plays; None = unknown card."""
        if card not in self.known_deck:
            return None
        out = self.out_of_hand()
        if card not in out:
            return 0
        return out.index(card) + 1

    def status(self) -> List[dict]:
        """One row per known card (plus placeholders for unknown slots), for a card-counter panel."""
        rows = []
        for c in self.known_deck:
            n = self.plays_until(c)
            rows.append({"card": c, "state": "hand" if n == 0 else "back", "plays_until": n,
                         "times_played": sum(1 for _, k in self.history if k == c)})
        rows.sort(key=lambda r: (r["state"] != "hand", r["plays_until"] or 0))
        for _ in range(self.unknown_slots):
            rows.append({"card": None, "state": "unknown", "plays_until": None, "times_played": 0})
        return rows

    def reset(self) -> None:
        self.known_deck.clear()
        self.history.clear()


@dataclass
class ElixirEstimator:
    """Estimates a player's elixir from their plays and the regen rate.

    Also keeps a short history, an uncertainty band (grows while no play has
    been observed, because a missed play means they have *less* than we think)
    and a leak timer (how long they have been sitting at 10).
    """

    elixir: float = 5.0
    last_t: Optional[float] = None    # match clock in *elapsed* seconds
    last_spend_t: Optional[float] = None
    cap_since: Optional[float] = None
    history: List[Tuple[float, float]] = field(default_factory=list)   # (elapsed, elixir)
    leaked: float = 0.0               # total elixir they could have had but wasted at the cap

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
        gained = dt / seconds_per_elixir
        new = self.elixir + gained
        if new > MAX_ELIXIR:
            self.leaked += new - MAX_ELIXIR
            new = MAX_ELIXIR
        self.elixir = new
        if self.elixir >= MAX_ELIXIR - 1e-6:
            if self.cap_since is None:
                self.cap_since = elapsed
        else:
            self.cap_since = None
        self.last_t = elapsed
        if not self.history or elapsed - self.history[-1][0] >= 1.0:
            self.history.append((round(elapsed, 1), round(self.elixir, 2)))
            if len(self.history) > 400:
                self.history.pop(0)

    def spend(self, cost: float) -> None:
        self.elixir = max(0.0, self.elixir - cost)
        self.last_spend_t = self.last_t
        self.cap_since = None
        if self.last_t is not None:
            self.history.append((round(self.last_t, 1), round(self.elixir, 2)))

    @property
    def uncertainty(self) -> float:
        """How far below the estimate they could realistically be (missed plays)."""
        if self.last_t is None or self.last_spend_t is None:
            return 1.0
        quiet = self.last_t - self.last_spend_t
        return min(3.0, 0.5 + quiet / 15.0)

    def leaking_for(self) -> float:
        if self.cap_since is None or self.last_t is None:
            return 0.0
        return self.last_t - self.cap_since

    def reset(self) -> None:
        self.elixir = 5.0
        self.last_t = None
        self.last_spend_t = None
        self.cap_since = None
        self.history.clear()
        self.leaked = 0.0


@dataclass
class TradeLedger:
    """Scores elixir exchanges: what each side spent, and the running lead."""

    my_plays: List[Tuple[float, str, float]] = field(default_factory=list)     # (t, card, cost)
    opp_plays: List[Tuple[float, str, float]] = field(default_factory=list)
    pair_window: float = 7.0

    def add(self, side: str, card: str, cost: float, t: float) -> None:
        (self.my_plays if side == "me" else self.opp_plays).append((t, card, cost))

    def spent(self, side: str, since: Optional[float] = None) -> float:
        plays = self.my_plays if side == "me" else self.opp_plays
        return sum(c for t, _, c in plays if since is None or t >= since)

    def lead(self, since: Optional[float] = None) -> float:
        """Positive = opponent has spent more than me (I am up on elixir spent)."""
        return self.spent("opp", since) - self.spent("me", since)

    def trades(self, limit: int = 6) -> List[dict]:
        """Pair each of my plays with opponent plays close in time; sign = elixir gained."""
        out = []
        for t, card, cost in self.my_plays[-40:]:
            near = [(ot, oc, occ) for ot, oc, occ in self.opp_plays if abs(ot - t) <= self.pair_window]
            if not near:
                continue
            ot, ocard, ocost = min(near, key=lambda x: abs(x[0] - t))
            out.append({"t": round(t, 1), "my_card": card, "my_cost": cost, "opp_card": ocard, "opp_cost": ocost, "net": round(ocost - cost, 1)})
        return out[-limit:]

    def reset(self) -> None:
        self.my_plays.clear()
        self.opp_plays.clear()


class OpponentTracker:
    """Combines cycle tracking and elixir estimation for the opponent."""

    def __init__(self, db: Optional[CardDB] = None):
        self.db = db or default_db()
        self.cycle = CycleTracker()
        self.elixir = ElixirEstimator()
        self.flags: Dict[str, str] = {}      # card -> "evo" | "hero"

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
        self.flags.clear()

    def info(self) -> OpponentInfo:
        return OpponentInfo(
            elixir=round(self.elixir.elixir, 1),
            known_deck=list(self.cycle.known_deck),
            predicted_hand=self.cycle.predicted_hand(),
            out_of_hand=self.cycle.out_of_hand(),
            unknown_slots=self.cycle.unknown_slots,
            flags=dict(self.flags),
        )
