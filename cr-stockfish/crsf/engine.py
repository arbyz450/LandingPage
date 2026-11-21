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

TOWER_VALUE_PRINCESS = 7.0   # elixir-equivalent of a full princess tower
TOWER_VALUE_KING = 12.0
TOWER_DAMAGE_PER_SEC = 110.0  # princess tower dps at level 11 (approx.)


@dataclass
class Weights:
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


@dataclass
class Move:
    card: Optional[str]              # None => wait
    zone: Optional[str]              # zone key, or "unit:<idx>" / "tower:<name>" for spells
    x: float = 9.0
    y: float = 8.0

    @property
    def is_wait(self) -> bool:
        return self.card is None

    @property
    def lane(self) -> str:
        return lane_of_x(self.x)

    def describe(self, db: CardDB, state: Optional[GameState] = None) -> str:
        if self.is_wait:
            return "Wait (hold elixir)"
        name = db.get(self.card).name
        if self.zone in ZONES:
            return f"{name} -> {ZONES[self.zone].label}"
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


def threat_weight(db: CardDB, u: Unit) -> float:
    """How urgent an enemy unit is: value x how close it is to my towers."""
    c = db.get(u.card)
    if c.targets == "none" and not c.has_role("spawner"):
        base = 0.4
    else:
        base = 1.0
    if u.y >= RIVER_Y:
        prox = 0.35 if u.y < RIVER_Y + 6 else 0.2    # still on their side: a building push
    else:
        prox = 0.7 + 0.8 * (RIVER_Y - u.y) / RIVER_Y   # 0.7 at the river, 1.5 at my king
    if c.is_building:
        prox = 0.5 if c.has_role("siege") and u.y >= RIVER_Y - 1 else 0.3
        if c.has_role("siege"):
            prox = 1.2   # X-Bow / Mortar locked on a tower is an emergency
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
    if not c.can_hit_tower() or c.dps <= 0:
        return 0.0
    n = unit_count(db, u)
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

def generate_moves(db: CardDB, state: GameState) -> List[Move]:
    moves: List[Move] = [Move(None, None)]
    enemies = [(i, u) for i, u in enumerate(state.units) if u.side == "opp"]
    for key in state.playable_hand():
        card = db.find(key)
        if card is None or card.cost > state.my_elixir + 1e-6:
            continue
        if card.is_spell:
            for i, u in enemies:
                moves.append(Move(key, f"unit:{i}", u.x, u.y))
            for tname, (tx, ty) in OPP_TOWER_POS.items():
                tw = state.towers[f"opp_{tname}"]
                if tw.alive and card.targets != "none":
                    moves.append(Move(key, f"tower:{tname}", tx, ty))
            if not enemies and card.targets == "none":
                moves.append(Move(key, "def_center", 9.0, 12.0))
            continue
        for z in ZONES.values():
            if card.kind in z.kinds:
                moves.append(Move(key, z.key, z.x, z.y))
    return moves


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------

class Engine:
    def __init__(self, db: Optional[CardDB] = None, weights: Optional[Weights] = None):
        self.db = db or default_db()
        self.w = weights or Weights()

    # ----- public ---------------------------------------------------------
    def analyse(self, state: GameState, top_n: int = 5) -> Analysis:
        db = self.db
        threats = [(u, threat_weight(db, u)) for u in state.opp_units()]
        threats.sort(key=lambda t: -t[1])
        recs: List[Recommendation] = []
        for mv in generate_moves(db, state):
            score, comps, reasons = self.score_move(state, mv, threats)
            recs.append(Recommendation(mv, score, reasons, comps))
        recs.sort(key=lambda r: -r.score)
        ev, breakdown = self.evaluate_position(state)
        notes = self._notes(state, threats)
        return Analysis(recs[:top_n], ev, breakdown, threats, notes)

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
        for idx, (u, tw) in enumerate(threats):
            if card.is_spell:
                if mv.zone != f"unit:{state.units.index(u)}":
                    # Spell lands elsewhere; only nearby units are hit.
                    dist = math.hypot(u.x - mv.x, u.y - mv.y)
                    if dist > max(1.5, card.range):
                        continue
                cs = counter_score(db, card, u)
                lf = 1.0
            else:
                cs = counter_score(db, card, u)
                lf = _lane_factor(mv.lane, u.lane)
                if mv.zone in BRIDGE_ZONES:
                    lf *= 0.5      # placing at the bridge is not how you defend
                if mv.zone in BACK_ZONES and u.on_my_side and u.y > 6:
                    lf *= 0.4
            gain = cs * lf * elixir_value(db, u)
            defense += gain
            prevented += cs * lf * expected_tower_damage(db, u)
            if gain >= 0.8:
                reasons.append(f"counters {db.get(u.card).name} ({cs:.0%})")
        if card.is_spell and defense == 0 and mv.zone and mv.zone.startswith("unit:"):
            reasons.append("does nothing useful to that unit")
        comps["defense"] = w.defense * defense
        comps["prevented"] = w.tower_damage_prevented * prevented

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
            if best_counter > 0.5 and mv.zone in BRIDGE_ZONES + BACK_ZONES:
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

        if mv.zone in BRIDGE_ZONES:
            lane = mv.lane
            tower = state.towers[f"opp_{lane}"]
            lane_bonus = 1.0 + 0.5 * (1.0 - tower.frac) if tower.alive else 0.6
            if card.is_win_condition or card.has_role("charge"):
                score += card.cost * (0.35 + 0.5 * openness + 0.4 * low_opp) * lane_bonus
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

        if mv.zone in BACK_ZONES:
            slow_push_ok = state.phase == "single" and state.time_left > 75 and state.my_elixir >= 7 and total_threat < 1.0
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

        if mv.zone in KITE_ZONES:
            # Only useful as a defensive placement; no offensive value.
            if total_threat < 1.0:
                score -= 0.3 * card.cost
        if mv.zone in DEF_ZONES and total_threat < 1.0 and card.is_troop:
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
        if endgame and state.my_elixir >= 7:
            score += frac * TOWER_VALUE_PRINCESS * 1.2 + 0.3
            reasons.append("chip damage in the endgame")
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
            cs = counter_score(db, oc, probe)
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
            answers_before = [k for k in remaining + [card.key] if db.find(k) and db.get(k).cost <= state.my_elixir and counter_score(db, db.get(k), probe) >= 0.55]
            answers_after = [k for k in remaining if db.find(k) and db.get(k).cost <= after and counter_score(db, db.get(k), probe) >= 0.55]
            if answers_before and not answers_after:
                pen = 0.5 * oc.cost
                if pen > worst:
                    worst = pen
                    reason = f"you could no longer answer {oc.name}"
        return worst, reason

    def _notes(self, state: GameState, threats) -> List[str]:
        notes = []
        o = state.opp
        if o.predicted_hand:
            notes.append("Opp hand: " + ", ".join(self.db.get(k).name for k in o.predicted_hand))
        if o.out_of_hand:
            notes.append("Opp cycling back: " + ", ".join(self.db.get(k).name for k in o.out_of_hand))
        if o.unknown_slots:
            notes.append(f"{o.unknown_slots} opponent card(s) still unknown")
        notes.append(f"Opp elixir ~{o.elixir:.1f} | you {state.my_elixir:.1f} | {state.phase} elixir")
        return notes
