"""A fast, deliberately simplified Clash Royale simulator for self-play.

What it models: two lanes, elixir regeneration by phase, the 8-card cycle,
troop movement and targeting (ground/air/buildings-only), overkill-aware
combat, splash, princess/king towers with range and activation, buildings
with lifetimes, damage spells with radius and the 35% tower factor, freeze
as a stun, regulation + overtime with the lowest-tower tiebreak.

What it does not model: exact pathing and pushback, spawners' spawns,
death-spawns, charge mechanics, champion abilities, evolutions, tornado
pulls, clone/mirror/rage/heal, exact tile geometry. Results are a
*consistent proxy* for comparing engine weights and decks against each
other, not a prediction of real ladder win rates.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .cards import Card, CardDB, default_db
from .engine import Engine, Weights
from .state import GameState, OpponentInfo, Tower, Unit, default_towers, KING_TOWER_HP, PRINCESS_TOWER_HP
from .tracker import CycleTracker, ElixirEstimator

DT = 0.5
REG = 180.0

# ---------------------------------------------------------------------------
# Card mechanics the stat sheet does not capture (approximate, level 11)
# ---------------------------------------------------------------------------

def _sub(key, name, cost, kind, transport, targets, hp, dmg, hs, rng, speed, count=1, splash=False, roles=()):
    return Card(key, name, cost, "common", kind, transport, targets, hp, dmg, hs, rng, speed, count, splash, tuple(roles))


SUBUNITS = {
    "golemite": _sub("golemite", "Golemite", 2, "troop", "ground", "buildings", 1030, 83, 2.5, 1.0, "slow"),
    "lava_pup": _sub("lava_pup", "Lava Pup", 1, "troop", "air", "both", 200, 60, 1.0, 1.6, "fast"),
    "elixir_golemite": _sub("elixir_golemite", "Elixir Golemite", 1, "troop", "ground", "buildings", 700, 100, 1.3, 1.0, "medium"),
    "elixir_blob": _sub("elixir_blob", "Elixir Blob", 1, "troop", "ground", "buildings", 300, 60, 1.3, 1.0, "medium"),
    "royal_recruit_1": _sub("royal_recruit_1", "Royal Recruit", 1, "troop", "ground", "ground", 850, 110, 1.3, 1.6, "medium"),
    "bush_goblin": _sub("bush_goblin", "Bush Goblin", 1, "troop", "ground", "ground", 337, 227, 1.5, 1.0, "very_fast"),
    "phoenix_egg": _sub("phoenix_egg", "Phoenix Egg", 1, "building", "none", "none", 400, 0, 0, 0, "none"),
}

# card -> (spawned key, count, period seconds). Spawner buildings/troops.
SPAWNERS = {
    "goblin_hut": ("spear_goblins", 1, 2.1), "furnace": ("fire_spirit", 1, 5.0), "tombstone": ("skeletons", 1, 3.1),
    "barbarian_hut": ("barbarians", 1, 7.0), "goblin_drill": ("goblins", 1, 3.0), "witch": ("skeletons", 3, 7.0),
    "night_witch": ("bats", 2, 7.0), "goblin_cage": None,
}
# card -> list of (key, count) spawned on death
DEATH_SPAWNS = {
    "golem": [("golemite", 2)], "golemite": [], "lava_hound": [("lava_pup", 6)], "tombstone": [("skeletons", 4)],
    "goblin_giant": [("spear_goblins", 2)], "elixir_golem": [("elixir_golemite", 2)], "elixir_golemite": [("elixir_blob", 2)],
    "skeleton_barrel": [("skeletons", 8)], "goblin_drill": [("goblins", 2)], "battle_ram": [("barbarians", 2)],
    "goblin_cage": [("goblins", 1)], "suspicious_bush": [("bush_goblin", 2)], "phoenix": [("phoenix_egg", 1)], "phoenix_egg": [("phoenix", 1)],
    "goblin_demolisher": [], "giant_skeleton": [],
}
DEATH_DAMAGE = {"giant_skeleton": 720, "ice_golem": 70, "wall_breakers": 0, "goblin_demolisher": 400, "goblin_barrel": 0}
# spells that place units: card -> (unit, count, over seconds)
SPAWN_SPELLS = {"graveyard": ("skeletons", 15, 10.0), "goblin_barrel": ("goblins", 3, 1.0), "royal_delivery": ("royal_recruit_1", 1, 1.0),
                "skeleton_barrel": None}
RAMP_CARDS = {"inferno_tower": 3.0, "inferno_dragon": 3.0, "mighty_miner": 4.0}   # seconds to full damage on one target
CHARGE_CARDS = {"prince": 2.0, "dark_prince": 2.0, "battle_ram": 2.0, "ram_rider": 2.0, "bandit": 2.0, "boss_bandit": 2.0}
COLLECTOR = {"elixir_collector": (8.5, 70.0)}   # one elixir every 8.5s for 70s
# how the engine (which only knows real cards) should see sub-units
ENGINE_ALIAS = {"golemite": "ice_golem", "lava_pup": "bats", "elixir_golemite": "ice_golem", "elixir_blob": "ice_golem",
                "royal_recruit_1": "knight", "bush_goblin": "goblins", "phoenix_egg": "tombstone"}
OT = 120.0
LANE_X = {"left": 3.5, "right": 14.5}
TOWER_RANGE = 7.5
TOWER_DPS = 110.0
KING_DPS = 130.0
TOWER_HIT_RADIUS = 1.5     # a melee unit "reaches" the tower within this + its range
SPELL_TOWER_FACTOR = 0.35


@dataclass
class SUnit:
    card: Card
    side: int                  # 0 or 1
    lane: str                  # side-0 perspective
    y: float                   # side-0 frame: 0 = side-0 king, 32 = side-1 king
    hp: float                  # remaining HP pool
    count: int
    lifetime: float = 0.0      # buildings
    stun: float = 0.0
    uid: int = 0
    spawn_timer: float = 0.0   # spawners
    ramp: float = 0.0          # seconds on current target (inferno)
    last_target: Optional[int] = None
    moved: float = 0.0         # tiles moved since last hit (charge)
    collect_timer: float = 0.0
    deploy_left: float = 1.0   # deploy time before the unit can act
    rage: float = 0.0          # seconds of rage left (+35% speed and attack rate)

    @property
    def per_unit_hp(self) -> float:
        return self.card.hp

    @property
    def alive_count(self) -> int:
        if self.count <= 1:
            return 1 if self.hp > 0 else 0
        return max(0, math.ceil(self.hp / max(1.0, self.card.hp) - 1e-9))

    @property
    def hp_frac(self) -> float:
        return max(0.0, min(1.0, self.hp / max(1.0, self.card.hp * max(1, self.count))))

    def forward(self) -> float:
        return 1.0 if self.side == 0 else -1.0


@dataclass
class SPlayer:
    deck: List[str]
    queue: List[str] = field(default_factory=list)
    elixir: float = 5.0
    towers: Dict[str, float] = field(default_factory=lambda: {"left": PRINCESS_TOWER_HP, "right": PRINCESS_TOWER_HP, "king": KING_TOWER_HP})
    king_active: bool = False
    plays: List[Tuple[float, str, str, float]] = field(default_factory=list)   # (t, card, lane, y)

    def __post_init__(self):
        if not self.queue:
            self.queue = list(self.deck)

    @property
    def hand(self) -> List[str]:
        return self.queue[:4]

    @property
    def next_card(self) -> str:
        return self.queue[4] if len(self.queue) > 4 else ""

    def crowns(self) -> int:
        return sum(1 for v in self.towers.values() if v <= 0)

    def play(self, card: str, cost: float) -> None:
        i = self.queue.index(card)
        self.queue.append(self.queue.pop(i))
        self.elixir -= cost


def tower_y(side: int, which: str) -> float:
    base = {"left": 6.5, "right": 6.5, "king": 2.5}[which]
    return base if side == 0 else 32.0 - base


class Match:
    def __init__(self, deck0: List[str], deck1: List[str], db: Optional[CardDB] = None, seed: int = 0):
        self.db = db or default_db()
        self.rng = random.Random(seed)
        self.p = [SPlayer(list(deck0)), SPlayer(list(deck1))]
        for pl in self.p:
            self.rng.shuffle(pl.queue)
        self.units: List[SUnit] = []
        self.pending_spawns: List[list] = []   # [side, key, remaining, lane, y, over, elapsed, total]
        self.t = 0.0
        self.overtime = False
        self.done = False
        self.winner: Optional[int] = None
        self._uid = 0
        self.log: List[str] = []

    # ----- time / elixir ----------------------------------------------------
    @property
    def time_left(self) -> float:
        return (OT - (self.t - REG)) if self.overtime else (REG - self.t)

    @property
    def multiplier(self) -> int:
        if self.overtime:
            return 3 if self.time_left <= 60 else 2
        return 2 if self.time_left <= 60 else 1

    # ----- deployment --------------------------------------------------------
    def can_deploy(self, side: int, card: Card, lane: str, y_own: float) -> bool:
        """y_own is in the player's own frame (0 = own king)."""
        if card.is_spell:
            return True
        opp = self.p[1 - side]
        limit = 25.0 if opp.towers[self._mirror_lane(side, lane)] <= 0 else 15.5
        return 0.0 <= y_own <= limit

    def _mirror_lane(self, side: int, lane: str) -> str:
        # lane names are stored in the side-0 frame; side 1 sees them mirrored
        if side == 0 or lane == "center":
            return lane
        return "right" if lane == "left" else "left"

    def deploy(self, side: int, key: str, lane_own: str, y_own: float, target: Optional[SUnit] = None) -> bool:
        card = self.db.get(key)
        pl = self.p[side]
        if key not in pl.hand or pl.elixir + 1e-6 < card.cost:
            return False
        lane_own = "left" if lane_own == "center" and self.rng.random() < 0.5 else ("right" if lane_own == "center" else lane_own)
        if not self.can_deploy(side, card, lane_own, y_own):
            return False
        lane0 = self._mirror_lane(side, lane_own)
        y0 = y_own if side == 0 else 32.0 - y_own
        pl.play(key, card.cost)
        pl.plays.append((self.t, key, lane0, y0))
        if card.is_spell:
            self._cast(side, card, lane0, y0)
            sp = SPAWN_SPELLS.get(card.key)
            if sp:
                ukey, n, over = sp
                self.pending_spawns.append([side, ukey, n, lane0, y0, over, 0.0, n])
            return True
        self._spawn_unit(side, card, lane0, y0)
        return True

    def _spawn_unit(self, side: int, card: Card, lane0: str, y0: float, count: Optional[int] = None) -> SUnit:
        self._uid += 1
        n = count if count is not None else max(1, card.count)
        life = card.lifetime or (40.0 if card.is_building else 0.0)
        if card.key in COLLECTOR:
            life = COLLECTOR[card.key][1]
        u = SUnit(card, side, lane0, y0, card.hp * n, n, lifetime=life, uid=self._uid)
        self.units.append(u)
        return u

    def _card(self, key: str) -> Card:
        return SUBUNITS.get(key) or self.db.get(key)

    def _cast(self, side: int, card: Card, lane0: str, y0: float) -> None:
        radius = max(1.5, card.range)
        if card.key == "rage":
            for u in self.units:
                if u.side == side and u.lane == lane0 and abs(u.y - y0) <= radius + 1:
                    u.rage = max(u.rage, card.lifetime or 6.0)
            return
        if card.key == "tornado":
            for u in self.units:
                if u.side != side and u.lane == lane0 and abs(u.y - y0) <= radius + 2.5 and not u.card.is_building:
                    u.y = y0                                  # pulled to the centre
                    u.last_target, u.ramp, u.moved = None, 0.0, 0.0
                    if card.damage > 0:
                        u.hp -= card.damage * (min(u.alive_count, 6) if u.card.count > 1 else 1)
            return
        for u in self.units:
            if u.side == side or u.lane != lane0 or abs(u.y - y0) > radius:
                continue
            if not card.can_target(u.card) and card.targets != "none":
                continue
            if card.damage > 0:
                dmg = card.damage * (1.0 if u.card.count <= 1 else min(u.alive_count, 6) / max(1, u.alive_count))
                u.hp -= card.damage if u.card.count <= 1 else card.damage * min(u.alive_count, 6)
            if card.key in ("freeze",):
                u.stun = max(u.stun, card.lifetime or 4.0)
            if card.key in ("zap", "giant_snowball", "electro_spirit", "lightning") and u.card.key in ("inferno_dragon", "inferno_tower", "sparky"):
                u.stun = max(u.stun, 1.0)
        # tower damage
        opp = self.p[1 - side]
        for which in ("left", "right", "king"):
            if which != "king" and which != lane0:
                continue
            if opp.towers[which] <= 0:
                continue
            ty = tower_y(1 - side, which)
            if abs(ty - y0) <= radius + 0.5 and card.damage > 0:
                opp.towers[which] -= card.damage * SPELL_TOWER_FACTOR
                if which == "king":
                    opp.king_active = True
        self._check_towers()

    # ----- simulation step --------------------------------------------------
    def step(self) -> None:
        if self.done:
            return
        dt = DT
        for pl in self.p:
            pl.elixir = min(10.0, pl.elixir + dt / (2.8 / self.multiplier))
        # spell spawns over time (graveyard, barrel, delivery)
        for ps in list(self.pending_spawns):
            side, key, remaining, lane0, y0, over, elapsed, total = ps
            ps[6] = elapsed + dt
            due = int(round(total * min(1.0, ps[6] / max(dt, over)))) - (total - remaining)
            for _ in range(max(0, due)):
                self._spawn_unit(side, self._card(key), lane0, y0 + self.rng.uniform(-1.0, 1.0), count=1)
                ps[2] -= 1
            if ps[2] <= 0:
                self.pending_spawns.remove(ps)
        # units act
        for u in list(self.units):
            if u.hp <= 0:
                continue
            if u.deploy_left > 0:                       # still spawning in
                u.deploy_left -= dt
                continue
            if u.rage > 0:
                u.rage -= dt
            if u.stun > 0:
                u.stun -= dt
                u.ramp = 0.0
                continue
            if u.card.is_building or u.card.key in SPAWNERS:
                if u.card.is_building:
                    u.lifetime -= dt
                    if u.lifetime <= 0:
                        u.hp = 0
                        continue
                sp = SPAWNERS.get(u.card.key)
                if sp:
                    u.spawn_timer += dt
                    if u.spawn_timer >= sp[2]:
                        u.spawn_timer = 0.0
                        self._spawn_unit(u.side, self._card(sp[0]), u.lane, u.y + u.forward() * 0.5, count=sp[1])
                if u.card.key in COLLECTOR:
                    u.collect_timer += dt
                    if u.collect_timer >= COLLECTOR[u.card.key][0]:
                        u.collect_timer = 0.0
                        self.p[u.side].elixir = min(10.0, self.p[u.side].elixir + 1.0)
                    continue
            target = self._pick_target(u)
            if target is not None:
                kind, obj = target
                tid = obj.uid if kind == "unit" else -1
                if tid != u.last_target:
                    u.ramp = 0.0
                    u.last_target = tid
                u.ramp += dt
                if kind == "unit":
                    self._hit_unit(u, obj, dt)
                else:
                    self._hit_tower(u, obj, dt)
                u.moved = 0.0
            elif not u.card.is_building and u.card.tiles_per_sec > 0:
                step_len = u.card.tiles_per_sec * dt * (1.35 if u.rage > 0 else 1.0)
                u.y += u.forward() * step_len
                u.y = max(0.5, min(31.5, u.y))
                u.moved += step_len
                u.ramp = 0.0
        # towers act
        for side in (0, 1):
            self._tower_fire(side, dt)
        dead = [u for u in self.units if u.hp <= 0]
        self.units = [u for u in self.units if u.hp > 0]
        for u in dead:
            self._on_death(u)
        self._check_towers()
        self.t += dt
        if not self.done:
            self._check_clock()

    def _pick_target(self, u: SUnit):
        c = u.card
        enemy = 1 - u.side
        best, best_d = None, 1e9
        if c.targets != "buildings" and c.targets != "none":
            for v in self.units:
                if v.side != enemy or v.lane != u.lane or v.hp <= 0:
                    continue
                if not c.can_target(v.card):
                    continue
                d = abs(v.y - u.y)
                if d <= c.range + 0.7 and d < best_d:
                    best, best_d = v, d
        if best is not None:
            return ("unit", best)
        if c.targets in ("buildings", "ground", "both"):
            # enemy buildings in lane (pull) then towers
            for v in self.units:
                if v.side == enemy and v.lane == u.lane and v.card.is_building and v.hp > 0 and abs(v.y - u.y) <= c.range + 0.7:
                    return ("unit", v)
            opp = self.p[enemy]
            which = u.lane if opp.towers[u.lane] > 0 else "king"
            if opp.towers[which] <= 0:
                return None
            ty = tower_y(enemy, which)
            if abs(ty - u.y) <= c.range + TOWER_HIT_RADIUS:
                return ("tower", which)
        if c.targets == "none":
            return None
        return None

    def _dmg_mult(self, u: SUnit) -> float:
        m = 1.35 if u.rage > 0 else 1.0
        if u.card.key in RAMP_CARDS:
            m = 0.15 + 0.85 * min(1.0, u.ramp / RAMP_CARDS[u.card.key])
        if u.card.key in CHARGE_CARDS and u.moved >= 3.0 and u.ramp <= DT + 1e-6:
            m *= CHARGE_CARDS[u.card.key]              # charged first hit
        return m

    def _on_death(self, u: SUnit) -> None:
        for key, n in DEATH_SPAWNS.get(u.card.key, []):
            c = self._card(key)
            self._spawn_unit(u.side, c, u.lane, u.y, count=n * max(1, c.count))   # one group of n units
        dmg = DEATH_DAMAGE.get(u.card.key, 0)
        if dmg:
            for v in self.units:
                if v.side != u.side and v.lane == u.lane and abs(v.y - u.y) <= 2.5 and v.hp > 0:
                    v.hp -= dmg * (min(v.alive_count, 6) if v.card.count > 1 else 1)

    def _hit_unit(self, u: SUnit, v: SUnit, dt: float) -> None:
        n_u = u.alive_count
        per_hit = u.card.damage if u.card.splash else min(u.card.damage, v.card.hp)
        dps = per_hit / max(0.1, u.card.hit_speed) * n_u * self._dmg_mult(u)
        if u.card.splash:
            dps *= min(v.alive_count, 6)
        v.hp -= dps * dt

    def _hit_tower(self, u: SUnit, which: str, dt: float) -> None:
        opp = self.p[1 - u.side]
        if u.card.hit_speed <= 0 and u.card.damage > 0:      # one-shot units
            opp.towers[which] -= u.card.damage * u.alive_count
            u.hp = 0
        else:
            opp.towers[which] -= u.card.dps * u.alive_count * dt * self._dmg_mult(u)
        if which == "king":
            opp.king_active = True

    def _tower_fire(self, side: int, dt: float) -> None:
        pl = self.p[side]
        enemy = 1 - side
        for which in ("left", "right", "king"):
            if pl.towers[which] <= 0:
                continue
            if which == "king" and not pl.king_active:
                continue
            ty = tower_y(side, which)
            rng = TOWER_RANGE if which != "king" else 7.0
            cands = [v for v in self.units if v.side == enemy and v.hp > 0 and abs(v.y - ty) <= rng
                     and (which == "king" or v.lane == which or pl.towers[v.lane] <= 0)]
            if not cands:
                continue
            v = min(cands, key=lambda v: abs(v.y - ty))
            dps = TOWER_DPS if which != "king" else KING_DPS
            v.hp -= min(dps * dt, dps * dt if v.card.count <= 1 else dps * dt)   # single target

    def _check_towers(self) -> None:
        for side, pl in enumerate(self.p):
            for which in ("left", "right"):
                if pl.towers[which] <= 0:
                    pl.towers[which] = 0.0
                    pl.king_active = True
            if pl.towers["king"] <= 0:
                pl.towers["king"] = 0.0
                self.done, self.winner = True, 1 - side
        if self.done:
            return
        if self.overtime and (self.p[0].crowns() != self.p[1].crowns()):
            self.done = True
            self.winner = 0 if self.p[0].crowns() < self.p[1].crowns() else 1

    def _check_clock(self) -> None:
        if not self.overtime and self.t >= REG:
            c0, c1 = self.p[0].crowns(), self.p[1].crowns()
            if c0 != c1:
                self.done, self.winner = True, (0 if c1 > c0 else 1)   # fewer towers lost wins
            else:
                self.overtime = True
        elif self.overtime and self.t >= REG + OT:
            self.done = True
            lo0 = min(v for v in self.p[0].towers.values() if v > 0)
            lo1 = min(v for v in self.p[1].towers.values() if v > 0)
            self.winner = None if abs(lo0 - lo1) < 1 else (0 if lo0 > lo1 else 1)

    # ----- view for the engine ---------------------------------------------
    def state_for(self, side: int, opp_cycle: CycleTracker, opp_elixir: ElixirEstimator) -> GameState:
        me, opp = self.p[side], self.p[1 - side]
        st = GameState()
        st.time_left = self.time_left
        st.overtime = self.overtime
        st.my_elixir = me.elixir
        st.hand = list(me.hand)
        st.next_card = me.next_card
        st.my_deck = list(me.deck)
        towers = default_towers()
        for which in ("left", "right", "king"):
            my_w = which if side == 0 else ("right" if which == "left" else "left" if which == "right" else "king")
            towers[f"my_{my_w}"] = Tower(hp=me.towers[which] or None, max_hp=KING_TOWER_HP if which == "king" else PRINCESS_TOWER_HP, alive=me.towers[which] > 0)
            towers[f"opp_{my_w}"] = Tower(hp=opp.towers[which] or None, max_hp=KING_TOWER_HP if which == "king" else PRINCESS_TOWER_HP, alive=opp.towers[which] > 0)
        st.towers = towers
        units = []
        for u in self.units:
            if u.hp <= 0:
                continue
            lane_own = self._mirror_lane(side, u.lane)
            x = LANE_X[lane_own]
            y = u.y if side == 0 else 32.0 - u.y
            units.append(Unit(ENGINE_ALIAS.get(u.card.key, u.card.key), "me" if u.side == side else "opp", x, y, u.hp_frac, u.alive_count, id=str(u.uid)))
        st.units = units
        st.opp = OpponentInfo(elixir=round(opp_elixir.elixir, 1), known_deck=list(opp_cycle.known_deck),
                              predicted_hand=opp_cycle.predicted_hand(), out_of_hand=opp_cycle.out_of_hand(),
                              unknown_slots=opp_cycle.unknown_slots)
        return st


