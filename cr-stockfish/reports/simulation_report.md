# Self-play simulation report

9505 engine-vs-engine games over 232 decks in 589.1s on 4 processes. Average game 161.1s, overtime in 21%, draws 0.0%. Engine beat the scripted mid-ladder bot 73% of the time.

The simulator is a simplified proxy (see crsf/sim.py). Use these numbers to compare decks and weights against each other, not as ladder predictions.

## Best decks

| # | deck | archetype | avg elixir | games | win rate | 95% CI |
|---|---|---|---|---|---|---|
| 1 | Battle Ram, Furnace, Rocket, Royal Delivery, Inferno Dragon, Little Prince, Ice Golem, Heal Spirit | bridge_spam | 3.38 | 83 | 98.8% | 94%-100% |
| 2 | Royal Hogs, Furnace, Fireball, Giant Snowball, Phoenix, Bowler, Ice Golem, Electro Spirit | three_musketeers | 3.38 | 78 | 98.7% | 93%-100% |
| 3 | Battle Ram, Tombstone, Fireball, Barbarian Barrel, Musketeer, Hunter, Ice Spirit, Skeletons | cycle | 2.88 | 100 | 98.0% | 93%-99% |
| 4 | Battle Ram, Tombstone, Rocket, The Log, Firecracker, Fisherman, Ice Golem, Electro Spirit | siege | 3.0 | 75 | 96.0% | 89%-99% |
| 5 | Skeleton Barrel, Tombstone, Rocket, Giant Snowball, Electro Wizard, Inferno Dragon, Skeletons, Ice Spirit | siege | 3.0 | 85 | 94.1% | 87%-98% |
| 6 | Wall Breakers, Tesla, Fireball, Tornado, Executioner, Phoenix, Ice Golem, Skeletons | siege | 3.12 | 92 | 93.5% | 86%-97% |
| 7 | Elixir Golem, Tesla, Rocket, Royal Delivery, Phoenix, Firecracker, Ice Spirit, Goblins | siege | 3.25 | 92 | 93.5% | 86%-97% |
| 8 | Battle Ram, Goblin Cage, Rocket, Tornado, Dart Goblin, Bowler, Skeletons, Fire Spirit | control | 3.38 | 71 | 93.0% | 85%-97% |
| 9 | Battle Ram, Tombstone, Rocket, Tornado, Witch, Wizard, Skeletons, Fire Spirit | siege | 3.5 | 83 | 92.8% | 85%-97% |
| 10 | Battle Ram, Furnace, Fireball, Zap, Wizard, Minions, Heal Spirit, Skeletons | bridge_spam | 3.0 | 79 | 92.4% | 84%-96% |
| 11 | Skeleton Barrel, Furnace, Rocket, Royal Delivery, Mega Minion, Bats, Heal Spirit, Ice Spirit | siege | 2.88 | 87 | 92.0% | 84%-96% |
| 12 | Royal Hogs, Lightning, Barbarian Barrel, Musketeer, Phoenix, Golden Knight, Skeletons, Goblins | cycle | 3.5 | 71 | 91.5% | 83%-96% |
| 13 | Battle Ram, Tesla, Lightning, The Log, Electro Wizard, Flying Machine, Spear Goblins, Skeletons | siege | 3.38 | 83 | 90.4% | 82%-95% |
| 14 | Battle Ram, Tesla, Lightning, Arrows, Magic Archer, Musketeer, Spear Goblins, Skeletons | evolution_centric | 3.5 | 89 | 89.9% | 82%-95% |
| 15 | Battle Ram, Lightning, Earthquake, Goblin Gang, Skeleton King, Inferno Dragon, Spear Goblins, Goblins | beatdown | 3.5 | 87 | 89.7% | 82%-94% |
| 16 | Golem, Night Witch, Phoenix, Bomber, Mini P.E.K.K.A, Elite Barbarians, Arrows, Zap | beatdown | 4.12 | 76 | 89.5% | 81%-95% |
| 17 | Elixir Golem, Poison, Arrows, Hunter, Bowler, Bats, Spear Goblins, Ice Spirit | control | 3.0 | 81 | 88.9% | 80%-94% |
| 18 | Goblin Drill, Furnace, Lightning, Royal Delivery, Musketeer, Skeleton King, Fire Spirit, Heal Spirit | bridge_spam | 3.38 | 80 | 88.7% | 80%-94% |
| 19 | Ram Rider, Inferno Tower, Poison, The Log, Minions, Phoenix, Skeletons, Ice Golem | cycle | 3.25 | 85 | 88.2% | 80%-94% |
| 20 | Three Musketeers, Bomb Tower, Fireball, Arrows, Little Prince, Hunter, Heal Spirit, Electro Spirit | three_musketeers | 3.62 | 92 | 88.0% | 80%-93% |

