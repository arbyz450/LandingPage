# Strategy report (self-play tournament)

5734 games in 330.1s: full round-robin of 32 meta decks (x2 seeds, both sides), five player styles against the tuned engine, and a sweep of the engine's aggression thresholds.

Simulator caveat: a simplified proxy of the game (see crsf/sim.py). Treat every number as relative, not as a ladder prediction.

## Meta decks, round-robin

| # | deck | archetype | games | win rate | 95% CI |
|---|---|---|---|---|---|
| 1 | Golem Night Witch — Golem, Night Witch, Phoenix, Bomber, Mini P.E.K.K.A, Elite Barbarians, Arrows, Zap | beatdown | 124 | 94.4% | 89%-97% |
| 2 | PEKKA Bridge Spam (Golden Knight) — Battle Ram, Royal Ghost, Golden Knight, P.E.K.K.A, Electro Wizard, Bandit, Furnace, Arrows | pekka_bridge_spam | 124 | 88.7% | 82%-93% |
| 3 | Battle Ram Bridge Spam (Giant Skeleton) — Battle Ram, Royal Ghost, Electro Wizard, Giant Skeleton, Bandit, Furnace, Arrows, Heal Spirit | bridge_spam | 124 | 83.1% | 76%-89% |
| 4 | Evo Royal Giant Hunter Monk — Royal Giant, Hunter, Monk, Fisherman, Skeletons, Electro Spirit, Fireball, Barbarian Barrel | royal_giant | 124 | 83.1% | 76%-89% |
| 5 | Royal Giant 3.0 Ghost Cycle — Royal Giant, Hunter, Royal Ghost, Fisherman, Skeletons, Electro Spirit, Fireball, The Log | royal_giant | 124 | 81.5% | 74%-87% |
| 6 | Evo Mortar Bait (Rascals / Cannon Cart) — Mortar, Skeleton Barrel, Ice Wizard, Goblin Gang, Rascals, Cannon Cart, Fireball, Barbarian Barrel | siege | 124 | 71.8% | 63%-79% |
| 7 | LumberLoon Freeze (Bowler) — Balloon, Lumberjack, Bowler, Inferno Dragon, Baby Dragon, Freeze, Tornado, Barbarian Barrel | lavaloon | 124 | 70.2% | 62%-78% |
| 8 | Mega Knight Witch Valkyrie (mid-ladder) — Mega Knight, Witch, Valkyrie, Mini P.E.K.K.A, Baby Dragon, Skeleton Army, Skeleton Barrel, Arrows | mega_knight | 124 | 67.7% | 59%-75% |
| 9 | Evo Royal Hogs Hut Cycle (Hero Berserker) — Royal Hogs, Royal Ghost, Berserker, Goblin Hut, Furnace, Electro Spirit, Fireball, Barbarian Barrel | cycle | 124 | 65.3% | 57%-73% |
| 10 | X-Bow 3.0 (Evo Tesla / Evo Archers / Hero Knight) — X-Bow, Tesla, Archers, Knight, Skeletons, Ice Spirit, Fireball, The Log | siege | 124 | 62.9% | 54%-71% |
| 11 | Royal Hogs Archer Queen Earthquake — Royal Hogs, Cannon, Archer Queen, Skeletons, Electro Spirit, The Log, Earthquake, Royal Delivery | cycle | 124 | 62.1% | 53%-70% |
| 12 | Hog 2.6 Cycle (Evo Skeletons / Evo Cannon / Hero Musketeer) — Hog Rider, Musketeer, Cannon, Ice Golem, Ice Spirit, Skeletons, Fireball, The Log | cycle | 124 | 61.3% | 52%-69% |
| 13 | Evo Goblin Drill Evo Mirror (Hero Bowler) — Goblin Drill, Mirror, Bowler, Knight, Goblin Hut, Furnace, Barbarian Barrel, Giant Snowball | goblin_drill | 124 | 54.8% | 46%-63% |
| 14 | Royal Hogs Three Musketeers — Three Musketeers, Royal Hogs, Royal Ghost, Barbarian Barrel, Ice Golem, Hunter, Fireball, Heal Spirit | three_musketeers | 124 | 52.4% | 44%-61% |
| 15 | Log Bait Ronin 2.5 — Goblin Barrel, Ronin, Magic Archer, Wall Breakers, Cannon, Fire Spirit, Ice Spirit, Skeletons | bait | 124 | 51.6% | 43%-60% |
| 16 | Minion Giant Rune Giant Little Prince — Minion Giant, Rune Giant, Little Prince, Cannon, Bats, Skeletons, Poison, Barbarian Barrel | control | 124 | 50.8% | 42%-59% |
| 17 | Minion Giant Lightning 3.1 — Minion Giant, Archers, Ice Wizard, Cannon, Skeletons, Lightning, Barbarian Barrel, Knight | control | 124 | 46.0% | 37%-55% |
| 18 | Golem Hero Electro Wizard — Golem, Electro Wizard, Elite Barbarians, Cannon Cart, Berserker, Furnace, Zap, Barbarian Barrel | beatdown | 124 | 44.4% | 36%-53% |
| 19 | Lava Hound Hero Mega Minion (Flying Machine) — Lava Hound, Mega Minion, Baby Dragon, Zap, Barbarians, Flying Machine, Tombstone, Fireball | lavaloon | 124 | 43.5% | 35%-52% |
| 20 | Goblin Drill Cycle 2.5 (Hero Knight / Evo Cannon) — Goblin Drill, Giant Snowball, Knight, Cannon, Poison, Bomber, Fire Spirit, Skeletons | goblin_drill | 124 | 42.7% | 34%-52% |
| 21 | Hog Earthquake Firecracker (Evo Tesla / Hero Knight) — Hog Rider, Firecracker, Knight, Tesla, The Log, Electro Spirit, Skeletons, Earthquake | cycle | 124 | 41.1% | 33%-50% |
| 22 | Classic Log Bait — Goblin Barrel, Ice Spirit, The Log, Princess, Goblin Gang, Knight, Inferno Tower, Rocket | bait | 124 | 37.1% | 29%-46% |
| 23 | Graveyard Control (Evo Furnace / Hero Ice Wizard) — Graveyard, Furnace, Ice Wizard, Knight, Poison, Goblin Hut, Skeletons, Barbarian Barrel | graveyard | 124 | 36.3% | 28%-45% |
| 24 | Evo Giant Sparky — Giant, Wizard, Mini P.E.K.K.A, Sparky, Zap, Tornado, Heal Spirit, Vines | beatdown | 124 | 36.3% | 28%-45% |
| 25 | LavaLoon (Hero Balloon / Hero Mega Minion) — Lava Hound, Balloon, Mega Minion, Zap, Barbarians, Skeleton Dragons, Tombstone, Fireball | lavaloon | 124 | 35.5% | 28%-44% |
| 26 | Hog Ronin Cycle 2.9 — Hog Rider, Ronin, Firecracker, Earthquake, Barbarian Barrel, Tesla, Ice Spirit, Skeletons | cycle | 124 | 29.0% | 22%-38% |
| 27 | Electro Giant Bowler Lightning — Electro Giant, Bowler, Baby Dragon, Goblin Hut, Lightning, Tornado, Barbarian Barrel, Knight | beatdown | 124 | 28.2% | 21%-37% |
| 28 | Evo Giant Double Prince — Giant, Zap, Mega Minion, Bomber, Prince, Dark Prince, Rage, Lightning | beatdown | 124 | 22.6% | 16%-31% |
| 29 | Splashyard (Hero Ice Wizard) — Graveyard, Valkyrie, Baby Dragon, Ice Wizard, Tombstone, Poison, Tornado, Barbarian Barrel | graveyard | 124 | 17.7% | 12%-25% |
| 30 | Evo Giant Graveyard (Evo Witch / Hero Bowler) — Giant, Graveyard, Witch, Bowler, Giant Snowball, Guards, Zappies, Arrows | graveyard | 124 | 17.7% | 12%-25% |
| 31 | Golem Elixir Collector — Golem, Electro Dragon, Skeleton Dragons, Elite Barbarians, Berserker, Elixir Collector, Tornado, Barbarian Barrel | beatdown | 124 | 16.1% | 11%-24% |
| 32 | Miner Evo Wall Breakers Bomb Tower — Miner, Wall Breakers, Valkyrie, Spear Goblins, Skeletons, Bomb Tower, Rocket, Tornado | cycle | 124 | 4.0% | 2%-9% |

