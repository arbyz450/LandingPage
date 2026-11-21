# Self-play simulation report

9505 engine-vs-engine games over 232 decks in 509.6s on 4 processes. Average game 185.3s, overtime in 26%, draws 0.0%. Engine beat the scripted mid-ladder bot 70% of the time.

The simulator is a simplified proxy (see crsf/sim.py). Use these numbers to compare decks and weights against each other, not as ladder predictions.

## Best decks

| # | deck | archetype | avg elixir | games | win rate | 95% CI |
|---|---|---|---|---|---|---|
| 1 | Giant, Inferno Tower, Rocket, Royal Delivery, Dart Goblin, Inferno Dragon, Heal Spirit, Fire Spirit | bait | 3.5 | 99 | 99.0% | 94%-100% |
| 2 | Royal Hogs, Inferno Tower, Rocket, Earthquake, Inferno Dragon, Mini P.E.K.K.A, Ice Spirit, Skeletons | siege | 3.62 | 66 | 98.5% | 92%-100% |
| 3 | Graveyard, Inferno Tower, Rocket, Arrows, Inferno Dragon, Hunter, Bats, Skeletons | siege | 3.75 | 78 | 97.4% | 91%-99% |
| 4 | Goblin Barrel, Lightning, Zap, Inferno Dragon, Zappies, Knight, Fire Spirit, Heal Spirit | bait | 3.0 | 72 | 97.2% | 90%-99% |
| 5 | Mortar, Poison, Arrows, Wizard, Inferno Dragon, Flying Machine, Goblins, Skeletons | cycle | 3.38 | 80 | 96.3% | 90%-99% |
| 6 | Hog Rider, Goblin Cage, Fireball, Earthquake, Inferno Dragon, Magic Archer, Spear Goblins, Ice Spirit | cycle | 3.25 | 84 | 95.2% | 88%-98% |
| 7 | Three Musketeers, Bomb Tower, Fireball, Arrows, Little Prince, Hunter, Heal Spirit, Electro Spirit | three_musketeers | 3.62 | 92 | 94.6% | 88%-98% |
| 8 | Graveyard, Lightning, The Log, Inferno Dragon, Archers, Magic Archer, Ice Spirit, Goblins | siege | 3.38 | 89 | 94.4% | 88%-98% |
| 9 | Balloon, Lumberjack, Bowler, Inferno Dragon, Baby Dragon, Freeze, Tornado, Barbarian Barrel | lavaloon | 3.88 | 82 | 93.9% | 86%-97% |
| 10 | Royal Giant, Hunter, Monk, Fisherman, Skeletons, Electro Spirit, Fireball, Barbarian Barrel | royal_giant | 3.25 | 79 | 92.4% | 84%-96% |
| 11 | Royal Giant, Cannon, Fireball, Barbarian Barrel, Baby Dragon, Mini P.E.K.K.A, Ice Spirit, Fire Spirit | cycle | 3.12 | 86 | 91.9% | 84%-96% |
| 12 | Royal Hogs, Inferno Tower, Lightning, Giant Snowball, Archer Queen, Lumberjack, Fire Spirit, Ice Spirit | goblin_drill | 3.62 | 94 | 91.5% | 84%-96% |
| 13 | Balloon, Lightning, Tornado, Inferno Dragon, Magic Archer, Monk, Ice Golem, Spear Goblins | beatdown | 3.88 | 88 | 90.9% | 83%-95% |
| 14 | Battle Ram, Furnace, Rocket, Royal Delivery, Inferno Dragon, Little Prince, Ice Golem, Heal Spirit | bridge_spam | 3.38 | 83 | 90.4% | 82%-95% |
| 15 | Miner, Poison, Royal Delivery, Princess, Mini P.E.K.K.A, Inferno Dragon, Goblins, Fire Spirit | goblin_drill | 3.0 | 91 | 86.8% | 78%-92% |
| 16 | Goblin Drill, Rocket, Earthquake, Mega Minion, Inferno Dragon, Bandit, Fire Spirit, Ice Spirit | siege | 3.12 | 75 | 86.7% | 77%-93% |
| 17 | Ram Rider, Bomb Tower, Poison, Giant Snowball, Minion Horde, Inferno Dragon, Bats, Skeletons | goblin_drill | 3.38 | 82 | 86.6% | 78%-92% |
| 18 | P.E.K.K.A, Fireball, The Log, Hunter, Knight, Dart Goblin, Skeletons, Bats | siege | 3.25 | 81 | 86.4% | 77%-92% |
| 19 | Giant, Tesla, Poison, Zap, Hunter, Archers, Spear Goblins, Goblins | evolution_centric | 3.25 | 81 | 86.4% | 77%-92% |
| 20 | Battle Ram, Lightning, Earthquake, Goblin Gang, Skeleton King, Inferno Dragon, Spear Goblins, Goblins | beatdown | 3.5 | 87 | 86.2% | 77%-92% |