# --------------------------------------------------------------------------
# Players
# --------------------------------------------------------------------------

# Player styles: engine weight multipliers + decision thresholds. "pro" is the
# tuned engine as shipped; the others are caricatures of common human styles.
STYLES: Dict[str, dict] = {
    "pro":        {"mult": {}, "min_score": 0.4, "min_margin": 1.0, "interval": 1.0},
    "aggressive": {"mult": {"offense": 1.4, "build_push": 1.3, "reserve": 0.5, "overcommit": 0.4, "wait_bias": -0.6}, "min_score": 0.2, "min_margin": 0.5, "interval": 1.0},
    "defensive":  {"mult": {"offense": 0.7, "reserve": 1.6, "overcommit": 1.6, "tower_damage_prevented": 1.3, "wait_bias": 0.4}, "min_score": 0.6, "min_margin": 1.6, "interval": 1.0},
    "slow":       {"mult": {}, "min_score": 0.4, "min_margin": 1.0, "interval": 2.5},     # human-like reaction time
    "spammer":    None,       # plays any affordable card at the bridge as soon as possible
    "midladder":  None,       # ScriptedPlayer
}


def style_weights(base: Weights, style: str) -> Weights:
    spec = STYLES.get(style) or {}
    w = Weights(**vars(base))
    for k, m in spec.get("mult", {}).items():
        if k == "wait_bias":
            w.wait_bias = w.wait_bias + m
        else:
            setattr(w, k, getattr(w, k) * m)
    return w


