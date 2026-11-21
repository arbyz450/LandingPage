"""Curated knowledge the engine reads from ``knowledge/*.json``.

* counters.json / counters_a.json / counters_b.json  - researched counter matrix
* placements.json                                     - pro placements per card/situation
* strategy.json                                       - principles, archetypes, matchups
* priors.json                                         - learned placement priors (see learn.py)

Everything is optional: with no files present the engine falls back to its
duel model and generic zones.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .learn import PlacementPriors

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = ROOT / "knowledge"


def _load_json(path: Path) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


@dataclass
class Placement:
    card: str
    situation: str
    label: str
    x: float
    y: float
    lane: str = "either"
    vs: Tuple[str, ...] = ()
    condition: str = ""
    note: str = ""

    def mirrored(self) -> "Placement":
        return Placement(self.card, self.situation, self.label + " (right)", 18.0 - self.x, self.y, "right", self.vs, self.condition, self.note)


@dataclass
class Archetype:
    id: str
    signature: Tuple[str, ...]
    gameplan: str = ""
    how_to_beat: str = ""
    beats: Tuple[str, ...] = ()
    loses_to: Tuple[str, ...] = ()


@dataclass
class Knowledge:
    counters: Dict[str, Dict[str, Tuple[float, str]]] = field(default_factory=dict)   # attacker -> {defender: (quality, note)}
    placements: Dict[str, List[Placement]] = field(default_factory=dict)              # card -> placements (left-lane normalised)
    placement_tips: Dict[str, List[str]] = field(default_factory=dict)
    mechanics: List[dict] = field(default_factory=list)
    archetypes: List[Archetype] = field(default_factory=list)
    matchups: Dict[Tuple[str, str], dict] = field(default_factory=dict)
    principles: List[dict] = field(default_factory=list)
    phase_policy: Dict[str, str] = field(default_factory=dict)
    priors: PlacementPriors = field(default_factory=PlacementPriors)
    loaded: List[str] = field(default_factory=list)

    # ----- loading --------------------------------------------------------
    @classmethod
    def load(cls, directory: Optional[Path] = None, valid_keys: Optional[set] = None) -> "Knowledge":
        d = Path(directory) if directory else KNOWLEDGE_DIR
        k = cls()
        ok = (lambda key: True) if valid_keys is None else (lambda key: key in valid_keys)
        for name in ("counters.json", "counters_a.json", "counters_b.json"):
            data = _load_json(d / name)
            if not data:
                continue
            k.loaded.append(name)
            for card, info in data.items():
                if not ok(card):
                    continue
                for e in info.get("countered_by", []):
                    if ok(e.get("card")):
                        k.counters.setdefault(card, {})[e["card"]] = (float(e.get("quality", 0.5)), e.get("note", ""))
                for e in info.get("counters", []):      # card counters X  <=> X countered_by card
                    if ok(e.get("card")):
                        k.counters.setdefault(e["card"], {}).setdefault(card, (float(e.get("quality", 0.5)), e.get("note", "")))
                tips = [t for t in info.get("placement_tips", []) if isinstance(t, str)]
                if tips:
                    k.placement_tips[card] = tips
        data = _load_json(d / "placements.json")
        if data:
            k.loaded.append("placements.json")
            k.mechanics = data.get("mechanics", [])
            for p in data.get("placements", []):
                if not ok(p.get("card")):
                    continue
                try:
                    pl = Placement(p["card"], p.get("situation", "offense"), p.get("label", ""), float(p["x"]), float(p["y"]),
                                   p.get("lane", "either"), tuple(v for v in p.get("vs", []) if ok(v)), p.get("condition", ""), p.get("note", ""))
                except (KeyError, TypeError, ValueError):
                    continue
                if pl.lane == "right":            # normalise to the left lane
                    pl = Placement(pl.card, pl.situation, pl.label, 18.0 - pl.x, pl.y, "either", pl.vs, pl.condition, pl.note)
                k.placements.setdefault(pl.card, []).append(pl)
        data = _load_json(d / "strategy.json")
        if data:
            k.loaded.append("strategy.json")
            k.principles = data.get("principles", [])
            k.phase_policy = data.get("phase_policy", {})
            for a in data.get("archetypes", []):
                k.archetypes.append(Archetype(a.get("id", "?"), tuple(c for c in a.get("signature_cards", []) if ok(c)),
                                              a.get("gameplan", ""), a.get("how_to_beat", ""), tuple(a.get("beats", [])), tuple(a.get("loses_to", []))))
            for m in data.get("matchups", []):
                k.matchups[(m.get("me", ""), m.get("opp", ""))] = m
        pri = d / "priors.json"
        if pri.exists():
            k.priors = PlacementPriors.load(pri)
            k.loaded.append("priors.json")
        return k

    # ----- queries ----------------------------------------------------------
    def curated_counter(self, defender: str, attacker: str) -> Optional[Tuple[float, str]]:
        return self.counters.get(attacker, {}).get(defender)

    def placements_for(self, card: str, situation: Optional[str] = None) -> List[Placement]:
        out = []
        for p in self.placements.get(card, []):
            if situation and p.situation != situation:
                continue
            out.append(p)
            if p.lane in ("either",) and p.x < 8.9:
                out.append(p.mirrored())
        return out

    def detect_archetype(self, deck: List[str]) -> Optional[Archetype]:
        best, best_n = None, 0
        for a in self.archetypes:
            n = sum(1 for c in deck if c in a.signature)
            if n > best_n:
                best, best_n = a, n
        return best if best_n >= 1 else None

    def matchup(self, me: Optional[str], opp: Optional[str]) -> Optional[dict]:
        if not me or not opp:
            return None
        return self.matchups.get((me, opp))


_DEFAULT: Optional[Knowledge] = None


def default_knowledge() -> Knowledge:
    global _DEFAULT
    if _DEFAULT is None:
        from .cards import default_db
        _DEFAULT = Knowledge.load(valid_keys=set(c.key for c in default_db()))
    return _DEFAULT