## Worst decks

- Lava Hound, Tesla, Rocket, Earthquake, Minions, Night Witch, Skeletons, Ice Golem (siege): 5.0% over 80
- Graveyard, Furnace, Ice Wizard, Knight, Poison, Goblin Hut, Skeletons, Barbarian Barrel (graveyard): 4.8% over 83
- Graveyard, Tombstone, Poison, Earthquake, Witch, Mother Witch, Skeletons, Ice Golem (graveyard): 2.5% over 80
- Goblin Drill, Furnace, Lightning, Tornado, Executioner, Ice Wizard, Goblins, Heal Spirit (graveyard): 0.0% over 90
- Goblin Drill, Tombstone, Rocket, Giant Snowball, Zappies, Night Witch, Goblins, Skeletons (goblin_drill): 0.0% over 82

## Cards by win rate (in decks that contained them, >=30 games)

| card | games | win rate |
|---|---|---|
| Freeze | 82 | 93.9% |
| Inferno Dragon | 1492 | 88.6% |
| Fisherman | 475 | 73.9% |
| Balloon | 500 | 70.8% |
| Rune Giant | 90 | 68.9% |
| Royal Giant | 1116 | 68.7% |
| Hunter | 1982 | 68.6% |
| Monk | 492 | 68.3% |
| Little Prince | 1531 | 67.8% |
| Lumberjack | 402 | 67.4% |
| P.E.K.K.A | 882 | 67.2% |
| Minion Giant | 163 | 66.3% |
| Mighty Miner | 400 | 66.2% |
| Ice Spirit | 3908 | 64.5% |
| Giant | 923 | 63.6% |
| Fire Spirit | 3090 | 63.0% |
| Mini P.E.K.K.A | 890 | 62.6% |
| Inferno Tower | 1896 | 62.3% |
| Royal Hogs | 1037 | 61.6% |
| Wizard | 1058 | 59.8% |
| Cannon | 2601 | 59.5% |
| Guards | 428 | 59.2% |
| Hog Rider | 1008 | 58.5% |
| Electro Spirit | 3363 | 57.4% |
| Three Musketeers | 608 | 57.4% |

...

| Elite Barbarians | 233 | 32.6% |
| Barbarians | 177 | 32.2% |
| Cannon Cart | 155 | 31.6% |
| Electro Wizard | 990 | 30.9% |
| Elixir Collector | 80 | 28.7% |
| Tombstone | 1697 | 28.2% |
| Skeleton Dragons | 172 | 27.3% |
| Goblin Hut | 324 | 23.5% |
| Giant Skeleton | 89 | 10.1% |
| Mirror | 78 | 7.7% |

## Archetype matchup matrix (row's win rate vs column)

