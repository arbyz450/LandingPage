"""Large-scale self-play: deck tournaments and weight tuning.

``simulate``: N games between decks drawn from the pool (meta + generated),
both sides driven by the engine, aggregated into deck / archetype / card
win rates and a markdown report.

``tune``: evolutionary search over ``engine.Weights``. Each candidate plays
the same deck pairs (sides swapped) against the current best weights; a
candidate is promoted only if it wins clearly AND still solves at least as
many benchmark puzzles, so tuning cannot buy simulator wins by unlearning
pro fundamentals.
"""
from __future__ import annotations

import json
import math
import os
import random
import time
from collections import defaultdict
from dataclasses import asdict
from multiprocessing import Pool
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .cards import default_db
from .decks import deck_pool
from .engine import Engine, Weights
from .knowledge import KNOWLEDGE_DIR, default_knowledge
from .state import GameState

WEIGHTS_PATH = KNOWLEDGE_DIR / "weights.json"


# ----------------------------------------------------------------------------
# workers (top-level so multiprocessing can pickle them)
# ----------------------------------------------------------------------------

def _play_spec(spec: dict) -> dict:
    from .sim import play_match
    w0 = Weights(**spec["w0"]) if spec.get("w0") else None
    w1 = Weights(**spec["w1"]) if spec.get("w1") else None
    r = play_match(spec["deck0"], spec["deck1"], w0, w1, seed=spec["seed"], scripted=spec.get("scripted"))
    r["i0"], r["i1"] = spec.get("i0"), spec.get("i1")
    r["tag"] = spec.get("tag")
    return r


def _run(specs: Sequence[dict], procs: int, progress: Optional[str] = None) -> List[dict]:
    out: List[dict] = []
    t0 = time.time()
    if procs <= 1:
        for i, s in enumerate(specs):
            out.append(_play_spec(s))
            if progress and (i + 1) % 50 == 0:
                print(f"  {progress}: {i + 1}/{len(specs)} games, {time.time() - t0:.0f}s", flush=True)
        return out
    with Pool(procs) as pool:
        for i, r in enumerate(pool.imap_unordered(_play_spec, specs, chunksize=4)):
            out.append(r)
            if progress and (i + 1) % 200 == 0:
                print(f"  {progress}: {i + 1}/{len(specs)} games, {time.time() - t0:.0f}s", flush=True)
    return out


def bench_score(weights: Optional[Weights], puzzles_path: Path) -> int:
    """How many benchmark puzzles these weights solve (see __main__.cmd_bench)."""
    db = default_db()
    eng = Engine(db, weights)
    with open(puzzles_path, "r", encoding="utf-8") as fh:
        puzzles = json.load(fh)["puzzles"]
    ok = 0
    for pz in puzzles:
        st = GameState.from_dict(pz["state"])
        best = eng.analyse(st, top_n=1).best
        if pz.get("wait"):
            ok += best.move.is_wait
            continue
        if best.move.is_wait or best.move.card not in pz["accept"]:
            continue
        if pz.get("lane") and best.move.lane != pz["lane"]:
            continue
        if pz.get("lane_any") and best.move.lane not in pz["lane_any"]:
            continue
        if pz.get("cls") and best.move.cls != pz["cls"]:
            continue
        if pz.get("not_cls") and best.move.cls in pz["not_cls"]:
            continue
        if pz.get("zone_prefix") and not (best.move.zone or "").startswith(pz["zone_prefix"]):
            continue
        ok += 1
    return ok


# ----------------------------------------------------------------------------
# tuning
# ----------------------------------------------------------------------------

def perturb(w: Weights, rng: random.Random, sigma: float = 0.25) -> Weights:
    d = asdict(w)
    for k, v in d.items():
        if k == "wait_bias":
            d[k] = v + rng.gauss(0, 0.15)
        else:
            d[k] = max(0.02, v * math.exp(rng.gauss(0, sigma)))
    return Weights(**d)