class EnginePlayer:
    def __init__(self, side: int, engine: Engine, min_score: float = 0.4, interval: float = 1.0, min_margin: float = 1.0):
        self.side = side
        self.engine = engine
        self.min_score = min_score
        self.min_margin = min_margin
        self.interval = interval
        self.opp_cycle = CycleTracker()
        self.opp_elixir = ElixirEstimator()
        self._seen_plays = 0
        self._next_t = 0.0

    def observe(self, m: Match) -> None:
        opp = m.p[1 - self.side]
        while self._seen_plays < len(opp.plays):
            t, key, _, _ = opp.plays[self._seen_plays]
            self.opp_cycle.record_play(key, t)
            self.opp_elixir.spend(m.db.get(key).cost)
            self._seen_plays += 1
        self.opp_elixir.tick(m.t, 2.8 / m.multiplier)

    def act(self, m: Match) -> None:
        self.observe(m)
        if m.t < self._next_t:
            return
        self._next_t = m.t + self.interval
        st = m.state_for(self.side, self.opp_cycle, self.opp_elixir)
        an = self.engine.analyse(st, top_n=1)
        best = an.best
        if best is None or best.move.is_wait:
            return
        if best.score < self.min_score and (best.score - an.wait_score) < self.min_margin:
            return
        mv = best.move
        lane = mv.lane if mv.lane != "center" else ("left" if mv.x <= 9 else "right")
        m.deploy(self.side, mv.card, lane, mv.y)


