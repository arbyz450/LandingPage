# Strategy report (self-play tournament)

5734 games in 355.8s: full round-robin of 32 meta decks (x2 seeds, both sides), five player styles against the tuned engine, and a sweep of the engine's aggression thresholds.

Simulator caveat: a simplified proxy of the game (see crsf/sim.py). Treat every number as relative, not as a ladder prediction.

## Meta decks, round-robin

| # | deck | archetype | games | win rate | 95% CI |
|---|---|---|---|---|---|
| 1 | Golem Night Witch — Golem, Night Witch, Phoenix, Bomber, Mini P.E.K.K.A, Elite Barbarians, Arrows, Zap | beatdown | 124 | 96.8% | 92%-99% |
| 2 | Evo Royal Giant Hunter Monk — Royal Giant, Hunter, Monk, Fisherman, Skeletons, Electro Spirit, Fireball, Barbarian Barrel | royal_giant | 124 | 91.9% | 86%-96% |
| 3 | Royal Giant 3.0 Ghost Cycle — Royal Giant, Hunter, Royal Ghost, Fisherman, Skeletons, Electro Spirit, Fireball, The Log | royal_giant | 124 | 83.9% | 76%-89% |
| 4 | Hog 2.6 Cycle (Evo Skeletons / Evo Cannon / Hero Musketeer) — Hog Rider, Musketeer, Cannon, Ice Golem, Ice Spirit, Skeletons, Fireball, The Log | cycle | 124 | 75.0% | 67%-82% |
| 5 | LumberLoon Freeze (Bowler) — Balloon, Lumberjack, Bowler, Inferno Dragon, Baby Dragon, Freeze, Tornado, Barbarian Barrel | lavaloon | 124 | 75.0% | 67%-82% |
| 6 | X-Bow 3.0 (Evo Tesla / Evo Archers / Hero Knight) — X-Bow, Tesla, Archers, Knight, Skeletons, Ice Spirit, Fireball, The Log | siege | 124 | 69.4% | 61%-77% |
| 7 | Evo Royal Hogs Hut Cycle (Hero Berserker) — Royal Hogs, Royal Ghost, Berserker, Goblin Hut, Furnace, Electro Spirit, Fireball, Barbarian Barrel | cycle | 124 | 68.5% | 60%-76% |
| 8 | Royal Hogs Archer Queen Earthquake — Royal Hogs, Cannon, Archer Queen, Skeletons, Electro Spirit, The Log, Earthquake, Royal Delivery | cycle | 124 | 65.3% | 57%-73% |
| 9 | Minion Giant Rune Giant Little Prince — Minion Giant, Rune Giant, Little Prince, Cannon, Bats, Skeletons, Poison, Barbarian Barrel | control | 124 | 63.7% | 55%-72% |
| 10 | Minion Giant Lightning 3.1 — Minion Giant, Archers, Ice Wizard, Cannon, Skeletons, Lightning, Barbarian Barrel, Knight | control | 124 | 60.5% | 52%-69% |
| 11 | Evo Goblin Drill Evo Mirror (Hero Bowler) — Goblin Drill, Mirror, Bowler, Knight, Goblin Hut, Furnace, Barbarian Barrel, Giant Snowball | goblin_drill | 124 | 58.1% | 49%-66% |
| 12 | Hog Earthquake Firecracker (Evo Tesla / Hero Knight) — Hog Rider, Firecracker, Knight, Tesla, The Log, Electro Spirit, Skeletons, Earthquake | cycle | 124 | 56.5% | 48%-65% |
| 13 | Golem Hero Electro Wizard — Golem, Electro Wizard, Elite Barbarians, Cannon Cart, Berserker, Furnace, Zap, Barbarian Barrel | beatdown | 124 | 53.2% | 44%-62% |
| 14 | Royal Hogs Three Musketeers — Three Musketeers, Royal Hogs, Royal Ghost, Barbarian Barrel, Ice Golem, Hunter, Fireball, Heal Spirit | three_musketeers | 124 | 53.2% | 44%-62% |
| 15 | Mega Knight Witch Valkyrie (mid-ladder) — Mega Knight, Witch, Valkyrie, Mini P.E.K.K.A, Baby Dragon, Skeleton Army, Skeleton Barrel, Arrows | mega_knight | 124 | 52.4% | 44%-61% |
| 16 | Graveyard Control (Evo Furnace / Hero Ice Wizard) — Graveyard, Furnace, Ice Wizard, Knight, Poison, Goblin Hut, Skeletons, Barbarian Barrel | graveyard | 124 | 51.6% | 43%-60% |
| 17 | Log Bait Ronin 2.5 — Goblin Barrel, Ronin, Magic Archer, Wall Breakers, Cannon, Fire Spirit, Ice Spirit, Skeletons | bait | 124 | 50.0% | 41%-59% |
| 18 | Goblin Drill Cycle 2.5 (Hero Knight / Evo Cannon) — Goblin Drill, Giant Snowball, Knight, Cannon, Poison, Bomber, Fire Spirit, Skeletons | goblin_drill | 124 | 48.8% | 40%-57% |
| 19 | Lava Hound Hero Mega Minion (Flying Machine) — Lava Hound, Mega Minion, Baby Dragon, Zap, Barbarians, Flying Machine, Tombstone, Fireball | lavaloon | 124 | 46.8% | 38%-56% |
| 20 | Evo Mortar Bait (Rascals / Cannon Cart) — Mortar, Skeleton Barrel, Ice Wizard, Goblin Gang, Rascals, Cannon Cart, Fireball, Barbarian Barrel | siege | 124 | 45.2% | 37%-54% |
| 21 | Classic Log Bait — Goblin Barrel, Ice Spirit, The Log, Princess, Goblin Gang, Knight, Inferno Tower, Rocket | bait | 124 | 43.5% | 35%-52% |
| 22 | Evo Giant Sparky — Giant, Wizard, Mini P.E.K.K.A, Sparky, Zap, Tornado, Heal Spirit, Vines | beatdown | 124 | 40.3% | 32%-49% |
| 23 | LavaLoon (Hero Balloon / Hero Mega Minion) — Lava Hound, Balloon, Mega Minion, Zap, Barbarians, Skeleton Dragons, Tombstone, Fireball | lavaloon | 124 | 40.3% | 32%-49% |
| 24 | PEKKA Bridge Spam (Golden Knight) — Battle Ram, Royal Ghost, Golden Knight, P.E.K.K.A, Electro Wizard, Bandit, Furnace, Arrows | pekka_bridge_spam | 124 | 39.5% | 31%-48% |
| 25 | Evo Giant Double Prince — Giant, Zap, Mega Minion, Bomber, Prince, Dark Prince, Rage, Lightning | beatdown | 124 | 37.1% | 29%-46% |
| 26 | Electro Giant Bowler Lightning — Electro Giant, Bowler, Baby Dragon, Goblin Hut, Lightning, Tornado, Barbarian Barrel, Knight | beatdown | 124 | 31.5% | 24%-40% |
| 27 | Hog Ronin Cycle 2.9 — Hog Rider, Ronin, Firecracker, Earthquake, Barbarian Barrel, Tesla, Ice Spirit, Skeletons | cycle | 124 | 30.6% | 23%-39% |
| 28 | Golem Elixir Collector — Golem, Electro Dragon, Skeleton Dragons, Elite Barbarians, Berserker, Elixir Collector, Tornado, Barbarian Barrel | beatdown | 124 | 21.8% | 15%-30% |
| 29 | Evo Giant Graveyard (Evo Witch / Hero Bowler) — Giant, Graveyard, Witch, Bowler, Giant Snowball, Guards, Zappies, Arrows | graveyard | 124 | 20.2% | 14%-28% |
| 30 | Splashyard (Hero Ice Wizard) — Graveyard, Valkyrie, Baby Dragon, Ice Wizard, Tombstone, Poison, Tornado, Barbarian Barrel | graveyard | 124 | 12.1% | 8%-19% |
| 31 | Battle Ram Bridge Spam (Giant Skeleton) — Battle Ram, Royal Ghost, Electro Wizard, Giant Skeleton, Bandit, Furnace, Arrows, Heal Spirit | bridge_spam | 124 | 11.7% | 7%-18% |
| 32 | Miner Evo Wall Breakers Bomb Tower — Miner, Wall Breakers, Valkyrie, Spear Goblins, Skeletons, Bomb Tower, Rocket, Tornado | cycle | 124 | 5.6% | 3%-11% |