## Worst decks

- Graveyard, Tombstone, Poison, Earthquake, Witch, Mother Witch, Skeletons, Ice Golem (graveyard): 6.2% over 80
- Electro Giant, Goblin Cage, Poison, The Log, Archer Queen, Skeleton Army, Goblins, Heal Spirit (beatdown): 5.4% over 92
- Goblin Giant, Goblin Cage, Lightning, Earthquake, Baby Dragon, Bandit, Heal Spirit, Ice Golem (beatdown): 2.7% over 73
- X-Bow, Bomb Tower, Lightning, Zap, Electro Wizard, Mighty Miner, Skeletons, Ice Golem (siege): 2.6% over 76
- Miner, Goblin Cage, Rocket, Earthquake, Electro Dragon, Bats, Heal Spirit, Skeletons (cycle): 0.0% over 74

## Cards by win rate (in decks that contained them, >=30 games)

| card | games | win rate |
|---|---|---|
| Battle Ram | 1091 | 90.1% |
| Phoenix | 899 | 89.1% |
| Skeleton Barrel | 498 | 84.1% |
| Giant Skeleton | 89 | 83.1% |
| Elixir Golem | 591 | 77.2% |
| Rascals | 78 | 74.4% |
| Golden Knight | 557 | 69.8% |
| Skeleton King | 827 | 69.0% |
| Fisherman | 475 | 67.2% |
| Royal Ghost | 402 | 67.2% |
| Inferno Dragon | 1492 | 67.1% |
| Musketeer | 1422 | 64.8% |
| Hunter | 1982 | 62.5% |
| Ice Spirit | 3908 | 62.4% |
| Wizard | 1058 | 61.4% |
| Mini P.E.K.K.A | 890 | 60.9% |
| Fire Spirit | 3090 | 60.4% |
| Royal Delivery | 2436 | 60.2% |
| Inferno Tower | 1896 | 60.0% |
| Bowler | 795 | 59.1% |
| P.E.K.K.A | 882 | 57.9% |
| Arrows | 1646 | 57.5% |
| Dart Goblin | 920 | 57.5% |
| Little Prince | 1531 | 57.3% |
| Bomber | 232 | 57.3% |

...

| Mega Knight | 470 | 36.4% |
| Dark Prince | 648 | 34.4% |
| Electro Giant | 924 | 33.9% |
| Archer Queen | 755 | 33.6% |
| Electro Dragon | 1355 | 32.8% |
| Minion Horde | 1077 | 32.2% |
| Skeleton Dragons | 172 | 30.2% |
| Goblin Cage | 1535 | 29.4% |
| Elixir Collector | 80 | 26.3% |
| Rage | 77 | 26.0% |

## Archetype matchup matrix (row's win rate vs column)

