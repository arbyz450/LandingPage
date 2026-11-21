# Self-play simulation report

9505 engine-vs-engine games over 232 decks in 682.1s on 4 processes. Average game 174.5s, overtime in 24%, draws 0.0%. Engine beat the scripted mid-ladder bot 74% of the time.

The simulator is a simplified proxy (see crsf/sim.py). Use these numbers to compare decks and weights against each other, not as ladder predictions.

## Best decks

| # | deck | archetype | avg elixir | games | win rate | 95% CI |
|---|---|---|---|---|---|---|
| 1 | Royal Hogs, Furnace, Fireball, Giant Snowball, Phoenix, Bowler, Ice Golem, Electro Spirit | three_musketeers | 3.38 | 78 | 98.7% | 93%-100% |
| 2 | Electro Giant, Lightning, Giant Snowball, Phoenix, Flying Machine, Zappies, Bats, Ice Golem | beatdown | 3.88 | 73 | 98.6% | 93%-100% |
| 3 | Royal Hogs, Lightning, Barbarian Barrel, Musketeer, Phoenix, Golden Knight, Skeletons, Goblins | cycle | 3.5 | 71 | 97.2% | 90%-99% |
| 4 | P.E.K.K.A, Lightning, Tornado, Phoenix, Golden Knight, Guards, Fire Spirit, Bats | control | 3.75 | 79 | 96.2% | 89%-99% |
| 5 | Ram Rider, Inferno Tower, Poison, The Log, Minions, Phoenix, Skeletons, Ice Golem | cycle | 3.25 | 85 | 95.3% | 88%-98% |
| 6 | Giant, Inferno Tower, Rocket, Royal Delivery, Dart Goblin, Inferno Dragon, Heal Spirit, Fire Spirit | bait | 3.5 | 99 | 94.9% | 89%-98% |
| 7 | Elixir Golem, Tesla, Rocket, Royal Delivery, Phoenix, Firecracker, Ice Spirit, Goblins | siege | 3.25 | 92 | 94.6% | 88%-98% |
| 8 | Three Musketeers, Bomb Tower, Fireball, Arrows, Little Prince, Hunter, Heal Spirit, Electro Spirit | three_musketeers | 3.62 | 92 | 94.6% | 88%-98% |
| 9 | Golem, Night Witch, Phoenix, Bomber, Mini P.E.K.K.A, Elite Barbarians, Arrows, Zap | beatdown | 4.12 | 76 | 93.4% | 86%-97% |
| 10 | Wall Breakers, Tesla, Fireball, Tornado, Executioner, Phoenix, Ice Golem, Skeletons | siege | 3.12 | 92 | 92.4% | 85%-96% |
| 11 | Hog Rider, Cannon, Poison, Tornado, Phoenix, Valkyrie, Ice Golem, Bats | control | 3.25 | 89 | 92.1% | 85%-96% |
| 12 | Battle Ram, Furnace, Rocket, Royal Delivery, Inferno Dragon, Little Prince, Ice Golem, Heal Spirit | bridge_spam | 3.38 | 83 | 91.6% | 84%-96% |
| 13 | Graveyard, Inferno Tower, Rocket, Arrows, Inferno Dragon, Hunter, Bats, Skeletons | siege | 3.75 | 78 | 88.5% | 80%-94% |
| 14 | Elixir Golem, Poison, Arrows, Phoenix, Magic Archer, Ice Wizard, Goblins, Fire Spirit | control | 3.0 | 83 | 88.0% | 79%-93% |
| 15 | Elixir Golem, Poison, Arrows, Hunter, Bowler, Bats, Spear Goblins, Ice Spirit | control | 3.0 | 81 | 87.7% | 79%-93% |
| 16 | Royal Hogs, Inferno Tower, Rocket, Earthquake, Inferno Dragon, Mini P.E.K.K.A, Ice Spirit, Skeletons | siege | 3.62 | 66 | 86.4% | 76%-93% |
| 17 | Royal Giant, Hunter, Monk, Fisherman, Skeletons, Electro Spirit, Fireball, Barbarian Barrel | royal_giant | 3.25 | 79 | 86.1% | 77%-92% |
| 18 | Hog Rider, Furnace, Lightning, Giant Snowball, Hunter, Golden Knight, Bats, Electro Spirit | bridge_spam | 3.38 | 85 | 85.9% | 77%-92% |
| 19 | Battle Ram, Tombstone, Fireball, Barbarian Barrel, Musketeer, Hunter, Ice Spirit, Skeletons | cycle | 2.88 | 100 | 85.0% | 77%-91% |
| 20 | Goblin Barrel, Fireball, The Log, Little Prince, Mini P.E.K.K.A, Wizard, Ice Spirit, Skeletons | cycle | 2.88 | 75 | 84.0% | 74%-91% |

