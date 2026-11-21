"""Card database.

Stats are tournament-standard (level 11) approximations stored in
``data/cards.json``. Edit that file to tune numbers; nothing here is hard-coded.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

DATA_DIR = Path(__file__).parent / "data"

SPEED_TILES_PER_SEC = {
    "slow": 0.75,
    "medium": 1.0,
    "fast": 1.5,
    "very_fast": 2.0,
    "none": 0.0,
}


@dataclass(frozen=True)
class Card:
    key: str
    name: str
    cost: int
    rarity: str
    kind: str          # troop | spell | building
    transport: str     # ground | air | none
    targets: str       # ground | air | both | buildings | none
    hp: float
    damage: float
    hit_speed: float
    range: float
    speed: str
    count: int
    splash: bool
    roles: tuple = field(default_factory=tuple)
    lifetime: float = 0.0
    notes: str = ""

    # ----- derived helpers -------------------------------------------------
    @property
    def is_spell(self) -> bool:
        return self.kind == "spell"

    @property
    def is_building(self) -> bool:
        return self.kind == "building"

    @property
    def is_troop(self) -> bool:
        return self.kind == "troop"

    @property
    def is_air(self) -> bool:
        return self.transport == "air"

    @property
    def dps(self) -> float:
        """Damage per second of a single unit (0 for spells)."""
        if self.hit_speed <= 0:
            return 0.0
        return self.damage / self.hit_speed

    @property
    def total_hp(self) -> float:
        return self.hp * max(1, self.count)

    @property
    def tiles_per_sec(self) -> float:
        return SPEED_TILES_PER_SEC.get(self.speed, 0.0)

    def has_role(self, *roles: str) -> bool:
        return any(r in self.roles for r in roles)

    @property
    def is_swarm(self) -> bool:
        return self.count >= 3 or "swarm" in self.roles

    @property
    def is_tank(self) -> bool:
        return "tank" in self.roles or self.hp >= 2500

    @property
    def is_win_condition(self) -> bool:
        return "win_condition" in self.roles

    def can_target(self, other: "Card") -> bool:
        """Can this card damage ``other`` (a troop/building on the field)?"""
        if self.targets == "none":
            return False
        if self.targets == "buildings":
            return other.is_building
        if other.is_air:
            return self.targets in ("air", "both")
        return self.targets in ("ground", "both")

    def can_hit_tower(self) -> bool:
        return self.targets in ("ground", "both", "buildings")


def _normalise(name: str) -> str:
    name = name.lower().strip()
    name = name.replace("p.e.k.k.a", "pekka").replace("x-bow", "x_bow")
    name = re.sub(r"[^a-z0-9]+", "_", name).strip("_")
    if name.startswith("the_"):
        name = name[4:]
    return name


class CardDB:
    """In-memory card database with lookup by key or (fuzzy) display name."""

    def __init__(self, cards: Iterable[Card]):
        self._cards: Dict[str, Card] = {c.key: c for c in cards}
        self._by_norm: Dict[str, Card] = {}
        for c in self._cards.values():
            self._by_norm[_normalise(c.name)] = c
            self._by_norm[_normalise(c.key)] = c

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "CardDB":
        path = Path(path) if path else DATA_DIR / "cards.json"
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        cards = []
        for entry in raw["cards"]:
            entry = dict(entry)
            entry["roles"] = tuple(entry.get("roles", ()))
            cards.append(Card(**entry))
        return cls(cards)

    def __len__(self) -> int:
        return len(self._cards)

    def __iter__(self):
        return iter(self._cards.values())

    def __contains__(self, key: str) -> bool:
        return key in self._cards

    def get(self, key: str) -> Card:
        if key in self._cards:
            return self._cards[key]
        norm = _normalise(key)
        if norm in self._by_norm:
            return self._by_norm[norm]
        raise KeyError(f"unknown card: {key!r}")

    def find(self, key: str) -> Optional[Card]:
        try:
            return self.get(key)
        except KeyError:
            return None

    def search(self, text: str, limit: int = 5) -> List[Card]:
        """Prefix / substring search on names, used by the overlay input box."""
        norm = _normalise(text)
        if not norm:
            return []
        starts = [c for c in self._cards.values() if _normalise(c.name).startswith(norm) or c.key.startswith(norm)]
        contains = [c for c in self._cards.values() if norm in _normalise(c.name) and c not in starts]
        return (starts + contains)[:limit]

    def keys(self) -> List[str]:
        return sorted(self._cards)


_DEFAULT: Optional[CardDB] = None


def default_db() -> CardDB:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = CardDB.load()
    return _DEFAULT
