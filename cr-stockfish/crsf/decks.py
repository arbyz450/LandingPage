"""Deck pool for simulation: current meta decks plus archetype-templated random decks."""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, List, Optional

from .cards import CardDB, default_db
from .knowledge import KNOWLEDGE_DIR

WIN_CONDITIONS = ["hog_rider", "giant", "golem", "royal_giant", "x_bow", "mortar", "balloon", "lava_hound", "graveyard",
                  "miner", "goblin_barrel", "goblin_drill", "ram_rider", "battle_ram", "wall_breakers", "royal_hogs",
                  "electro_giant", "goblin_giant", "mega_knight", "pekka", "three_musketeers", "elixir_golem", "skeleton_barrel"]
BUILDINGS = ["tesla", "cannon", "inferno_tower", "bomb_tower", "tombstone", "goblin_cage", "furnace"]
BIG_SPELLS = ["fireball", "poison", "rocket", "lightning"]
SMALL_SPELLS = ["log", "zap", "arrows", "giant_snowball", "barbarian_barrel", "earthquake", "tornado", "royal_delivery"]
SUPPORT = ["musketeer", "electro_wizard", "wizard", "baby_dragon", "witch", "night_witch", "valkyrie", "knight", "mini_pekka",
           "dark_prince", "prince", "hunter", "magic_archer", "firecracker", "archers", "mega_minion", "minions", "bandit",
           "lumberjack", "inferno_dragon", "phoenix", "electro_dragon", "executioner", "bowler", "fisherman", "dart_goblin",
           "princess", "goblin_gang", "guards", "skeleton_army", "minion_horde", "zappies", "flying_machine", "mother_witch",
           "ice_wizard", "archer_queen", "golden_knight", "skeleton_king", "mighty_miner", "monk", "little_prince", "bats"]
CYCLE = ["skeletons", "ice_spirit", "fire_spirit", "electro_spirit", "heal_spirit", "bats", "ice_golem", "spear_goblins", "goblins", "skeletons"]


def meta_decks(db: Optional[CardDB] = None) -> List[Dict]:
    db = db or default_db()
    path = KNOWLEDGE_DIR / "meta_decks.json"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    out = []
    for d in data.get("decks", []):
        cards = [c for c in d.get("cards", []) if db.find(c)]
        if len(cards) == 8 and len(set(cards)) == 8:
            out.append({"name": d.get("name", "meta"), "archetype": d.get("archetype", ""), "cards": cards, "source": "meta"})
    return out


def random_deck(rng: random.Random, db: Optional[CardDB] = None) -> Dict:
    db = db or default_db()
    ok = lambda k: db.find(k) is not None
    for _ in range(200):
        cards: List[str] = []
        wc = rng.choice([c for c in WIN_CONDITIONS if ok(c)])
        cards.append(wc)
        if rng.random() < 0.7:
            cards.append(rng.choice([c for c in BUILDINGS if ok(c)]))
        cards.append(rng.choice([c for c in BIG_SPELLS if ok(c)]))
        cards.append(rng.choice([c for c in SMALL_SPELLS if ok(c)]))
        support = [c for c in SUPPORT if ok(c)]
        anti_air = [c for c in support if db.get(c).targets in ("air", "both")]
        cards.append(rng.choice(anti_air))
        while len(cards) < 8:
            pool = support if len(cards) < 6 else [c for c in CYCLE if ok(c)]
            c = rng.choice(pool)
            if c not in cards:
                cards.append(c)
        if len(set(cards)) != 8:
            continue
        avg = sum(db.get(c).cost for c in cards) / 8
        if 2.6 <= avg <= 4.6:
            return {"name": f"{wc}-{int(avg * 10)}", "archetype": "generated", "cards": cards, "source": "generated"}
    raise RuntimeError("could not generate a deck")


def deck_pool(n_random: int = 200, seed: int = 7, db: Optional[CardDB] = None) -> List[Dict]:
    db = db or default_db()
    rng = random.Random(seed)
    pool = meta_decks(db)
    seen = {tuple(sorted(d["cards"])) for d in pool}
    target = len(pool) + n_random
    while len(pool) < target:
        d = random_deck(rng, db)
        key = tuple(sorted(d["cards"]))
        if key in seen:
            continue
        seen.add(key)
        pool.append(d)
    return pool