## Best meta deck against each archetype

| opponent archetype | best deck | win rate | games |
|---|---|---|---|
| bait | Royal Giant 3.0 Ghost Cycle | 100% | 8 |
| beatdown | Golem Night Witch | 100% | 20 |
| bridge_spam | Hog Earthquake Firecracker (Evo Tesla / Hero Knight) | 100% | 4 |
| control | Golem Night Witch | 100% | 8 |
| cycle | Golem Night Witch | 100% | 24 |
| goblin_drill | Royal Giant 3.0 Ghost Cycle | 100% | 8 |
| graveyard | Evo Goblin Drill Evo Mirror (Hero Bowler) | 100% | 12 |
| lavaloon | Evo Royal Giant Hunter Monk | 100% | 12 |
| mega_knight | Evo Goblin Drill Evo Mirror (Hero Bowler) | 100% | 4 |
| pekka_bridge_spam | LumberLoon Freeze (Bowler) | 100% | 4 |
| royal_giant | Golem Night Witch | 75% | 8 |
| siege | Royal Giant 3.0 Ghost Cycle | 100% | 8 |
| three_musketeers | LumberLoon Freeze (Bowler) | 100% | 4 |

## Archetype matrix (row beats column, meta decks only)

| | bait | beatdown | bridge_spam | control | cycle | goblin_drill | graveyard | lavaloon | mega_knight | pekka_bridge_spam | royal_giant | siege | three_musketeers |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bait | 50% (8) | 52% (48) | 100% (8) | 25% (16) | 40% (48) | 50% (16) | 83% (24) | 58% (24) | 62% (8) | 50% (8) | 0% (16) | 31% (16) | 0% (8) |
| beatdown | 48% (48) | 50% (120) | 96% (24) | 25% (48) | 52% (144) | 38% (48) | 60% (72) | 35% (72) | 33% (24) | 54% (24) | 25% (48) | 48% (48) | 54% (24) |
| bridge_spam | 0% (8) | 4% (24) | - | 12% (8) | 21% (24) | 6% (8) | 25% (12) | 8% (12) | 25% (4) | 0% (4) | 0% (8) | 12% (8) | 25% (4) |
| control | 75% (16) | 75% (48) | 88% (8) | 50% (8) | 60% (48) | 62% (16) | 79% (24) | 62% (24) | 25% (8) | 88% (8) | 19% (16) | 25% (16) | 75% (8) |
| cycle | 60% (48) | 48% (144) | 79% (24) | 40% (48) | 50% (120) | 54% (48) | 79% (72) | 44% (72) | 50% (24) | 46% (24) | 10% (48) | 52% (48) | 42% (24) |
| goblin_drill | 50% (16) | 62% (48) | 94% (8) | 38% (16) | 46% (48) | 50% (8) | 96% (24) | 46% (24) | 100% (8) | 88% (8) | 0% (16) | 19% (16) | 38% (8) |
| graveyard | 17% (24) | 40% (72) | 75% (12) | 21% (24) | 21% (72) | 4% (24) | 50% (24) | 33% (36) | 17% (12) | 42% (12) | 0% (24) | 21% (24) | 42% (12) |
| lavaloon | 42% (24) | 65% (72) | 92% (12) | 38% (24) | 56% (72) | 54% (24) | 67% (36) | 50% (24) | 50% (12) | 100% (12) | 12% (24) | 33% (24) | 50% (12) |
| mega_knight | 38% (8) | 67% (24) | 75% (4) | 75% (8) | 50% (24) | 0% (8) | 83% (12) | 50% (12) | - | 50% (4) | 0% (8) | 62% (8) | 50% (4) |
| pekka_bridge_spam | 50% (8) | 46% (24) | 100% (4) | 12% (8) | 54% (24) | 12% (8) | 58% (12) | 0% (12) | 50% (4) | - | 0% (8) | 38% (8) | 75% (4) |
| royal_giant | 100% (16) | 75% (48) | 100% (8) | 81% (16) | 90% (48) | 100% (16) | 100% (24) | 88% (24) | 100% (8) | 100% (8) | 50% (8) | 94% (16) | 75% (8) |
| siege | 69% (16) | 52% (48) | 88% (8) | 75% (16) | 48% (48) | 81% (16) | 79% (24) | 67% (24) | 38% (8) | 62% (8) | 6% (16) | 50% (8) | 38% (8) |
| three_musketeers | 100% (8) | 46% (24) | 75% (4) | 25% (8) | 58% (24) | 62% (8) | 58% (12) | 50% (12) | 50% (4) | 25% (4) | 25% (8) | 62% (8) | - |