## Worst decks

- Royal Hogs, Tombstone, Lightning, Giant Snowball, Flying Machine, Zappies, Heal Spirit, Skeletons (hybrid): 7.4% over 95
- Graveyard, Tombstone, Poison, Earthquake, Witch, Mother Witch, Skeletons, Ice Golem (graveyard): 5.0% over 80
- Electro Giant, Goblin Cage, Poison, The Log, Archer Queen, Skeleton Army, Goblins, Heal Spirit (beatdown): 4.3% over 92
- Miner, Goblin Cage, Rocket, Earthquake, Electro Dragon, Bats, Heal Spirit, Skeletons (cycle): 4.1% over 74
- Goblin Drill, Tombstone, Rocket, Giant Snowball, Zappies, Night Witch, Goblins, Skeletons (goblin_drill): 3.7% over 82

## Cards by win rate (in decks that contained them, >=30 games)

| card | games | win rate |
|---|---|---|
| Phoenix | 899 | 92.1% |
| Elixir Golem | 591 | 79.7% |
| Freeze | 82 | 72.0% |
| Inferno Dragon | 1492 | 68.6% |
| Fisherman | 475 | 67.2% |
| Hunter | 1982 | 66.4% |
| Inferno Tower | 1896 | 63.3% |
| Ice Spirit | 3908 | 62.6% |
| Royal Delivery | 2436 | 62.6% |
| Little Prince | 1531 | 62.3% |
| Royal Giant | 1116 | 62.1% |
| Bowler | 795 | 60.6% |
| Mini P.E.K.K.A | 890 | 60.3% |
| P.E.K.K.A | 882 | 60.0% |
| Musketeer | 1422 | 59.9% |
| Fire Spirit | 3090 | 59.4% |
| Balloon | 500 | 59.0% |
| Royal Hogs | 1037 | 59.0% |
| Wizard | 1058 | 58.2% |
| Electro Spirit | 3363 | 57.6% |
| Golden Knight | 557 | 57.5% |
| Skeleton King | 827 | 57.0% |
| Bomber | 232 | 56.9% |
| Fireball | 4668 | 56.3% |
| Elite Barbarians | 233 | 56.2% |

...

| Mega Knight | 470 | 37.2% |
| Dark Prince | 648 | 35.0% |
| Goblin Giant | 725 | 34.5% |
| Electro Wizard | 990 | 32.8% |
| Skeleton Dragons | 172 | 32.6% |
| Rage | 77 | 32.5% |
| Goblin Cage | 1535 | 31.3% |
| Elixir Collector | 80 | 31.2% |
| Bandit | 475 | 26.9% |
| Giant Skeleton | 89 | 15.7% |

## Archetype matchup matrix (row's win rate vs column)