| | bait | beatdown | bridge_spam | control | cycle | evolution_centric | goblin_drill | graveyard | hybrid | lavaloon | mega_knight | pekka_bridge_spam | royal_giant | siege | three_musketeers |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bait | 50% (56) | 63% (134) | 36% (47) | 43% (83) | 51% (254) | 25% (12) | 54% (67) | 83% (48) | 88% (32) | 44% (36) | 69% (13) | 67% (27) | 50% (42) | 44% (213) | 49% (37) |
| beatdown | 37% (134) | 50% (306) | 22% (80) | 35% (170) | 43% (574) | 29% (17) | 45% (133) | 78% (101) | 79% (61) | 44% (71) | 38% (26) | 51% (57) | 36% (84) | 42% (429) | 40% (73) |
| bridge_spam | 64% (47) | 78% (80) | 50% (16) | 74% (53) | 71% (150) | 50% (8) | 68% (37) | 80% (25) | 90% (19) | 75% (20) | 80% (5) | 68% (19) | 64% (28) | 68% (133) | 56% (16) |
| control | 57% (83) | 65% (170) | 26% (53) | 50% (78) | 56% (369) | 33% (12) | 64% (56) | 82% (67) | 79% (33) | 56% (52) | 50% (6) | 68% (34) | 60% (40) | 56% (279) | 36% (36) |
| cycle | 49% (254) | 57% (574) | 29% (150) | 44% (369) | 50% (1112) | 23% (35) | 54% (268) | 74% (227) | 82% (116) | 48% (170) | 54% (37) | 63% (124) | 36% (151) | 45% (926) | 40% (161) |
| evolution_centric | 75% (12) | 71% (17) | 50% (8) | 67% (12) | 77% (35) | - | 82% (11) | 100% (8) | 100% (6) | 78% (9) | 0% (1) | 100% (1) | 80% (5) | 86% (36) | 78% (9) |
| goblin_drill | 46% (67) | 55% (133) | 32% (37) | 36% (56) | 46% (268) | 18% (11) | 50% (58) | 74% (49) | 74% (27) | 62% (39) | 67% (9) | 61% (31) | 36% (31) | 43% (211) | 17% (42) |
| graveyard | 17% (48) | 22% (101) | 20% (25) | 18% (67) | 26% (227) | 0% (8) | 26% (49) | 50% (34) | 39% (23) | 30% (33) | 33% (12) | 48% (25) | 19% (37) | 26% (186) | 23% (30) |
| hybrid | 12% (32) | 21% (61) | 10% (19) | 21% (33) | 18% (116) | 0% (6) | 26% (27) | 61% (23) | 50% (14) | 19% (21) | 0% (1) | 18% (11) | 5% (20) | 24% (98) | 6% (18) |
| lavaloon | 56% (36) | 56% (71) | 25% (20) | 44% (52) | 52% (170) | 22% (9) | 38% (39) | 70% (33) | 81% (21) | 50% (22) | 60% (5) | 79% (19) | 32% (19) | 42% (123) | 36% (25) |
| mega_knight | 31% (13) | 62% (26) | 20% (5) | 50% (6) | 46% (37) | 100% (1) | 33% (9) | 67% (12) | 100% (1) | 40% (5) | 50% (4) | 100% (2) | 0% (4) | 58% (24) | 67% (3) |
| pekka_bridge_spam | 33% (27) | 49% (57) | 32% (19) | 32% (34) | 37% (124) | 0% (1) | 39% (31) | 52% (25) | 82% (11) | 21% (19) | 0% (2) | 50% (10) | 50% (22) | 36% (80) | 33% (15) |
| royal_giant | 50% (42) | 64% (84) | 36% (28) | 40% (40) | 64% (151) | 20% (5) | 64% (31) | 81% (37) | 95% (20) | 68% (19) | 100% (4) | 50% (22) | 50% (16) | 49% (133) | 50% (20) |
| siege | 56% (213) | 58% (429) | 32% (133) | 44% (279) | 55% (926) | 14% (36) | 57% (211) | 74% (186) | 76% (98) | 58% (123) | 42% (24) | 64% (80) | 51% (133) | 50% (692) | 43% (120) |
| three_musketeers | 51% (37) | 60% (73) | 44% (16) | 64% (36) | 60% (161) | 22% (9) | 83% (42) | 77% (30) | 94% (18) | 64% (25) | 33% (3) | 67% (15) | 50% (20) | 57% (120) | 50% (18) |

## Engine weights used

```json
{
 "defense": 0.9737299580304896,
 "tower_damage_prevented": 0.9876903485576395,
 "offense": 0.9254513428633968,
 "support_synergy": 1.1650139813481293,
 "build_push": 0.5274450166477493,
 "cycle": 0.19329988192724243,
 "leak": 3.503211212093165,
 "reserve": 0.6494761057230684,
 "overcommit": 1.0681406481993625,
 "opp_response": 0.6672920497893889,
 "spell_cycle": 0.13119891884383802,
 "wait_bias": -0.22694871174701312
}
```