## Player styles against the tuned engine

| style | win rate vs engine | games |
|---|---|---|
| aggressive | 48.3% | 300 |
| defensive | 53.0% | 300 |
| slow | 47.3% | 300 |
| spammer | 15.7% | 300 |
| midladder | 31.7% | 300 |

Aggressive style vs defensive style: aggressive wins 42.7%.

## Aggression sweep (decision thresholds vs the shipped baseline 0.4 / 1.0)

The 0.4 / 1.0 row is a CONTROL: it is identical to the baseline, so its distance from 50% is the noise level of this sweep. Only differences clearly larger than that mean anything.

| play if worth >= | or >= better than waiting | win rate vs baseline | vs control | games |
|---|---|---|---|---|
| 0.2 | 0.5 | 55.3% | -1.4% | 300 |
| 0.2 | 2.5 | 63.0% | +6.3% | 300 |
| 0.4 | 0.5 | 55.0% | -1.7% | 300 |
| 0.4 | 1.0 | 56.7% (control) | +0.0% | 300 |
| 0.4 | 1.5 | 59.0% | +2.3% | 300 |
| 0.6 | 1.5 | 56.3% | -0.4% | 300 |
| 0.8 | 2.0 | 60.7% | +4.0% | 300 |

No threshold setting beat the control by more than the noise (±7%); keep the shipped 0.4 / 1.0.

## Takeaways (auto-generated from the numbers above)

- **aggressive** style wins 48% against the engine: close; worth studying what it does.
- **defensive** style wins 53% against the engine: close; worth studying what it does.
- **slow** style wins 47% against the engine: close; worth studying what it does.
- **spammer** style wins 16% against the engine: the engine's balance beats it.
- **midladder** style wins 32% against the engine: the engine's balance beats it.
- Counter-picks: vs bait: Royal Giant 3.0 Ghost Cycle; vs beatdown: Golem Night Witch; vs bridge_spam: Hog Earthquake Firecracker (Evo Tesla / Hero Knight); vs control: Golem Night Witch; vs cycle: Golem Night Witch; vs goblin_drill: Royal Giant 3.0 Ghost Cycle.