def tune(iters: int = 6, candidates: int = 6, pairs: int = 30, procs: int = 4, seed: int = 1,
         out: Path = WEIGHTS_PATH, puzzles: Optional[Path] = None, log_path: Optional[Path] = None) -> Weights:
    rng = random.Random(seed)
    pool = deck_pool(n_random=120, seed=seed)
    base = Weights.load(out) if out.exists() else Weights()
    puzzles = puzzles or Path(__file__).resolve().parent.parent / "benchmarks" / "puzzles.json"
    base_bench = bench_score(base, puzzles)
    log: List[dict] = []
    print(f"tuning: baseline solves {base_bench} puzzles; {iters} iterations x {candidates} candidates x {pairs} deck pairs (x2 sides)", flush=True)
    for it in range(iters):
        deck_pairs = [(rng.randrange(len(pool)), rng.randrange(len(pool))) for _ in range(pairs)]
        cands = [perturb(base, rng, sigma=0.3 if it < 2 else 0.18) for _ in range(candidates)]
        specs = []
        for ci, cw in enumerate(cands):
            for pi, (a, b) in enumerate(deck_pairs):
                s = 1000 * it + 10 * pi
                specs.append({"deck0": pool[a]["cards"], "deck1": pool[b]["cards"], "w0": asdict(cw), "w1": asdict(base), "seed": s, "tag": (ci, 0)})
                specs.append({"deck0": pool[b]["cards"], "deck1": pool[a]["cards"], "w0": asdict(base), "w1": asdict(cw), "seed": s + 1, "tag": (ci, 1)})
        results = _run(specs, procs, progress=f"iter {it + 1}")
        score: Dict[int, List[float]] = defaultdict(list)
        for r in results:
            ci, cand_side = r["tag"]
            if r["winner"] is None:
                score[ci].append(0.5)
            else:
                score[ci].append(1.0 if r["winner"] == cand_side else 0.0)
        ranked = sorted(((sum(v) / len(v), ci) for ci, v in score.items()), reverse=True)
        wr, ci = ranked[0]
        cand_bench = bench_score(cands[ci], puzzles)
        n = len(score[ci])
        se = math.sqrt(0.25 / n)
        promoted = wr > 0.5 + 1.5 * se and cand_bench >= base_bench
        entry = {"iter": it + 1, "best_candidate_winrate": round(wr, 3), "games": n, "bench": cand_bench, "base_bench": base_bench, "promoted": promoted, "weights": asdict(cands[ci])}
        log.append(entry)
        print(f"  iter {it + 1}: best candidate {wr:.1%} over {n} games, bench {cand_bench}/{base_bench} -> {'PROMOTED' if promoted else 'kept baseline'}", flush=True)
        if promoted:
            base, base_bench = cands[ci], cand_bench
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, "w", encoding="utf-8") as fh:
                json.dump(asdict(base), fh, indent=2)
    if log_path:
        with open(log_path, "w", encoding="utf-8") as fh:
            json.dump({"final": asdict(base), "log": log}, fh, indent=2)
    return base


# ----------------------------------------------------------------------------
# tournament
# ----------------------------------------------------------------------------

def _wilson(wins: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = wins / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - half) / denom, (centre + half) / denom