## Best meta deck against each archetype

| opponent archetype | best deck | win rate | games |
|---|---|---|---|
| bait | Royal Giant 3.0 Ghost Cycle | 100% | 8 |
| beatdown | Golem Night Witch | 100% | 20 |
| bridge_spam | Evo Royal Hogs Hut Cycle (Hero Berserker) | 100% | 4 |
| control | Mega Knight Witch Valkyrie (mid-ladder) | 100% | 8 |
| cycle | Evo Royal Giant Hunter Monk | 100% | 24 |
| goblin_drill | Evo Royal Giant Hunter Monk | 100% | 8 |
| graveyard | Log Bait Ronin 2.5 | 100% | 12 |
| lavaloon | Golem Night Witch | 100% | 12 |
| mega_knight | Royal Giant 3.0 Ghost Cycle | 100% | 4 |
| pekka_bridge_spam | Battle Ram Bridge Spam (Giant Skeleton) | 75% | 4 |
| royal_giant | Golem Night Witch | 100% | 8 |
| siege | PEKKA Bridge Spam (Golden Knight) | 100% | 8 |
| three_musketeers | Evo Royal Giant Hunter Monk | 100% | 4 |

## Archetype matrix (row beats column, meta decks only)

| | bait | beatdown | bridge_spam | control | cycle | goblin_drill | graveyard | lavaloon | mega_knight | pekka_bridge_spam | royal_giant | siege | three_musketeers |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bait | 50% (8) | 52% (48) | 12% (8) | 25% (16) | 56% (48) | 62% (16) | 67% (24) | 50% (24) | 38% (8) | 25% (8) | 0% (16) | 19% (16) | 38% (8) |
| beatdown | 48% (48) | 50% (120) | 4% (24) | 27% (48) | 50% (144) | 40% (48) | 65% (72) | 32% (72) | 29% (24) | 4% (24) | 19% (48) | 31% (48) | 42% (24) |
| bridge_spam | 88% (8) | 96% (24) | - | 100% (8) | 75% (24) | 62% (8) | 92% (12) | 75% (12) | 75% (4) | 75% (4) | 88% (8) | 62% (8) | 100% (4) |
| control | 75% (16) | 73% (48) | 0% (8) | 50% (8) | 56% (48) | 44% (16) | 71% (24) | 46% (24) | 0% (8) | 0% (8) | 0% (16) | 6% (16) | 75% (8) |
| cycle | 44% (48) | 50% (144) | 25% (24) | 44% (48) | 50% (120) | 48% (48) | 78% (72) | 47% (72) | 29% (24) | 8% (24) | 6% (48) | 25% (48) | 38% (24) |
| goblin_drill | 38% (16) | 60% (48) | 38% (8) | 56% (16) | 52% (48) | 50% (8) | 88% (24) | 54% (24) | 38% (8) | 12% (8) | 6% (16) | 25% (16) | 25% (8) |
| graveyard | 33% (24) | 35% (72) | 8% (12) | 29% (24) | 22% (72) | 12% (24) | 50% (24) | 28% (36) | 17% (12) | 8% (12) | 0% (24) | 12% (24) | 8% (12) |
| lavaloon | 50% (24) | 68% (72) | 25% (12) | 54% (24) | 53% (72) | 46% (24) | 72% (36) | 50% (24) | 17% (12) | 8% (12) | 21% (24) | 29% (24) | 50% (12) |
| mega_knight | 62% (8) | 71% (24) | 25% (4) | 100% (8) | 71% (24) | 62% (8) | 83% (12) | 83% (12) | - | 25% (4) | 38% (8) | 62% (8) | 50% (4) |
| pekka_bridge_spam | 75% (8) | 96% (24) | 25% (4) | 100% (8) | 92% (24) | 88% (8) | 92% (12) | 92% (12) | 75% (4) | - | 75% (8) | 100% (8) | 100% (4) |
| royal_giant | 100% (16) | 81% (48) | 12% (8) | 100% (16) | 94% (48) | 94% (16) | 100% (24) | 79% (24) | 62% (8) | 25% (8) | 50% (8) | 81% (16) | 62% (8) |
| siege | 81% (16) | 69% (48) | 38% (8) | 94% (16) | 75% (48) | 75% (16) | 88% (24) | 71% (24) | 38% (8) | 0% (8) | 19% (16) | 50% (8) | 88% (8) |
| three_musketeers | 62% (8) | 58% (24) | 0% (4) | 25% (8) | 62% (24) | 75% (8) | 92% (12) | 50% (12) | 50% (4) | 0% (4) | 38% (8) | 12% (8) | - |