| | bait | beatdown | bridge_spam | control | cycle | evolution_centric | goblin_drill | graveyard | hybrid | lavaloon | mega_knight | pekka_bridge_spam | royal_giant | siege | three_musketeers |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bait | 50% (56) | 74% (134) | 66% (47) | 70% (83) | 59% (254) | 58% (12) | 57% (67) | 81% (48) | 91% (32) | 58% (36) | 54% (13) | 70% (27) | 50% (42) | 66% (213) | 43% (37) |
| beatdown | 26% (134) | 50% (306) | 52% (80) | 48% (170) | 40% (574) | 29% (17) | 38% (133) | 79% (101) | 79% (61) | 48% (71) | 27% (26) | 53% (57) | 31% (84) | 53% (429) | 40% (73) |
| bridge_spam | 34% (47) | 48% (80) | 50% (16) | 58% (53) | 43% (150) | 12% (8) | 46% (37) | 68% (25) | 79% (19) | 55% (20) | 80% (5) | 58% (19) | 32% (28) | 56% (133) | 38% (16) |
| control | 30% (83) | 52% (170) | 42% (53) | 50% (78) | 45% (369) | 25% (12) | 41% (56) | 78% (67) | 82% (33) | 54% (52) | 17% (6) | 74% (34) | 25% (40) | 57% (279) | 28% (36) |
| cycle | 41% (254) | 60% (574) | 57% (150) | 55% (369) | 50% (1112) | 49% (35) | 44% (268) | 78% (227) | 81% (116) | 58% (170) | 43% (37) | 73% (124) | 34% (151) | 55% (926) | 44% (161) |
| evolution_centric | 42% (12) | 71% (17) | 88% (8) | 75% (12) | 51% (35) | - | 36% (11) | 88% (8) | 83% (6) | 78% (9) | 100% (1) | 100% (1) | 60% (5) | 72% (36) | 33% (9) |
| goblin_drill | 43% (67) | 62% (133) | 54% (37) | 59% (56) | 56% (268) | 64% (11) | 50% (58) | 84% (49) | 63% (27) | 62% (39) | 89% (9) | 74% (31) | 52% (31) | 58% (211) | 29% (42) |
| graveyard | 19% (48) | 21% (101) | 32% (25) | 22% (67) | 22% (227) | 12% (8) | 16% (49) | 50% (34) | 35% (23) | 24% (33) | 8% (12) | 36% (25) | 14% (37) | 27% (186) | 23% (30) |
| hybrid | 9% (32) | 21% (61) | 21% (19) | 18% (33) | 19% (116) | 17% (6) | 37% (27) | 65% (23) | 50% (14) | 43% (21) | 0% (1) | 27% (11) | 35% (20) | 33% (98) | 6% (18) |
| lavaloon | 42% (36) | 52% (71) | 45% (20) | 46% (52) | 42% (170) | 22% (9) | 38% (39) | 76% (33) | 57% (21) | 50% (22) | 40% (5) | 63% (19) | 26% (19) | 46% (123) | 32% (25) |
| mega_knight | 46% (13) | 73% (26) | 20% (5) | 83% (6) | 57% (37) | 0% (1) | 11% (9) | 92% (12) | 100% (1) | 60% (5) | 50% (4) | 100% (2) | 25% (4) | 54% (24) | 67% (3) |
| pekka_bridge_spam | 30% (27) | 47% (57) | 42% (19) | 26% (34) | 27% (124) | 0% (1) | 26% (31) | 64% (25) | 73% (11) | 37% (19) | 0% (2) | 50% (10) | 18% (22) | 32% (80) | 20% (15) |
| royal_giant | 50% (42) | 69% (84) | 68% (28) | 75% (40) | 66% (151) | 40% (5) | 48% (31) | 86% (37) | 65% (20) | 74% (19) | 75% (4) | 82% (22) | 50% (16) | 68% (133) | 60% (20) |
| siege | 34% (213) | 47% (429) | 44% (133) | 43% (279) | 45% (926) | 28% (36) | 42% (211) | 73% (186) | 67% (98) | 55% (123) | 46% (24) | 68% (80) | 32% (133) | 50% (692) | 27% (120) |
| three_musketeers | 57% (37) | 60% (73) | 62% (16) | 72% (36) | 56% (161) | 67% (9) | 71% (42) | 77% (30) | 94% (18) | 68% (25) | 33% (3) | 80% (15) | 40% (20) | 73% (120) | 50% (18) |

## Engine weights used

```json
{
 "defense": 1.2206071245926373,
 "tower_damage_prevented": 1.1579560843847376,
 "offense": 1.028387301095691,
 "support_synergy": 0.8358186588271216,
 "build_push": 0.5845871320239134,
 "cycle": 0.3447687492745849,
 "leak": 2.6715091780992064,
 "reserve": 0.651467217593212,
 "overcommit": 1.2163829047125028,
 "opp_response": 0.6451564721160423,
 "spell_cycle": 0.15382515292923307,
 "wait_bias": 0.002854013173965269
}
```