class ScriptedPlayer:
    """A mid-ladder style bot: defends what it can see, otherwise pushes when rich."""

    def __init__(self, side: int, db: CardDB, rng: random.Random, interval: float = 1.0):
        self.side = side
        self.db = db
        self.rng = rng
        self.interval = interval
        self._next_t = 0.0

    def act(self, m: Match) -> None:
        if m.t < self._next_t:
            return
        self._next_t = m.t + self.interval
        pl = m.p[self.side]
        own_units = [(u, (u.y if self.side == 0 else 32 - u.y)) for u in m.units if u.side != self.side]
        threats = [(u, y) for u, y in own_units if y < 16]
        hand = [self.db.get(k) for k in pl.hand if self.db.get(k).cost <= pl.elixir]
        if threats:
            u, y = min(threats, key=lambda t: t[1])
            lane = m._mirror_lane(self.side, u.lane)
            answers = [c for c in hand if (c.is_spell and c.damage >= u.card.hp * 0.9) or (not c.is_spell and c.can_target(u.card))]
            if answers:
                c = self.rng.choice(answers)
                m.deploy(self.side, c.key, lane, min(14.0, max(6.0, y - 1)) if not c.is_spell else y)
            return
        if pl.elixir >= 8 and hand:
            c = self.rng.choice(hand)
            lane = self.rng.choice(["left", "right"])
            y = 15.0 if (c.is_win_condition or c.has_role("charge")) else 3.0
            if c.is_spell:
                return
            m.deploy(self.side, c.key, lane, y)