def simulate(games: int = 10000, n_random: int = 200, procs: int = 4, seed: int = 3, out_dir: Path = Path("reports"),
             weights: Optional[Weights] = None, scripted_share: float = 0.0) -> dict:
    db = default_db()
    k = default_knowledge()
    rng = random.Random(seed)
    pool = deck_pool(n_random=n_random, seed=seed)
    w = weights if weights is not None else (Weights.load(WEIGHTS_PATH) if WEIGHTS_PATH.exists() else Weights())
    wd = asdict(w)
    for d in pool:
        if d["archetype"] in ("", "generated"):
            a = k.detect_archetype(d["cards"])
            d["archetype"] = a.id if a else "other"
    specs = []
    order = list(range(len(pool)))
    for g in range(games):
        if g % len(pool) == 0:
            rng.shuffle(order)
        a = order[g % len(pool)]
        b = rng.randrange(len(pool))
        while b == a:
            b = rng.randrange(len(pool))
        spec = {"deck0": pool[a]["cards"], "deck1": pool[b]["cards"], "w0": wd, "w1": wd, "seed": seed * 100000 + g, "i0": a, "i1": b}
        if scripted_share and rng.random() < scripted_share:
            spec["scripted"] = 1
            spec["tag"] = "scripted"
        specs.append(spec)
    t0 = time.time()
    results = _run(specs, procs, progress="simulate")
    elapsed = time.time() - t0

    deck_stats = [{"w": 0.0, "n": 0, "crowns_for": 0, "crowns_against": 0} for _ in pool]
    card_stats: Dict[str, Dict[str, float]] = defaultdict(lambda: {"w": 0.0, "n": 0})
    arch: Dict[Tuple[str, str], Dict[str, float]] = defaultdict(lambda: {"w": 0.0, "n": 0})
    durations, ot, draws = [], 0, 0
    vs_scripted = {"w": 0.0, "n": 0}
    for r in results:
        i0, i1 = r["i0"], r["i1"]
        if r.get("tag") == "scripted":
            vs_scripted["n"] += 1
            vs_scripted["w"] += 1.0 if r["winner"] == 0 else (0.5 if r["winner"] is None else 0.0)
            continue
        s0 = 1.0 if r["winner"] == 0 else (0.5 if r["winner"] is None else 0.0)
        s1 = 1.0 - s0
        durations.append(r["t"])
        ot += r["overtime"]
        draws += r["winner"] is None
        for i, sc, cf, ca in ((i0, s0, r["crowns"][0], r["crowns"][1]), (i1, s1, r["crowns"][1], r["crowns"][0])):
            deck_stats[i]["w"] += sc
            deck_stats[i]["n"] += 1
            deck_stats[i]["crowns_for"] += cf
            deck_stats[i]["crowns_against"] += ca
            for c in pool[i]["cards"]:
                card_stats[c]["w"] += sc
                card_stats[c]["n"] += 1
        a0, a1 = pool[i0]["archetype"], pool[i1]["archetype"]
        arch[(a0, a1)]["w"] += s0
        arch[(a0, a1)]["n"] += 1
        arch[(a1, a0)]["w"] += s1
        arch[(a1, a0)]["n"] += 1

    decks_out = []
    for i, d in enumerate(pool):
        st = deck_stats[i]
        if st["n"] == 0:
            continue
        lo, hi = _wilson(st["w"], st["n"])
        decks_out.append({"name": d["name"], "archetype": d["archetype"], "source": d["source"], "cards": d["cards"],
                          "games": st["n"], "win_rate": round(st["w"] / st["n"], 3), "ci": [round(lo, 3), round(hi, 3)],
                          "crowns_for": st["crowns_for"], "crowns_against": st["crowns_against"],
                          "avg_elixir": round(sum(db.get(c).cost for c in d["cards"]) / 8, 2)})
    decks_out.sort(key=lambda d: -d["win_rate"])
    cards_out = sorted(({"card": c, "games": int(v["n"]), "win_rate": round(v["w"] / v["n"], 3)} for c, v in card_stats.items() if v["n"] >= 30), key=lambda x: -x["win_rate"])
    archs = sorted({a for a, _ in arch} | {b for _, b in arch})
    matrix = {a: {b: (round(arch[(a, b)]["w"] / arch[(a, b)]["n"], 3) if arch[(a, b)]["n"] else None) for b in archs} for a in archs}
    counts = {a: {b: int(arch[(a, b)]["n"]) for b in archs} for a in archs}
    summary = {
        "games": len(durations), "elapsed_s": round(elapsed, 1), "procs": procs, "decks": len(pool),
        "avg_duration_s": round(sum(durations) / max(1, len(durations)), 1), "overtime_rate": round(ot / max(1, len(durations)), 3),
        "draw_rate": round(draws / max(1, len(durations)), 3), "weights": wd,
        "vs_scripted_winrate": (round(vs_scripted["w"] / vs_scripted["n"], 3) if vs_scripted["n"] else None),
    }
    report = {"summary": summary, "decks": decks_out, "cards": cards_out, "archetype_matrix": matrix, "archetype_counts": counts}
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    with open(out_dir / f"simulation_{stamp}.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    md = render_report(report, db)
    with open(out_dir / "simulation_report.md", "w", encoding="utf-8") as fh:
        fh.write(md)
    print(md)
    return report


def render_report(rep: dict, db) -> str:
    s = rep["summary"]
    L = [f"# Self-play simulation report", "",
         f"{s['games']} engine-vs-engine games over {s['decks']} decks in {s['elapsed_s']}s on {s['procs']} processes. "
         f"Average game {s['avg_duration_s']}s, overtime in {s['overtime_rate']:.0%}, draws {s['draw_rate']:.1%}."
         + (f" Engine beat the scripted mid-ladder bot {s['vs_scripted_winrate']:.0%} of the time." if s.get("vs_scripted_winrate") is not None else ""), "",
         "The simulator is a simplified proxy (see crsf/sim.py). Use these numbers to compare decks and weights against each other, not as ladder predictions.", "",
         "## Best decks", "", "| # | deck | archetype | avg elixir | games | win rate | 95% CI |", "|---|---|---|---|---|---|---|"]
    for i, d in enumerate(rep["decks"][:20], 1):
        names = ", ".join(db.get(c).name if db.find(c) else c for c in d["cards"])
        L.append(f"| {i} | {names} | {d['archetype']} | {d['avg_elixir']} | {d['games']} | {d['win_rate']:.1%} | {d['ci'][0]:.0%}-{d['ci'][1]:.0%} |")
    L += ["", "## Worst decks", ""]
    for d in rep["decks"][-5:]:
        L.append(f"- {', '.join(db.get(c).name if db.find(c) else c for c in d['cards'])} ({d['archetype']}): {d['win_rate']:.1%} over {d['games']}")
    L += ["", "## Cards by win rate (in decks that contained them, >=30 games)", "", "| card | games | win rate |", "|---|---|---|"]
    for c in rep["cards"][:25]:
        L.append(f"| {db.get(c['card']).name if db.find(c['card']) else c['card']} | {c['games']} | {c['win_rate']:.1%} |")
    L += ["", "...", ""]
    for c in rep["cards"][-10:]:
        L.append(f"| {db.get(c['card']).name if db.find(c['card']) else c['card']} | {c['games']} | {c['win_rate']:.1%} |")
    archs = list(rep["archetype_matrix"])
    L += ["", "## Archetype matchup matrix (row's win rate vs column)", "", "| | " + " | ".join(archs) + " |", "|---|" + "---|" * len(archs)]
    for a in archs:
        cells = []
        for b in archs:
            v = rep["archetype_matrix"][a][b]
            n = rep["archetype_counts"][a][b]
            cells.append("-" if v is None else f"{v:.0%} ({n})")
        L.append(f"| {a} | " + " | ".join(cells) + " |")
    L += ["", "## Engine weights used", "", "```json", json.dumps(s["weights"], indent=1), "```", ""]
    return "\n".join(L)
