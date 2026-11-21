# Tomorrow's checklist — live card placement on Google Play Games

Everything below was asked for in the first session or discovered while building. Work top-down.

## 0. Start-of-day sanity (5 min)
- [ ] `cd cr-stockfish && python -m pytest tests -q` (62 tests) and `python -m crsf bench` (25/25)
- [ ] `python -m crsf gui --demo` opens the dashboard and shows plays on synthetic frames

## 1. See the real game (the part that must work first)
- [ ] Open Clash Royale in Google Play Games, enter Training Camp.
- [ ] `python -m crsf calibrate --window "Clash Royale" --out preview.png`
      Check: green boxes on the 4 cards, cyan on the elixir bar, yellow on tower HP numbers. The layout in
      `crsf/data/layout.json` was measured from your screenshot (556x990 game area), so it should be close.
      If the frame is wrong, pass `--bbox x,y,w,h --no-auto-frame` (the command prints its guess).
- [ ] Elixir reading matches the number on screen at 0, 5 and 10 (watch `python -m crsf advise --window "Clash Royale" --no-overlay`).
- [ ] `python -m crsf learn-cards --window "Clash Royale"` then `python -m crsf label <crop> <card_key>` for all 8 cards + next slot.
      Then the hand shows correctly in the GUI. (Card keys: `python -m crsf cards`.)
- [ ] Health bars: place troops in training camp; units should appear on the GUI minimap with the right side and HP.
      Tune HSV thresholds in `crsf/vision/healthbars.py` if red/blue bars are missed.
- [ ] Type `o <card>` right after the trainer plays something: the new red unit gets labelled (classifier classes count goes up).
- [ ] Optional: Tesseract installed → tower HP and clock read automatically (`pip install pytesseract` + Tesseract binary).

## 2. Make it click without touching your mouse
- [ ] GUI → Input "Click without moving my mouse (window messages)" → Start → Arm autoplay with Dry run ON.
      Watch the log for sensible plays for a whole training match.
- [ ] Dry run OFF in training camp. If nothing happens in-game, Google Play Games ignores posted messages:
      switch to "Real mouse clicks (cursor restored)" (`pip install pyautogui`). ADB is only possible with an emulator
      (LDPlayer/BlueStacks) or a phone over USB — that is the fully independent option.
- [ ] Verify tap accuracy: the gold marker on the minimap and the in-game placement agree. If placements are shifted,
      adjust `arena` / `river_frac` in layout.json (tiles_to_pixel is the inverse of arena_to_tiles).

## 3. Card knowledge completeness (your ask: "know exactly how every card works, heroes and everything")
- [ ] `knowledge/mechanics.json` is seeded (123 cards, evolutions list, tower troops, heroes where found) but mostly
      `verified: false`. Research and fill: every champion ability (cost, effect, cooldown, single-use since Aug 2026),
      every evolution (cycles + effect), every Hero form (18 listed), tower troops (Dagger Duchess dagger count,
      Royal Chef pancakes, Cannoneer ground-only), spawn-on-death units, charge mechanics, ramp damage, death damage.
- [ ] Decide how the engine should use them: hero/evo flags on the opponent's cards from the `d` command
      (e.g. `d evo knight, hero musketeer, ...`), counter adjustments for evolutions (Evo Skeletons, Evo RG recoil, Evo Knight).
- [ ] Re-verify the 28 stat corrections that were applied unverified (`knowledge/card_updates.json`, `verified:false`).
- [ ] Goblins count (3 vs 4), Goblin Curse numbers, Vines Oct-2025 numbers, Spirit Empress forms — flagged uncertain.

## 4. Timings and techniques (your ask: "perfect timings to block troops and cool techniques")
- [ ] `knowledge/techniques.json` (research agent output) is loaded by the engine: distance-timed techniques delay a
      counter until the attacker reaches the trigger tile; matching techniques show as "Technique:" notes.
      Review the entries, fix tiles that look wrong, add the ones you know from pro play.
- [ ] Deploy delay: troops take ~1 s to spawn. Add a per-card deploy-time to the timing gate (play 1 tile earlier).

## 5. Simulation and tuning (your ask: "as many simulations as it takes")
- [ ] Read `reports/simulation_report.md` and `reports/tuning_log.json` from tonight's run.
- [ ] The simulator is a proxy. Biggest remaining gaps: pathing/pushback, tornado pull, clone/rage/heal/mirror,
      champion abilities, evolutions, heroes, exact spawn timings. Each one you add makes tuning more trustworthy.
- [ ] Add more puzzles to `benchmarks/puzzles.json` from your own games (they gate tuning so it can't unlearn fundamentals).
- [ ] Run `python -m crsf tune --iters 20 --pairs 100` overnight when the sim is better.

## 6. Learning from pro games
- [ ] Play a pro's match video full-screen, `python -m crsf learn --monitor 1`, type `o <card>` on their opponent's plays.
- [ ] `python -m crsf priors` → placements the pros used become candidates with a bonus. Aim for 50 games.

## 7. Known limits to keep in mind
- Research pages (Deck Shop, wiki, RoyaleAPI) could not be fetched from the build environment; counters/placements come
  from search summaries + model knowledge. Treat qualities as expert estimates until checked against a live source.
- Unit identity without a trained detector depends on labelling; ClashRoyaleBuildABot's MIT ONNX detector
  (`units_M_480x352.onnx` + class list, in its GitHub repo) can be dropped in with `--onnx ... --onnx-classes ...`
  for the 101 older cards.
- Supercell bans third-party automation. Secondary account only.

## 8. What tonight's simulation said (reports/simulation_report.md, reports/tuning_log.json)
- 10 tuning iterations x 6 candidates x 120 games: one weight set promoted (63% vs baseline, still 25/25 puzzles) →
  `knowledge/weights.json` (slightly more support synergy, less fear of the opponent's reply, a small bias toward acting).
- 9,505 engine-vs-engine games over 232 decks; engine beat the scripted mid-ladder bot 73%.
- Simulator artifacts to fix before trusting deck rankings: Battle Ram decks win ~95%+ (charge x2 + death-spawn
  Barbarians + no pathing/pushback is too strong), Graveyard and "hybrid" decks lose ~75% (skeleton spawn pacing and
  no splash-at-tower modelling), Inferno Dragon everywhere (ramp helps but it still never gets reset in the sim unless
  zapped). Add: pushback/knockback, tornado pull, retarget on stun, spell-on-graveyard, deploy delay (~1 s), king-tower
  activation from splash.
