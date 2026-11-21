"""The engine: move generation, evaluation and ranked recommendations.

Everything is measured in *elixir-equivalents*: a move that scores +2.0 is
expected to be worth about two elixir more than doing nothing. The pipeline
for one analysis is:

1. ``generate_moves``   - every playable card x every sensible placement zone,
                          plus the explicit "wait" move.
2. ``score_move``       - defensive value against current threats, offensive
                          value given the opponent's predicted hand and elixir,
                          elixir management (leaks, reserves, over-commit),
                          and a 1-ply opponent-response penalty.
3. ``analyse``          - sort, attach human-readable reasons, and return the
                          top-N recommendations plus a static position eval.

All weights live in ``Weights`` so they can be tuned without touching logic.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .cards import Card, CardDB, default_db
from .knowledge import Knowledge, default_knowledge
from .state import (MY_TOWER_POS, OPP_TOWER_POS, RIVER_Y, GameState, Tower, Unit, lane_of_x)

# --------------------------------------------------------------------------
# Placement zones (tile coordinates, my half of the arena unless a spell)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Zone:
    key: str
    label: str
    x: float
    y: float
    kinds: Tuple[str, ...]      # which card kinds may use this zone

    @property
    def lane(self) -> str:
        return lane_of_x(self.x)


ZONES: Dict[str, Zone] = {z.key: z for z in [
    Zone("back_left", "behind king tower, left", 6.0, 2.5, ("troop",)),
    Zone("back_right", "behind king tower, right", 12.0, 2.5, ("troop",)),
    Zone("def_left", "left defensive pocket (in front of tower)", 5.0, 10.0, ("troop", "building")),
    Zone("def_right", "right defensive pocket (in front of tower)", 13.0, 10.0, ("troop", "building")),
    Zone("def_center", "center, between the towers", 9.0, 10.5, ("troop", "building")),
    Zone("bridge_left", "left bridge", 3.5, 15.0, ("troop",)),
    Zone("bridge_right", "right bridge", 14.5, 15.0, ("troop",)),
    Zone("kite_left", "left, next to king tower (kite / activate king)", 7.0, 5.0, ("troop",)),
    Zone("kite_right", "right, next to king tower (kite / activate king)", 11.0, 5.0, ("troop",)),
]}

BACK_ZONES = ("back_left", "back_right")
BRIDGE_ZONES = ("bridge_left", "bridge_right")
DEF_ZONES = ("def_left", "def_right", "def_center")
KITE_ZONES = ("kite_left", "kite_right")

DEATH_DAMAGE_CARDS = {"giant_skeleton": 0.35, "goblin_demolisher": 0.5, "ice_golem": 0.7}   # swarm multiplier vs death blasts

TOWER_VALUE_PRINCESS = 7.0   # elixir-equivalent of a full princess tower
TOWER_VALUE_KING = 12.0
TOWER_DAMAGE_PER_SEC = 110.0  # princess tower dps at level 11 (approx.)


@dataclass
class Weights:
    """Scoring weights. ``knowledge/weights.json`` (written by `crsf tune`) overrides the defaults."""

    defense: float = 1.0
    tower_damage_prevented: float = 1.0
    offense: float = 1.0
    support_synergy: float = 0.9
    build_push: float = 0.55
    cycle: float = 0.25
    leak: float = 3.0
    reserve: float = 0.6
    overcommit: float = 1.0
    opp_response: float = 0.8
    spell_cycle: float = 0.15
    wait_bias: float = 0.0

    @classmethod
    def load(cls, path) -> "Weights":
        import json as _json
        with open(path, "r", encoding="utf-8") as fh:
            data = _json.load(fh)
        fields = set(cls.__dataclass_fields__)
        return cls(**{k: float(v) for k, v in data.items() if k in fields})

    @classmethod
    def default(cls) -> "Weights":
        from .knowledge import KNOWLEDGE_DIR
        p = KNOWLEDGE_DIR / "weights.json"
        if p.exists():
            try:
                return cls.load(p)
            except (OSError, ValueError, TypeError):
                pass
        return cls()


@dataclass
class Move:
    card: Optional[str]              # None => wait
    zone: Optional[str]              # zone key, "unit:<idx>" / "tower:<name>" for spells, "kp:<label>" / "pr:<n>" for knowledge/prior placements
    x: float = 9.0
    y: float = 8.0
    label: str = ""                  # human label for knowledge / prior placements
    source: str = "zone"             # zone | knowledge | prior | spell

    @property
    def is_wait(self) -> bool:
        return self.card is None

    @property
    def lane(self) -> str:
        return lane_of_x(self.x)

    @property
    def cls(self) -> str:
        """Coarse placement class: back | def | bridge | kite | spell."""
        if self.zone in BACK_ZONES:
            return "back"
        if self.zone in BRIDGE_ZONES:
            return "bridge"
        if self.zone in KITE_ZONES:
            return "kite"
        if self.zone in DEF_ZONES:
            return "def"
        if self.zone and (self.zone.startswith("unit:") or self.zone.startswith("tower:")):
            return "spell"
        if self.y >= 13.5:
            return "bridge"
        if self.y <= 4.5:
            return "back"
        return "def"

    def describe(self, db: CardDB, state: Optional[GameState] = None) -> str:
        if self.is_wait:
            return "Wait (hold elixir)"
        name = db.get(self.card).name
        if self.zone in ZONES:
            return f"{name} -> {ZONES[self.zone].label}"
        if self.label:
            return f"{name} -> {self.label} ({self.x:.1f}, {self.y:.1f})"
        if self.zone and self.zone.startswith("tower:"):
            return f"{name} on opponent's {self.zone.split(':', 1)[1]} tower"
        if self.zone and self.zone.startswith("unit:") and state is not None:
            idx = int(self.zone.split(":", 1)[1])
            if 0 <= idx < len(state.units):
                u = state.units[idx]
                return f"{name} on enemy {db.get(u.card).name} ({u.lane} lane)"
        return f"{name} at ({self.x:.1f}, {self.y:.1f})"


@dataclass
class Recommendation:
    move: Move
    score: float
    reasons: List[str] = field(default_factory=list)
    components: Dict[str, float] = field(default_factory=dict)

    def text(self, db: CardDB, state: Optional[GameState] = None) -> str:
        return f"{self.move.describe(db, state)}  [{self.score:+.1f}]"


@dataclass
class Analysis:
    recommendations: List[Recommendation]
    eval: float                      # static position eval, + is good for me
    eval_breakdown: Dict[str, float]
    threats: List[Tuple[Unit, float]]   # enemy units with threat weights
    notes: List[str] = field(default_factory=list)
    wait_score: float = 0.0          # score of doing nothing (decisions are relative to this)
    n_candidates: int = 0

    @property
    def margin(self) -> float:
        """How much better the best move is than waiting."""
        return (self.best.score - self.wait_score) if self.best else 0.0

    @property
    def best(self) -> Optional[Recommendation]:
        return self.recommendations[0] if self.recommendations else None


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def unit_count(db: CardDB, u: Unit) -> int:
    return u.count if u.count > 0 else max(1, db.get(u.card).count)


def elixir_value(db: CardDB, u: Unit) -> float:
    """Approximate remaining elixir value of a unit on the field."""
    c = db.get(u.card)
    n = unit_count(db, u)
    frac = u.hp_frac * (n / max(1, c.count)) if c.count > 1 else u.hp_frac
    return max(0.3, c.cost * max(0.1, frac))


def threat_weight(db: CardDB, u: Unit, my_units: Sequence[Unit] = ()) -> float:
    """How urgent an enemy unit is: value x how close it is to my towers (or my push)."""
    c = db.get(u.card)
    if c.targets == "none" and not c.has_role("spawner"):
        base = 0.4
    else:
        base = 1.0
    if u.y >= RIVER_Y:
        # Still on their side: 0.7 at the bridge, falling to 0.2 at their king tower.
        prox = max(0.2, 0.7 - (u.y - RIVER_Y) * 0.0625)
    else:
        prox = 0.7 + 0.8 * (RIVER_Y - u.y) / RIVER_Y   # 0.7 at the river, 1.5 at my king
    if c.is_building:
        prox = 0.5 if c.has_role("siege") and u.y >= RIVER_Y - 1 else 0.3
        if c.has_role("siege"):
            prox = 1.2   # X-Bow / Mortar locked on a tower is an emergency
    # An enemy answering my push on their side threatens my investment.
    for m in my_units:
        if m.lane == u.lane and abs(m.y - u.y) <= 4.0 and c.can_target(db.get(m.card)):
            prox = max(prox, 0.85)
            break
    return base * elixir_value(db, u) * prox


def _effective_dps(att: Card, n_att: int, target: Card, n_target: int, target_hp_each: float) -> float:
    """Total dps ``att`` (x n_att) deals to ``target`` (x n_target).

    Overkill is modelled: a single-target hit can remove at most one unit's
    worth of HP, so a P.E.K.K.A kills one skeleton per swing.
    """
    if not att.can_target(target) or att.hit_speed <= 0:
        return 0.0
    per_hit = att.damage if att.splash else min(att.damage, max(1.0, target_hp_each))
    dps = per_hit / att.hit_speed * n_att
    if att.splash:
        dps *= min(n_target, 6)       # hits the whole swarm at once
    return dps


def _free_hits_time(defender: Card, attacker: Card) -> float:
    """Seconds a longer-ranged defender shoots before a melee attacker arrives."""
    gap = defender.range - attacker.range
    if gap <= 0 or attacker.tiles_per_sec <= 0:
        return 0.0
    return min(4.0, gap / attacker.tiles_per_sec)


def counter_score(db: CardDB, defender: Card, u: Unit) -> float:
    """0..1: how well ``defender`` (freshly placed) handles enemy unit ``u``.

    Combines a time-to-kill duel model with categorical knowledge (splash vs
    swarm, buildings pulling building-targeters, resets, air targeting...).
    """
    att = db.get(u.card)
    n_att = unit_count(db, u)
    hp_att = att.hp * u.hp_frac

    # ---- spells -----------------------------------------------------------
    if defender.is_spell:
        if defender.targets == "none":
            return 0.0
        if att.is_air and defender.targets == "ground":
            return 0.0
        if att.is_building and defender.targets == "ground" and defender.key in ("earthquake",):
            return 0.9
        kill = min(1.0, defender.damage / max(1.0, hp_att)) if hp_att > 0 else 0.0
        if kill >= 1.0:
            return 1.0
        if defender.has_role("reset") and att.key in ("inferno_dragon", "sparky", "inferno_tower"):
            kill = max(kill, 0.7)
        elif defender.has_role("reset") and att.has_role("charge", "win_condition"):
            kill = max(kill, 0.35)
        return 0.9 * kill if kill > 0.5 else 0.5 * kill

    # ---- troops & buildings --------------------------------------------
    if not defender.can_target(att):
        # Can't hurt it. Buildings still pull building-targeters; tanks distract.
        if defender.is_building and att.targets == "buildings":
            return 0.6
        if defender.is_building and att.can_target(defender) and not att.is_air:
            return 0.3
        return 0.0

    n_def = max(1, defender.count)
    d_dps = _effective_dps(defender, n_def, att, n_att, hp_att)
    a_dps = _effective_dps(att, n_att, defender, n_def, defender.hp)

    if d_dps <= 0:
        return 0.0
    ttk_att = (hp_att * (1 if defender.splash else n_att)) / d_dps  # time to kill attacker
    if a_dps <= 0:
        ttk_def = 30.0 if att.targets == "buildings" else 60.0
    else:
        ttk_def = (defender.hp * (1 if att.splash else n_def)) / a_dps
    ttk_def += _free_hits_time(defender, att)
    if defender.is_building:
        ttk_def += 3.0            # buildings pull / soak for a while
    ratio = ttk_def / max(0.3, ttk_att)
    score = ratio / (1.0 + ratio)

    # Categorical adjustments
    if att.key in DEATH_DAMAGE_CARDS and defender.is_swarm:
        score *= DEATH_DAMAGE_CARDS[att.key]      # its death blast erases the swarm
    if att.is_swarm and not defender.splash and defender.count < 3 and defender.hit_speed > 0.8:
        score *= 0.55
    if att.is_swarm and defender.splash:
        score = max(score, 0.85)
    if defender.is_swarm and att.splash:
        score *= 0.35
    if att.is_air and defender.has_role("anti_air"):
        score = max(score, 0.7)
    if defender.has_role("reset") and att.has_role("charge"):
        score = max(score, 0.7)
    if defender.has_role("reset") and att.key in ("inferno_dragon", "sparky", "inferno_tower"):
        score = max(score, 0.8)
    if defender.is_building and att.targets == "buildings":
        score = max(score, 0.7)
    if att.targets == "buildings" and defender.is_troop and not defender.is_swarm and defender.dps > 150:
        score = max(score, 0.65)  # free hits on a building-targeter
    if ttk_att > 12:
        score *= 0.8              # takes forever: tower damage leaks through
    return max(0.0, min(1.0, score))


def expected_tower_damage(db: CardDB, u: Unit) -> float:
    """Elixir-equivalent of damage ``u`` would deal if left alone."""
    c = db.get(u.card)
    if not c.can_hit_tower():
        return 0.0
    n = unit_count(db, u)
    if c.dps <= 0:
        if c.damage > 0 and c.is_troop:        # one-shot units (wall breakers, skeleton barrel)
            return min(1.2 * TOWER_VALUE_PRINCESS, 0.7 * c.damage * n / 3052.0 * TOWER_VALUE_PRINCESS)
        return 0.0
    # Time the unit survives under tower fire while connected.
    survive = (c.hp * u.hp_frac * n) / TOWER_DAMAGE_PER_SEC
    survive = min(survive, 25.0)
    dmg = c.dps * n * survive * (0.6 if c.is_swarm else 1.0)
    return min(1.2 * TOWER_VALUE_PRINCESS, 0.7 * dmg / 3052.0 * TOWER_VALUE_PRINCESS)


def _lane_factor(zone_lane: str, unit_lane: str) -> float:
    if zone_lane == unit_lane:
        return 1.0
    if "center" in (zone_lane, unit_lane):
        return 0.7
    return 0.12


# --------------------------------------------------------------------------
# Move generation
# --------------------------------------------------------------------------

def _situation(state: GameState, lane: str) -> str:
    enemies = state.opp_units()
    if any(u.on_my_side and (u.lane == lane or lane == "center") for u in enemies):
        return "defense"
    if enemies:
        return "counter_push"
    return "offense"


def generate_moves(db: CardDB, state: GameState, knowledge: Optional[Knowledge] = None) -> List[Move]:
    moves: List[Move] = [Move(None, None)]
    enemies = [(i, u) for i, u in enumerate(state.units) if u.side == "opp"]
    pockets_open = {"left": not state.towers["opp_left"].alive, "right": not state.towers["opp_right"].alive}
    for key in state.playable_hand():
        card = db.find(key)
        if card is None or card.cost > state.my_elixir + 1e-6:
            continue
        if card.is_spell:
            for i, u in enemies:
                moves.append(Move(key, f"unit:{i}", u.x, u.y, source="spell"))
            for tname, (tx, ty) in OPP_TOWER_POS.items():
                tw = state.towers[f"opp_{tname}"]
                if tw.alive and card.targets != "none":
                    moves.append(Move(key, f"tower:{tname}", tx, ty, source="spell"))
            if not enemies and card.targets == "none":
                moves.append(Move(key, "def_center", 9.0, 12.0))
            if knowledge:
                for p in knowledge.placements_for(key, "prediction"):
                    moves.append(Move(key, f"kp:{p.label}", p.x, p.y, label=p.label, source="knowledge"))
            continue
        for z in ZONES.values():
            if card.kind in z.kinds:
                moves.append(Move(key, z.key, z.x, z.y))
        if knowledge:
            seen = set()
            for p in knowledge.placements_for(key):
                if p.y > 15.5 and not pockets_open.get(p.lane if p.lane in pockets_open else lane_of_x(p.x), False):
                    continue                        # enemy half: only when that tower is down
                k = (round(p.x * 2), round(p.y * 2))
                if k in seen:
                    continue
                seen.add(k)
                moves.append(Move(key, f"kp:{p.label}", p.x, p.y, label=p.label, source="knowledge"))
            for lane in ("left", "right"):
                for n, c in enumerate(knowledge.priors.candidates(key, _situation(state, lane), lane)):
                    k = (round(c["x"] * 2), round(c["y"] * 2))
                    if k in seen or c["y"] > 15.5:
                        continue
                    seen.add(k)
                    moves.append(Move(key, f"pr:{lane}:{n}", c["x"], c["y"], label=f"learned {lane} placement", source="prior"))
    return moves


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------

class Engine:
    def __init__(self, db: Optional[CardDB] = None, weights: Optional[Weights] = None, knowledge: Optional[Knowledge] = None):
        self.db = db or default_db()
        self.w = weights or Weights.default()
        self.k = knowledge if knowledge is not None else default_knowledge()

    def cs(self, defender: Card, u: Unit) -> float:
        """Counter score with curated knowledge blended over the duel model."""
        model = counter_score(self.db, defender, u)
        cur = self.k.curated_counter(defender.key, u.card)
        score = model if cur is None else 0.35 * model + 0.65 * cur[0]
        if u.card in DEATH_DAMAGE_CARDS and defender.is_swarm and not defender.is_spell:
            score *= DEATH_DAMAGE_CARDS[u.card]      # hard rule: never swarm a death blast
        if u.side == "opp" and self._flag_of(u.card):
            score *= 0.85                             # evolutions / heroes are harder to answer
        return max(0.0, min(1.0, score))

    def _flag_of(self, card: str) -> Optional[str]:
        st = getattr(self, "_state", None)
        return st.opp.flags.get(card) if st is not None else None

    # ----- public ---------------------------------------------------------
    def analyse(self, state: GameState, top_n: int = 5) -> Analysis:
        db = self.db
        self._state = state
        mine = state.my_units()
        threats = [(u, threat_weight(db, u, mine) * (1.2 if state.opp.flags.get(u.card) else 1.0)) for u in state.opp_units()]
        threats.sort(key=lambda t: -t[1])
        recs: List[Recommendation] = []
        base_w = self.w
        self.w = self._matchup_weights(state)
        try:
            for mv in generate_moves(db, state, self.k):
                score, comps, reasons = self.score_move(state, mv, threats)
                recs.append(Recommendation(mv, score, reasons, comps))
        finally:
            self.w = base_w
        recs.sort(key=lambda r: -r.score)
        wait_score = next((r.score for r in recs if r.move.is_wait), 0.0)
        n_cand = len(recs)
        recs = self._dedupe(recs)
        ev, breakdown = self.evaluate_position(state)
        notes = self._notes(state, threats)
        return Analysis(recs[:top_n], ev, breakdown, threats, notes, wait_score=wait_score, n_candidates=n_cand)

    @staticmethod
    def _dedupe(recs: List[Recommendation]) -> List[Recommendation]:
        """Collapse near-identical placements of the same card (keep the best)."""
        out: List[Recommendation] = []
        for r in recs:
            dup = False
            for o in out:
                if o.move.card == r.move.card and abs(o.move.x - r.move.x) < 1.6 and abs(o.move.y - r.move.y) < 2.1 and o.move.cls == r.move.cls:
                    dup = True
                    break
            if not dup:
                out.append(r)
        return out

    def _lowest_tower(self, state: GameState, prefix: str) -> float:
        vals = [state.towers[f"{prefix}_{n}"].hp_or_max for n in ("left", "right") if state.towers[f"{prefix}_{n}"].alive]
        return min(vals) if vals else 0.0

    def _matchup_weights(self, state: GameState) -> Weights:
        """Archetype- and phase-aware weight adjustments."""
        w = Weights(**vars(self.w))
        # Overtime / last seconds: the lowest tower decides the tiebreak.
        if state.overtime or state.time_left <= 20:
            mine, theirs = self._lowest_tower(state, "my"), self._lowest_tower(state, "opp")
            if mine < theirs - 150:
                w.offense *= 1.35          # behind on tiebreak: must deal damage
                w.spell_cycle *= 2.0
                w.wait_bias -= 0.3
            elif mine > theirs + 150:
                w.wait_bias += 0.4         # ahead: defend, don't gamble
                w.tower_damage_prevented *= 1.3
                w.overcommit *= 1.5
        opp_arch = self.k.detect_archetype(state.opp.known_deck)
        if opp_arch is None:
            return w
        if opp_arch.id in ("beatdown", "lavaloon", "golem", "three_musketeers"):
            w.build_push *= 0.6          # don't race a beatdown deck with your own slow push
            w.reserve *= 1.4             # keep the inferno / counters ready
            w.offense *= 1.1             # punish opposite lane when they commit
        elif opp_arch.id in ("cycle", "hog_cycle", "miner_cycle", "mortar_cycle"):
            w.overcommit *= 1.4          # they punish every over-commit
            w.spell_cycle *= 1.3
        elif opp_arch.id in ("siege", "x_bow", "mortar"):
            w.offense *= 1.25            # constant pressure beats siege
            w.wait_bias -= 0.2
        elif opp_arch.id in ("bait", "log_bait", "spell_bait"):
            w.reserve *= 1.3             # hold the log / small spell
        elif opp_arch.id in ("bridge_spam", "pekka_bridge_spam"):
            w.wait_bias += 0.1
            w.tower_damage_prevented *= 1.15
        return w

    def evaluate_position(self, state: GameState) -> Tuple[float, Dict[str, float]]:
        db = self.db

        def towers(prefix: str) -> float:
            v = 0.0
            for name, val in (("left", TOWER_VALUE_PRINCESS), ("right", TOWER_VALUE_PRINCESS), ("king", TOWER_VALUE_KING)):
                t = state.towers[f"{prefix}_{name}"]
                v += val * t.frac if t.alive else 0.0
            return v

        tower_diff = towers("my") - towers("opp")
        elixir_diff = state.my_elixir - state.opp.elixir
        field_diff = sum(elixir_value(db, u) for u in state.my_units()) - sum(elixir_value(db, u) for u in state.opp_units())
        threat_pressure = -sum(expected_tower_damage(db, u) * 0.3 for u in state.opp_units() if u.on_my_side)
        threat_pressure += sum(expected_tower_damage(db, u) * 0.3 for u in state.my_units() if not u.on_my_side)
        total = tower_diff + elixir_diff + 0.8 * field_diff + threat_pressure
        return round(total, 2), {
            "towers": round(tower_diff, 2),
            "elixir": round(elixir_diff, 2),
            "field": round(0.8 * field_diff, 2),
            "pressure": round(threat_pressure, 2),
        }

    # ----- scoring one move ----------------------------------------------
    def score_move(self, state: GameState, mv: Move, threats: Sequence[Tuple[Unit, float]]):
        db, w = self.db, self.w
        comps: Dict[str, float] = {}
        reasons: List[str] = []
        total_threat = sum(t for _, t in threats)

        if mv.is_wait:
            return self._score_wait(state, threats, comps, reasons)

        card = db.get(mv.card)
        after = state.my_elixir - card.cost

        # 1. Defense ----------------------------------------------------------
        defense = 0.0
        prevented = 0.0
        protect = 0.0
        mine = state.my_units()
        # A swarm defender is a liability when a splash unit escorts the push in that lane.
        splash_lanes = {u.lane for u, _ in threats if db.get(u.card).splash and not db.get(u.card).is_building}
        for idx, (u, tw) in enumerate(threats):
            if card.is_spell:
                if mv.zone != f"unit:{state.units.index(u)}":
                    # Spell lands elsewhere; only nearby units are hit.
                    dist = math.hypot(u.x - mv.x, u.y - mv.y)
                    if dist > max(1.5, card.range):
                        continue
                cs = self.cs(card, u)
                lf = 1.0
            else:
                cs = self.cs(card, u)
                lf = _lane_factor(mv.lane, u.lane)
                if mv.lane == "center" and card.is_building and db.get(u.card).targets == "buildings":
                    lf = 1.0       # a centre building pulls building-targeters from either lane
                if mv.source == "knowledge" and self._kp_targets(card.key, mv, u.card):
                    lf = 1.0       # the pro placement was designed for exactly this attacker
                if mv.cls == "bridge":
                    lf *= 0.5      # placing at the bridge is not how you defend
                if mv.cls == "back" and u.on_my_side and u.y > 6:
                    lf *= 0.4
                dy = abs(u.y - mv.y)
                if card.is_building:
                    lf *= 1.0 if (u.on_my_side or db.get(u.card).targets == "buildings") else 0.2
                elif dy > 6:
                    lf *= max(0.25, 1.2 - dy / 16.0)   # the defender has to walk there first
            urgency = min(1.0, tw / max(0.3, elixir_value(db, u)))   # ~proximity: far-away units are not defence yet
            if card.is_swarm and not card.is_spell and u.lane in splash_lanes and not db.get(u.card).splash:
                cs *= 0.4          # the escort's splash will erase the swarm before it works
            gain = cs * lf * elixir_value(db, u) * urgency
            defense += gain
            prevented += cs * lf * expected_tower_damage(db, u) * urgency
            # Protecting my own units: an enemy that is killing my troop is worth stopping.
            for m in mine:
                if m.lane == u.lane and abs(m.y - u.y) <= 3.0 and db.get(u.card).can_target(db.get(m.card)):
                    protect += 0.5 * cs * lf * elixir_value(db, m)
                    break
            if gain >= 0.8:
                reasons.append(f"counters {db.get(u.card).name} ({cs:.0%})")
        if card.is_spell and defense == 0 and mv.zone and mv.zone.startswith("unit:"):
            reasons.append("does nothing useful to that unit")
        comps["defense"] = w.defense * defense
        comps["prevented"] = w.tower_damage_prevented * prevented
        comps["protect"] = w.defense * protect
        if protect >= 0.8:
            reasons.append("protects your troops")

        # 1b. Knowledge / learned placement bonus -------------------------------
        kb, kb_reasons = self._placement_bonus(state, mv, card, threats)
        comps["placement"] = kb
        reasons += kb_reasons

        # 1c. Technique timing: don't drop the counter before the attacker reaches the trigger tile
        tg, tg_reason = self._timing_gate(state, mv, card, threats)
        if tg:
            comps["timing"] = -tg
            reasons.append(tg_reason)

        # 2. Offense ----------------------------------------------------------
        offense, off_reasons = self._offense(state, mv, card, total_threat)
        comps["offense"] = w.offense * offense
        reasons += off_reasons

        # 3. Elixir management ------------------------------------------------
        mgmt = 0.0
        if state.my_elixir >= 9.5:
            mgmt += 0.8          # anything beats leaking
        reserve_pen, reserve_reason = self._reserve_penalty(state, card)
        if reserve_pen:
            mgmt -= w.reserve * reserve_pen
            reasons.append(reserve_reason)
        if after <= 1.0 and state.opp.elixir >= 6 and total_threat < 1.0:
            mgmt -= w.overcommit * 1.0
            reasons.append("leaves you empty while opponent has elixir")
        comps["elixir"] = mgmt

        # 4. Opponent response (1-ply) ---------------------------------------
        resp = 0.0
        if not card.is_spell:
            best_counter, counter_card = self._opp_best_counter(state, card, mv)
            if best_counter > 0.5 and mv.cls in ("bridge", "back"):
                resp = w.opp_response * best_counter * card.cost * 0.5
                reasons.append(f"opponent likely has {db.get(counter_card).name} in hand")
        comps["response"] = -resp

        # 5. Cost -------------------------------------------------------------
        # Defense/offense gains are gross; subtract what we spend, but only the
        # part not "converted" into a unit that stays on the field.
        stays = 0.0 if card.is_spell else 0.45 * card.cost
        comps["cost"] = -(card.cost - stays)
        if total_threat < 1.0 and offense < 0.5 and not card.is_spell:
            comps["cost"] -= 0.2 * card.cost   # pointless play

        total = sum(comps.values())
        if not reasons:
            reasons.append("cycles the hand" if card.cost <= 2 else "neutral play")
        return round(total, 2), comps, reasons

    def _score_wait(self, state: GameState, threats, comps, reasons):
        w = self.w
        total_threat = sum(t for _, t in threats)
        s = w.wait_bias
        if state.my_elixir >= 9.5:
            s -= w.leak
            reasons.append("you are leaking elixir")
        elif state.my_elixir >= 9.0:
            s -= w.leak / 3
            reasons.append("about to leak elixir")
        if total_threat >= 2.0:
            s -= total_threat * 0.6
            reasons.append("there is a threat on your side")
        if state.opp.elixir - state.my_elixir >= 2 and total_threat < 1.0:
            s += 0.4
            reasons.append("opponent is up on elixir, don't start a push now")
        if state.my_elixir < 4 and total_threat < 1.0:
            s += 0.3
            reasons.append("build elixir")
        if state.time_left > 165 and not state.overtime and not state.units and state.my_elixir < 9:
            s += 0.6
            reasons.append("opening: build to 9-10 elixir or cycle a cheap card at the back")
        if not reasons:
            reasons.append("nothing urgent")
        comps["wait"] = s
        return round(s, 2), comps, reasons

    # ----- offense ------------------------------------------------------
    def _offense(self, state: GameState, mv: Move, card: Card, total_threat: float):
        db = self.db
        reasons: List[str] = []
        score = 0.0
        opp_el = state.opp.elixir
        if card.is_spell:
            return self._spell_offense(state, mv, card)
        if card.is_building:
            if not card.has_role("spawner") and total_threat < 1.0:
                # Pre-placing a defensive building is fine when opponent threatens a building-targeter
                for key in state.opp.predicted_hand:
                    oc = db.find(key)
                    if oc and oc.targets == "buildings" and oc.is_win_condition and mv.zone == "def_center":
                        score += 0.35 * card.cost
                        reasons.append(f"pre-places against {oc.name}")
                        break
            if card.has_role("spawner") and mv.zone in DEF_ZONES:
                score += 0.4 * card.cost
                reasons.append("spawner value over time")
            return score, reasons

        opp_counter, counter_card = self._opp_best_counter(state, card, mv)
        openness = 1.0 - opp_counter
        low_opp = max(0.0, (6.0 - opp_el) / 6.0)     # 1.0 when opp has 0, 0 at 6+

        opening = state.time_left > 165 and not state.overtime and not state.units
        if mv.cls == "bridge" and mv.lane != "center":
            lane = mv.lane
            tower = state.towers[f"opp_{lane}"]
            lane_bonus = 1.0 + 0.5 * (1.0 - tower.frac) if tower.alive else 0.6
            other = "right" if lane == "left" else "left"
            committed = [u for u in state.opp_units() if u.lane == other and not u.on_my_side and db.get(u.card).cost >= 5]
            if card.is_win_condition or card.has_role("charge"):
                score += card.cost * (0.35 + 0.5 * openness + 0.4 * low_opp) * lane_bonus
                if opening:
                    score -= 0.6 * card.cost
                    reasons.append("never open with your win condition")
                if committed:
                    score += 0.35 * card.cost
                    reasons.append(f"punish the opposite lane while their {db.get(committed[0].card).name} walks")
                if openness > 0.6:
                    reasons.append("opponent has no good counter in hand")
                if low_opp > 0.4:
                    reasons.append(f"opponent is low on elixir (~{opp_el:.0f})")
                if tower.alive and tower.frac < 0.35:
                    reasons.append(f"{lane} tower is low ({tower.hp_or_max:.0f} HP)")
            elif card.has_role("support", "ranged", "splash", "mini_tank"):
                score += card.cost * (0.1 + 0.25 * openness)
            # Support behind a tank already in that lane
            tank_ahead = [u for u in state.my_units() if u.lane == lane and u.y > mv.y - 4
                          and db.get(u.card).has_role("tank", "win_condition", "mini_tank")]
            if tank_ahead and not card.is_win_condition:
                score += self.w.support_synergy * card.cost * 0.6
                reasons.append(f"supports your {db.get(tank_ahead[0].card).name}")
            # Counter-push: a surviving unit of mine in that lane
            if any(u.lane == lane and u.on_my_side for u in state.my_units()) and card.is_win_condition:
                score += 0.3 * card.cost
                reasons.append("counter-push with your surviving units")

        if mv.cls == "back":
            slow_push_ok = total_threat < 1.0 and (
                (state.phase == "single" and state.time_left > 75 and state.my_elixir >= 7)
                or (state.phase != "single" and state.my_elixir >= 6 and not state.overtime))
            if card.is_tank and card.cost >= 5:
                if slow_push_ok or state.my_elixir >= 9:
                    score += self.w.build_push * card.cost
                    reasons.append("start a slow push from the back")
                else:
                    score -= 0.3 * card.cost
            elif card.has_role("support", "ranged") and not card.is_win_condition:
                tank_ahead = [u for u in state.my_units() if u.lane == mv.lane and db.get(u.card).is_tank]
                if tank_ahead:
                    score += self.w.support_synergy * card.cost * 0.5
                    reasons.append(f"builds behind your {db.get(tank_ahead[0].card).name}")
                elif state.my_elixir >= 8:
                    score += 0.25 * card.cost
                    reasons.append("safe placement to build a push")
            elif card.has_role("cycle") or card.cost <= 2:
                if state.my_elixir >= 7 and total_threat < 1.0:
                    score += self.w.cycle * 2
                    reasons.append("cheap cycle, keeps elixir from capping")
                    wincons = [k for k in state.my_deck if db.find(k) and db.get(k).is_win_condition]
                    if wincons and not any(k in state.hand for k in wincons):
                        score += 0.5
                        reasons.append("cycles toward your win condition")
            elif card.is_win_condition:
                score -= 0.4 * card.cost   # win conditions belong at the bridge

        if mv.cls == "kite":
            # Only useful as a defensive placement; no offensive value.
            if total_threat < 1.0:
                score -= 0.3 * card.cost
        if mv.cls == "def" and total_threat < 1.0 and card.is_troop:
            score -= 0.25 * card.cost
        return score, reasons

    def _spell_offense(self, state: GameState, mv: Move, card: Card):
        reasons: List[str] = []
        score = 0.0
        if not (mv.zone or "").startswith("tower:"):
            return score, reasons
        tname = mv.zone.split(":", 1)[1]
        tower = state.towers[f"opp_{tname}"]
        tower_dmg = card.damage * 0.3 if card.has_role("spell_small", "spell_big") else 0.0
        if card.key in ("rocket", "lightning", "fireball", "poison", "arrows", "void", "royal_delivery"):
            tower_dmg = card.damage * (0.35 if card.key != "rocket" else 0.33)
        if tower_dmg <= 0:
            return -1.0, ["wasted spell"]
        if tower.alive and tower.hp_or_max <= tower_dmg:
            value = TOWER_VALUE_KING if tname == "king" else TOWER_VALUE_PRINCESS
            score += value + 5.0
            reasons.append(f"finishes the {tname.replace('_', ' ')} tower")
            return score, reasons
        frac = tower_dmg / tower.max_hp
        endgame = state.overtime or state.time_left <= 30
        behind = endgame and self._lowest_tower(state, "my") < self._lowest_tower(state, "opp") - 150
        if endgame and state.my_elixir >= 7:
            score += frac * TOWER_VALUE_PRINCESS * 1.5 + 0.3
            reasons.append("chip damage in the endgame")
            if behind:
                score += 0.8 * card.cost
                reasons.append("behind on the tiebreak: tower damage wins the game")
            if state.my_elixir >= 9:
                score += 0.5 * card.cost
        elif state.my_elixir >= 9:
            score += self.w.spell_cycle * card.cost + frac * TOWER_VALUE_PRINCESS
            reasons.append("spell cycle instead of leaking")
        else:
            score += frac * TOWER_VALUE_PRINCESS * 0.5 - 0.3
        return score, reasons

    # ----- opponent model ------------------------------------------------
    def _opp_best_counter(self, state: GameState, card: Card, mv: Move) -> Tuple[float, Optional[str]]:
        """How well the opponent's predicted hand (within their elixir) answers ``card``."""
        db = self.db
        probe = Unit(card.key, "me", mv.x, mv.y)
        best, best_card = 0.0, None
        hand = state.opp.predicted_hand
        unknown = state.opp.unknown_slots
        for key in hand:
            oc = db.find(key)
            if not oc or oc.cost > state.opp.elixir + 0.5:
                continue
            cs = self.cs(oc, probe)
            if cs > best:
                best, best_card = cs, oc.key
        if unknown > 0 and state.opp.elixir >= 3:
            # Unknown cards: assume a generic 50% answer, scaled by how much is unknown.
            generic = 0.45 * min(1.0, unknown / 4)
            if generic > best:
                best, best_card = generic, None
        if best_card is None:
            return best, None
        return best, best_card

    def _reserve_penalty(self, state: GameState, card: Card) -> Tuple[float, str]:
        """Penalise spending if it means we can no longer answer a likely threat."""
        db = self.db
        after = state.my_elixir - card.cost
        worst, reason = 0.0, ""
        remaining = [k for k in state.hand if k and k != card.key]
        for key in state.opp.predicted_hand:
            oc = db.find(key)
            if not oc or not (oc.is_win_condition or oc.cost >= 5):
                continue
            if oc.cost > state.opp.elixir + 1.0:
                continue
            probe = Unit(oc.key, "opp", 3.5, 14.0)
            answers_before = [k for k in remaining + [card.key] if db.find(k) and db.get(k).cost <= state.my_elixir and self.cs(db.get(k), probe) >= 0.55]
            answers_after = [k for k in remaining if db.find(k) and db.get(k).cost <= after and self.cs(db.get(k), probe) >= 0.55]
            if answers_before and not answers_after:
                pen = 0.5 * oc.cost
                if pen > worst:
                    worst = pen
                    reason = f"you could no longer answer {oc.name}"
        return worst, reason

    def _timing_gate(self, state: GameState, mv: Move, card: Card, threats) -> Tuple[float, str]:
        """Penalty for playing a timed counter too early (distance-timed techniques)."""
        if card.is_spell and mv.zone and mv.zone.startswith("tower:"):
            return 0.0, ""
        best_pen, why = 0.0, ""
        for t in self.k.techniques:
            if card.key not in t.cards or t.family not in ("deploy_timing", "kiting_pulling", "king_activation", "spell_timing", "micro"):
                continue
            ty = t.trigger_y
            if ty is None:
                continue
            for u, w in threats:
                if u.card not in t.vs or (u.lane != mv.lane and mv.lane != "center"):
                    continue
                early = u.y - ty          # tiles the attacker still has to travel
                if early > 1.0:
                    pen = min(0.8 * card.cost, 0.25 * card.cost * early)
                    if pen > best_pen:
                        best_pen, why = pen, f"too early: {t.name} wants {self.db.get(u.card).name} at y≈{ty:.0f} (now {u.y:.0f})"
        return best_pen, why

    def _kp(self, card_key: str, mv: Move):
        label = mv.zone.split(":", 1)[1] if mv.zone else ""
        return next((p for p in self.k.placements_for(card_key) if p.label == label), None)

    def _kp_targets(self, card_key: str, mv: Move, attacker: str) -> bool:
        p = self._kp(card_key, mv)
        return bool(p and attacker in p.vs)

    def _placement_bonus(self, state: GameState, mv: Move, card: Card, threats) -> Tuple[float, List[str]]:
        reasons: List[str] = []
        if mv.source == "knowledge":
            pl = self._kp(card.key, mv)
            if pl is None:
                return 0.0, reasons
            sit = _situation(state, mv.lane)
            bonus = 0.0
            if pl.situation == sit or (pl.situation == "counter_push" and sit == "offense") or (pl.situation == "offense" and sit == "counter_push"):
                bonus += 0.12 * card.cost
            elif pl.situation == "prediction":
                bonus += 0.05 * card.cost
            else:
                bonus -= 0.1 * card.cost        # right spot, wrong moment
            if pl.vs:
                hits = [u for u, _ in threats if u.card in pl.vs and (u.lane == mv.lane or mv.lane == "center")]
                if hits:
                    bonus += 0.3 * card.cost
                    reasons.append(f"pro placement vs {self.db.get(hits[0].card).name}: {pl.label}")
                elif card.is_troop or card.is_building:
                    bonus -= 0.05 * card.cost
            if bonus > 0 and not reasons:
                reasons.append(f"pro placement: {pl.label}")
            return bonus, reasons
        if mv.source == "prior":
            lane = mv.zone.split(":")[1]
            n = int(mv.zone.split(":")[2])
            cands = self.k.priors.candidates(card.key, _situation(state, lane), lane)
            strength = cands[n]["strength"] if n < len(cands) else 0.0
            if strength > 0:
                reasons.append("placement learned from pro games")
            return 0.2 * card.cost * strength, reasons
        return 0.0, reasons

    def _notes(self, state: GameState, threats) -> List[str]:
        notes = []
        o = state.opp
        opp_arch = self.k.detect_archetype(o.known_deck) if o.known_deck else None
        my_arch = self.k.detect_archetype(state.my_deck) if state.my_deck else None
        if o.elixir >= 9.5:
            notes.append("Opponent is at 10 elixir: they are leaking. Expect a big play; keep your counters ready.")
        if o.flags:
            notes.append("Opp upgrades: " + ", ".join(f"{f} {self.db.get(c).name}" for c, f in o.flags.items() if self.db.find(c)) + " (counted as harder to answer)")
        if opp_arch:
            notes.append(f"Opp archetype: {opp_arch.id}. {opp_arch.how_to_beat}".strip())
            mu = self.k.matchup(my_arch.id if my_arch else None, opp_arch.id)
            if mu:
                notes.append(f"Matchup plan ({my_arch.id} vs {opp_arch.id}): {mu.get('plan', '')}")
        on_board = [u.card for u in state.opp_units()]
        for t in self.k.techniques_for(state.playable_hand(), on_board, list(o.predicted_hand), limit=2):
            notes.append(f"Technique: {t.name}. {t.do}")
        pol = self.k.phase_policy.get("overtime" if state.overtime else state.phase)
        if pol:
            first = pol.split(". ")[0]
            notes.append(f"{'Overtime' if state.overtime else state.phase.title() + ' elixir'}: {first[:140]}")
        if o.predicted_hand:
            notes.append("Opp hand: " + ", ".join(self.db.get(k).name for k in o.predicted_hand))
        if o.out_of_hand:
            notes.append("Opp cycling back: " + ", ".join(self.db.get(k).name for k in o.out_of_hand))
        if o.unknown_slots:
            notes.append(f"{o.unknown_slots} opponent card(s) still unknown")
        notes.append(f"Opp elixir ~{o.elixir:.1f} | you {state.my_elixir:.1f} | {state.phase} elixir")
        return notes