class SpammerPlayer:
    """Plays the first affordable card at the bridge the moment it can (the classic ladder spammer)."""

    def __init__(self, side: int, db: CardDB, rng: random.Random, interval: float = 0.5):
        self.side = side
        self.db = db
        self.rng = rng
        self.interval = interval
        self._next_t = 0.0

    def act(self, m: Match) -> None:
        if m.t < self._next_t:
            return
        self._next_t = m.t + self.interval
        pl = m.p[self.side]
        hand = [self.db.get(k) for k in pl.hand if self.db.get(k).cost <= pl.elixir]
        if not hand:
            return
        c = self.rng.choice(hand)
        lane = self.rng.choice(["left", "right"])
        if c.is_spell:
            m.deploy(self.side, c.key, lane, 25.5)       # spells straight at the tower
        else:
            m.deploy(self.side, c.key, lane, 15.0)


def make_player(side: int, style: str, db: CardDB, rng: random.Random, base_w: Optional[Weights], knowledge):
    if style == "midladder":
        return ScriptedPlayer(side, db, rng)
    if style == "spammer":
        return SpammerPlayer(side, db, rng)
    spec = STYLES.get(style) or STYLES["pro"]
    w = style_weights(base_w or Weights.default(), style)
    return EnginePlayer(side, Engine(db, w, knowledge), min_score=spec["min_score"], interval=spec["interval"], min_margin=spec["min_margin"])