## Player styles against the tuned engine

| style | win rate vs engine | games |
|---|---|---|
| aggressive | 49.7% | 300 |
| defensive | 53.0% | 300 |
| slow | 45.0% | 300 |
| spammer | 18.7% | 300 |
| midladder | 22.3% | 300 |

Aggressive style vs defensive style: aggressive wins 40.0%.

## Aggression sweep (decision thresholds vs the shipped baseline 0.4 / 1.0)

The 0.4 / 1.0 row is a CONTROL: it is identical to the baseline, so its distance from 50% is the noise level of this sweep. Only differences clearly larger than that mean anything.

| play if worth >= | or >= better than waiting | win rate vs baseline | vs control | games |
|---|---|---|---|---|
| 0.2 | 0.5 | 52.0% | -3.0% | 300 |
| 0.2 | 2.5 | 53.7% | -1.3% | 300 |
| 0.4 | 0.5 | 52.0% | -3.0% | 300 |
| 0.4 | 1.0 | 55.0% (control) | +0.0% | 300 |
| 0.4 | 1.5 | 55.7% | +0.7% | 300 |
| 0.6 | 1.5 | 55.2% | +0.2% | 300 |
| 0.8 | 2.0 | 56.0% | +1.0% | 300 |

No threshold setting beat the control by more than the noise (±5%); keep the shipped 0.4 / 1.0.

## Takeaways (auto-generated from the numbers above)

- **aggressive** style wins 50% against the engine: close; worth studying what it does.
- **defensive** style wins 53% against the engine: close; worth studying what it does.
- **slow** style wins 45% against the engine: close; worth studying what it does.
- **spammer** style wins 19% against the engine: the engine's balance beats it.
- **midladder** style wins 22% against the engine: the engine's balance beats it.
- Counter-picks: vs bait: Royal Giant 3.0 Ghost Cycle; vs beatdown: Golem Night Witch; vs bridge_spam: Evo Royal Hogs Hut Cycle (Hero Berserker); vs control: Mega Knight Witch Valkyrie (mid-ladder); vs cycle: Evo Royal Giant Hunter Monk; vs goblin_drill: Evo Royal Giant Hunter Monk.