| | bait | beatdown | bridge_spam | control | cycle | evolution_centric | goblin_drill | graveyard | hybrid | lavaloon | mega_knight | pekka_bridge_spam | royal_giant | siege | three_musketeers |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bait | 50% (56) | 60% (134) | 53% (47) | 53% (83) | 52% (254) | 33% (12) | 61% (67) | 83% (48) | 78% (32) | 50% (36) | 62% (13) | 67% (27) | 48% (42) | 54% (213) | 46% (37) |
| beatdown | 40% (134) | 50% (306) | 42% (80) | 46% (170) | 45% (574) | 41% (17) | 44% (133) | 73% (101) | 88% (61) | 45% (71) | 54% (26) | 51% (57) | 33% (84) | 49% (429) | 38% (73) |
| bridge_spam | 47% (47) | 57% (80) | 50% (16) | 55% (53) | 57% (150) | 25% (8) | 51% (37) | 52% (25) | 90% (19) | 55% (20) | 100% (5) | 74% (19) | 36% (28) | 62% (133) | 56% (16) |
| control | 47% (83) | 54% (170) | 45% (53) | 50% (78) | 51% (369) | 33% (12) | 54% (56) | 78% (67) | 73% (33) | 56% (52) | 67% (6) | 79% (34) | 48% (40) | 55% (279) | 33% (36) |
| cycle | 48% (254) | 55% (574) | 43% (150) | 49% (369) | 50% (1112) | 40% (35) | 48% (268) | 73% (227) | 80% (116) | 47% (170) | 57% (37) | 67% (124) | 39% (151) | 53% (926) | 35% (161) |
| evolution_centric | 67% (12) | 59% (17) | 75% (8) | 67% (12) | 60% (35) | - | 46% (11) | 88% (8) | 100% (6) | 56% (9) | 100% (1) | 100% (1) | 40% (5) | 56% (36) | 44% (9) |
| goblin_drill | 39% (67) | 56% (133) | 49% (37) | 46% (56) | 52% (268) | 55% (11) | 50% (58) | 74% (49) | 74% (27) | 64% (39) | 56% (9) | 61% (31) | 32% (31) | 53% (211) | 14% (42) |
| graveyard | 17% (48) | 27% (101) | 48% (25) | 22% (67) | 27% (227) | 12% (8) | 26% (49) | 50% (34) | 52% (23) | 33% (33) | 17% (12) | 56% (25) | 8% (37) | 30% (186) | 23% (30) |
| hybrid | 22% (32) | 12% (61) | 10% (19) | 27% (33) | 20% (116) | 0% (6) | 26% (27) | 48% (23) | 50% (14) | 24% (21) | 0% (1) | 36% (11) | 20% (20) | 29% (98) | 6% (18) |
| lavaloon | 50% (36) | 55% (71) | 45% (20) | 44% (52) | 53% (170) | 44% (9) | 36% (39) | 67% (33) | 76% (21) | 50% (22) | 40% (5) | 74% (19) | 26% (19) | 43% (123) | 28% (25) |
| mega_knight | 38% (13) | 46% (26) | 0% (5) | 33% (6) | 43% (37) | 0% (1) | 44% (9) | 83% (12) | 100% (1) | 60% (5) | 50% (4) | 50% (2) | 0% (4) | 46% (24) | 67% (3) |
| pekka_bridge_spam | 33% (27) | 49% (57) | 26% (19) | 21% (34) | 33% (124) | 0% (1) | 39% (31) | 44% (25) | 64% (11) | 26% (19) | 50% (2) | 50% (10) | 32% (22) | 35% (80) | 40% (15) |
| royal_giant | 52% (42) | 67% (84) | 64% (28) | 52% (40) | 61% (151) | 60% (5) | 68% (31) | 92% (37) | 80% (20) | 74% (19) | 100% (4) | 68% (22) | 50% (16) | 61% (133) | 45% (20) |
| siege | 46% (213) | 51% (429) | 38% (133) | 45% (279) | 47% (926) | 44% (36) | 47% (211) | 70% (186) | 71% (98) | 57% (123) | 54% (24) | 65% (80) | 39% (133) | 50% (692) | 26% (120) |
| three_musketeers | 54% (37) | 62% (73) | 44% (16) | 67% (36) | 65% (161) | 56% (9) | 86% (42) | 77% (30) | 94% (18) | 72% (25) | 33% (3) | 60% (15) | 55% (20) | 74% (120) | 50% (18) |

## Engine weights used

```json
{
 "defense": 0.948150031166059,
 "tower_damage_prevented": 0.9755322246339114,
 "offense": 0.8564601880076644,
 "support_synergy": 1.5080639741517994,
 "build_push": 0.5058149919755356,
 "cycle": 0.14945937741234347,
 "leak": 4.090829598845088,
 "reserve": 0.7030320198420038,
 "overcommit": 1.1409244443357542,
 "opp_response": 0.5565983496401554,
 "spell_cycle": 0.11475437537194665,
 "wait_bias": -0.45389742349402623
}
```
