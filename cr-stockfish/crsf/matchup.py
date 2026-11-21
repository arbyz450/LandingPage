"""Deck-vs-deck matchup planning: how to counter any deck with any deck.

Given both decks, assign your best answer to each of their cards, find the
threats you cannot answer cleanly (and the mitigation), find the cards of
yours they cannot answer (your win paths), name both archetypes, pull the
matchup plan from the strategy knowledge, and derive reserve rules the live
advisor shows during the match.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .cards import CardDB, default_db
from .engine import Engine
from .knowledge import Knowledge, default_knowledge
from .state import Unit


@dataclass
class Answer:
    threat: str
    answers: List[Tuple[str, float]]      # (my card, quality) best first

    @property
    def best(self) -> Tuple[Optional[str], float]:
        return self.answers[0] if self.answers else (None, 0.0)


@dataclass
class MatchupPlan:
    my_deck: List[str]
    opp_deck: List[str]
    my_archetype: Optional[str]
    opp_archetype: Optional[str]
    answers: List[Answer]                 # one per opponent card
    their_answers: List[Answer]           # one per my card (their best answer to it)
    danger: List[Answer]                  # their cards my best answer < 0.5
    win_paths: List[Answer]               # my cards their best answer < 0.5
    spell_targets: List[Tuple[str, str]]  # (my spell, their card it kills for value)
    reserve_rules: List[str]
    plan_text: str
    coverage: float                       # mean best-answer quality vs their deck
    exposure: float                       # mean of their best answers vs my deck
    mechanics: List[str] = field(default_factory=list)   # champion abilities / special mechanics in their deck

    def summary_lines(self, db: CardDB, n: int = 3) -> List[str]:
        lines = []
        for a in self.danger[:n]:
            best, q = a.best
            lines.append(f"Danger: {db.get(a.threat).name} (best answer {db.get(best).name if best else 'none'} {q:.0%})")
        for a in self.win_paths[:n]:
            lines.append(f"Win path: {db.get(a.threat).name} (their best answer only {a.best[1]:.0%})")
        return lines

    def render(self, db: CardDB) -> str:
        L = [f"MATCHUP  {self.my_archetype or '?'} vs {self.opp_archetype or '?'}   coverage {self.coverage:.0%} / exposure {self.exposure:.0%}", ""]
        L.append("Their card            your answers")
        for a in self.answers:
            ans = ", ".join(f"{db.get(c).name} {q:.0%}" for c, q in a.answers[:3]) or "none"
            flag = "  <-- DANGER" if a.best[1] < 0.5 else ""
            L.append(f"  {db.get(a.threat).name:<20} {ans}{flag}")
        L += ["", "Your card             their best answer"]
        for a in self.their_answers:
            best, q = a.best
            flag = "  <-- WIN PATH" if q < 0.5 else ""
            L.append(f"  {db.get(a.threat).name:<20} {db.get(best).name + ' ' if best else 'none '}{q:.0%}{flag}")
        if self.spell_targets:
            L += ["", "Spell value: " + "; ".join(f"{db.get(s).name} on {db.get(t).name}" for s, t in self.spell_targets)]
        if self.reserve_rules:
            L += ["", "Reserve rules:"] + [f"  - {r}" for r in self.reserve_rules]
        if self.plan_text:
            L += ["", "Plan: " + self.plan_text]
        if self.mechanics:
            L += ["", "Their mechanics to respect:"] + [f"  - {m}" for m in self.mechanics]
        return "\n".join(L)


def plan_matchup(my_deck: List[str], opp_deck: List[str], db: Optional[CardDB] = None, k: Optional[Knowledge] = None,
                 flags: Optional[Dict[str, str]] = None) -> MatchupPlan:
    db = db or default_db()
    k = k if k is not None else default_knowledge()
    eng = Engine(db, knowledge=k)
    my = [db.get(c).key for c in my_deck]
    opp = [db.get(c).key for c in opp_deck]

    def answers_for(threat: str, pool: List[str]) -> Answer:
        tc = db.get(threat)
        probe = Unit(threat, "opp", 3.5, 12.0)
        out = []
        for c in pool:
            cc = db.get(c)
            if tc.is_spell:
                continue
            q = eng.cs(cc, probe)
            # cheaper answers are better answers
            q *= 1.0 if cc.cost <= tc.cost else max(0.6, 1.0 - 0.1 * (cc.cost - tc.cost))
            out.append((c, round(q, 2)))
        out.sort(key=lambda x: -x[1])
        return Answer(threat, out)

    answers = [answers_for(t, my) for t in opp if not db.get(t).is_spell]
    their = [answers_for(t, opp) for t in my if not db.get(t).is_spell]
    danger = sorted([a for a in answers if a.best[1] < 0.5 and db.get(a.threat).cost >= 3], key=lambda a: a.best[1])
    win_paths = sorted([a for a in their if a.best[1] < 0.5 and (db.get(a.threat).is_win_condition or db.get(a.threat).cost >= 4)], key=lambda a: a.best[1])
    spell_targets = []
    for s in my:
        sc = db.get(s)
        if not sc.is_spell or sc.damage <= 0:
            continue
        for t in opp:
            tc = db.get(t)
            if tc.is_spell or tc.is_building:
                continue
            if sc.damage >= tc.hp and tc.cost >= sc.cost - 1 and sc.can_target(tc):
                spell_targets.append((s, t))
    my_arch = k.detect_archetype(my)
    opp_arch = k.detect_archetype(opp)
    mu = k.matchup(my_arch.id if my_arch else None, opp_arch.id if opp_arch else None)
    plan_text = mu.get("plan", "") if mu else (opp_arch.how_to_beat if opp_arch else "")
    reserve = []
    for a in answers:
        tc = db.get(a.threat)
        best, q = a.best
        if best and (tc.is_win_condition or tc.cost >= 5) and q >= 0.5:
            reserve.append(f"Keep {db.get(best).name} (and {db.get(best).cost} elixir) available while {tc.name} is in their hand")
    for a in danger[:2]:
        tc = db.get(a.threat)
        best, q = a.best
        mitig = f"stack {db.get(best).name} with your tower and spell" if best else "out-pressure the other lane instead"
        reserve.append(f"No clean answer to {tc.name}: {mitig}; never let it connect with a tank in front")
    coverage = sum(a.best[1] for a in answers) / max(1, len(answers))
    exposure = sum(a.best[1] for a in their) / max(1, len(their))
    mech = []
    for c in opp:
        for line in k.card_mechanics(c, (flags or {}).get(c))[:1]:
            mech.append(f"{db.get(c).name}: {line[:140]}")
    return MatchupPlan(my, opp, my_arch.id if my_arch else None, opp_arch.id if opp_arch else None, answers, their,
                       danger, win_paths, spell_targets, reserve[:6], plan_text, round(coverage, 3), round(exposure, 3), mech[:6])