def play_match_players(deck0: List[str], deck1: List[str], p0: dict, p1: dict, seed: int = 0,
                       db: Optional[CardDB] = None, knowledge=None) -> dict:
    """Like ``play_match`` but each side is described by a player spec:
    {"style": "pro|aggressive|defensive|slow|spammer|midladder", "weights": dict|None,
     "min_score": float|None, "min_margin": float|None, "interval": float|None}.
    """
    db = db or default_db()
    from .knowledge import default_knowledge
    k = knowledge if knowledge is not None else default_knowledge()
    m = Match(deck0, deck1, db, seed)
    rng = random.Random(seed + 1)
    players = []
    for side, p in ((0, p0), (1, p1)):
        style = p.get("style", "pro")
        w = Weights(**p["weights"]) if p.get("weights") else None
        pl = make_player(side, style, db, rng, w, k)
        if isinstance(pl, EnginePlayer):
            if p.get("min_score") is not None:
                pl.min_score = float(p["min_score"])
            if p.get("min_margin") is not None:
                pl.min_margin = float(p["min_margin"])
            if p.get("interval") is not None:
                pl.interval = float(p["interval"])
        players.append(pl)
    steps = 0
    while not m.done and steps < int((REG + OT) / DT) + 4:
        for pl in players:
            pl.act(m)
        m.step()
        steps += 1
    return {
        "winner": m.winner, "t": round(m.t, 1), "overtime": m.overtime,
        "crowns": [m.p[1].crowns(), m.p[0].crowns()],
        "towers": [dict(m.p[0].towers), dict(m.p[1].towers)],
        "plays": [len(m.p[0].plays), len(m.p[1].plays)],
    }


def play_match(deck0: List[str], deck1: List[str], w0: Optional[Weights] = None, w1: Optional[Weights] = None,
               seed: int = 0, db: Optional[CardDB] = None, scripted: Optional[int] = None, knowledge=None,
               style0: str = "pro", style1: str = "pro") -> dict:
    db = db or default_db()
    m = Match(deck0, deck1, db, seed)
    rng = random.Random(seed + 1)
    from .knowledge import default_knowledge
    k = knowledge if knowledge is not None else default_knowledge()
    players = []
    for side, w, style in ((0, w0, style0), (1, w1, style1)):
        if scripted == side:
            players.append(ScriptedPlayer(side, db, rng))
        elif style != "pro" or w is None:
            players.append(make_player(side, style, db, rng, w, k))
        else:
            players.append(EnginePlayer(side, Engine(db, w, k)))
    steps = 0
    while not m.done and steps < int((REG + OT) / DT) + 4:
        for p in players:
            p.act(m)
        m.step()
        steps += 1
    return {
        "winner": m.winner, "t": round(m.t, 1), "overtime": m.overtime,
        "crowns": [m.p[1].crowns(), m.p[0].crowns()],      # crowns taken BY side 0, BY side 1
        "towers": [dict(m.p[0].towers), dict(m.p[1].towers)],
        "plays": [len(m.p[0].plays), len(m.p[1].plays)],
    }
