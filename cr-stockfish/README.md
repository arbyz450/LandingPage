# CR Stockfish — a Clash Royale engine that advises, learns, and can play

`crsf` reads a Clash Royale match from the screen (emulator or Android phone),
reconstructs the game state, ranks every card × placement the way Stockfish
ranks moves, explains why, and — over ADB — can tap the plays itself.

```
[AUTOPLAY ON] plays: 7
last: Inferno Tower @ def_left (3s ago)

eval +3.2   (towers +0.0, elixir +4.0, field -0.8)
you 8.0  |  opp ~2.0  |  2:05 single
hand: Skeleton Army, The Log, Inferno Tower, Hog Rider
threats: Giant (left, y13, 3.8), Witch (left, y15, 3.8)

1. Inferno Tower -> left defensive pocket (in front of tower)  [+14.2]
      counters Giant (93%); counters Witch (98%)
2. Skeleton Army -> left defensive pocket (in front of tower)  [+8.9]

Opp hand: Zap, Skeleton Army, Musketeer, Mini P.E.K.K.A
Opp archetype: beatdown. Defend cheaply, punish the opposite lane when the tank drops.
```

## Read this first: what is real and what is not

| Claim | Reality |
|---|---|
| "Plays like a pro" | It plays like a strong, explainable rule-based engine with a researched counter matrix, pro placement library, cycle/elixir tracking and a one-ply look at the opponent's reply. It does not reach pro level. No Clash Royale bot does. |
| "Never makes a mistake" | No engine achieves that, Stockfish included. This one makes fewer, and tells you why it chose a move so you can correct it in `knowledge/`. |
| "Learned from 50 pro videos" | Nothing here watched a video. `crsf learn` extracts *your* or a pro's placements while their match plays on your screen, and `crsf priors` turns those into placement statistics the engine uses. The research in `knowledge/` was done from text sources and model knowledge (see "Knowledge base" for how it was built). |
| "Sees the whole board" | Units are found by their health bars (position, side, HP) without any ML. Their identity is learned over time: each time you type `o hog` or you play a card, the newly appeared unit's crop is labelled. Until a unit is recognised, it is a generic `unknown` threat. An Ultralytics YOLO plug-in exists for a trained detector. |
| "Plays for me" | Yes, through ADB (`crsf play`): emulators and real Android phones. See the Terms-of-Service note. iOS cannot be automated without a jailbreak. |

**Terms of Service.** Supercell's terms prohibit bots and third-party tools
that give an advantage. Reading the screen to *advise* is lower risk than
tapping for you, but both can get an account banned. Use a secondary account,
friendly battles and training camp. The code never modifies the game or its
memory; it only looks at pixels and sends taps.

## Which emulator?

Any Android target that exposes ADB works. Recommended, in order:

| Target | Why | Setup |
|---|---|---|
| **LDPlayer 9** (Windows) | Light, stable ADB, easy portrait mode | Settings → Other → *ADB debugging: Open local connection*. Display: Phone 1080×1920, 240 DPI. Port 5555. |
| **BlueStacks 5** (Windows) | Most used by bot projects | Settings → Advanced → *Android Debug Bridge: on*. Display: Portrait 1080×1920. Port 5555 (changes per instance; the settings page shows it). |
| **MEmu / Nox / MuMu** | Fine | ADB on by default: MEmu 21503, Nox 62001, MuMu 7555. |
| **Real Android phone** | Exact game, no emulator detection | Developer options → USB debugging; plug in USB (or `adb tcpip 5555` once, then `--connect <phone-ip>:5555` over Wi-Fi). Mirror with `scrcpy` if you want to watch. |
| Google Play Games on PC | Not recommended | No ADB; screen capture only (`advise --monitor 1` works, `play` does not). |
| macOS | Use a phone over ADB, or the Android Studio emulator (ARM translation, slow). BlueStacks Air has no ADB. |

Install Android platform-tools so `adb` is on your PATH, then `adb devices`
must list the target as `device`.

## Install

```bash
cd cr-stockfish
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install pytesseract pygetwindow               # optional: tower HP/clock OCR, window capture
python -m pytest tests -q
```

Python 3.10+. Linux may need `sudo apt install python3-tk tesseract-ocr`.

## Five-minute start

```bash
# 1. Engine only, no screen (a position file is the Clash Royale "FEN"):
python -m crsf analyze examples/state_giant_push.json

# 2. Point it at the emulator and check the HUD boxes land on the right things:
python -m crsf calibrate --emulator ldplayer --out preview.png

# 3. Teach it your 8 cards once (crops of the hand slots -> templates/cards/<key>.png):
python -m crsf learn-cards --emulator ldplayer          # saves unknown slot crops while you play
python -m crsf label templates/unlabeled/slot1_1700000000.png hog_rider

# 4. Advise (overlay window) ...
python -m crsf advise --emulator ldplayer
# ... or let it play. Start with a dry run: it decides and logs, but never taps.
python -m crsf play --emulator ldplayer --dry-run
python -m crsf play --emulator ldplayer
```

Replace `--emulator ldplayer` with `--emulator bluestacks`, `--connect 127.0.0.1:5555`,
`--emulator phone` (USB), or capture the screen instead with `--monitor 1`
(advise/learn only).

### In-match commands (overlay box or terminal)

| Command | Meaning |
|---|---|
| `o hog` | opponent played Hog Rider → cycle + elixir tracker, and the enemy unit that just appeared is labelled `hog_rider` |
| `u` | undo the last opponent play |
| `d giant,witch,zap,...` | set the opponent's deck (archetype detection kicks in) |
| `m hog,musk,log,...` | set your deck |
| `e 4` / `t 2:30` / `t 1:00 ot` | override opponent elixir / match clock |
| `x balloon opp right` / `c` | place / clear a manual unit |
| `p` | (play) pause or resume autoplay |
| `r` | reset for a new match |

Your elixir, hand, your own cycle, the opponent's cycle and elixir, unit
positions and HP are automatic. Opponent card *names* are the one thing you
type, two keystrokes each; the classifier learns their sprites from that.

## Learning from gameplay (yours or a pro's)

```bash
python -m crsf learn --monitor 1          # play a pro's match video full-screen, or your own games
python -m crsf priors                     # -> knowledge/priors.json
```

`learn` watches the hand like it watches yours: when a card leaves the hand
and a new friendly health bar appears, that is a deploy event with its context
(lane, enemy presence in that lane, elixir, phase). `priors` clusters those per
card and situation (offense / defense / counter-push), mirrored onto one lane.
The engine then proposes those exact tiles as candidate placements with a
bonus proportional to how often pros used them. Type `o <card>` during the
video and enemy sprites get labelled as well, which makes the classifier
useful against those decks later.

Log every match you play with `play`/`advise` too: they append deploy events
to `data/events/` automatically.

## Knowledge base (`knowledge/`)

| File | Content | Origin |
|---|---|---|
| `counters_a.json`, `counters_b.json` | For each of 120 cards: best counters with a 0–1 quality and a note, what it counters, placement tips | Web search summaries (Deck Shop, wiki, RoyaleAPI, TrophyCoach) plus model knowledge; direct page fetches were blocked in the build environment, so treat qualities as expert estimates |
| `placements.json` | Named pro placements in tile coordinates per card and situation (pig push, 4-3 Tesla, king activation, kiting, pulls, predictions) and the mechanics behind them | same |
| `strategy.json` | Principles (elixir counting, opening, spell value, phases, tiebreak), archetypes with signature cards, matchup plans, tower-troop notes | same |
| `meta_decks.json` | Current meta decks with archetypes | same |
| `card_updates.json` | Stat corrections, new cards, evolutions, tower troops | same |
| `priors.json` | Learned placement statistics | your `crsf learn` runs |

Everything is plain JSON. Fix a quality, add a placement, change a weight in
`crsf/engine.Weights`; nothing is compiled in.

## How the engine thinks

1. **Threats.** Each enemy unit gets a weight: remaining elixir value × urgency
   (1.5 at your king tower, 0.7 at the bridge, 0.2 in their back yard; siege
   buildings count as emergencies).
2. **Counter score** (0–1) per defender × attacker: a duel model (time-to-kill
   both ways with overkill, ranged free hits, building pull) blended 35/65
   with the curated matrix when one exists, plus categorical rules (splash vs
   swarm, resets vs charges and infernos, anti-air, building-targeters).
3. **Candidate moves.** Generic zones (back, defensive pockets, centre, bridge,
   kite), every named pro placement for the card, learned prior placements,
   spells on each enemy unit, prediction spots and towers, and *wait*.
4. **Score in elixir-equivalents.** Defence (counter × lane fit × value ×
   urgency) + tower damage prevented + placement bonus (pro placement matches
   the situation and the attacker it was designed for) + offence (win
   condition at the bridge valued by the opponent's predicted hand, their
   elixir, tower HP, a tank already walking, opposite-lane punishes; slow
   pushes from the back; support behind tanks; cycle toward your win
   condition; opening discipline) + elixir management (leak, reserve-a-counter,
   over-commit, spell cycling, tower finishes, tiebreak chip) − cost −
   opponent's best reply from their predicted hand within their elixir.
5. **Archetype and phase.** The opponent's known cards are matched to an
   archetype; weights shift (hold counters vs beatdown, don't over-commit vs
   cycle, pressure vs siege, keep the log vs bait) and the matchup plan is
   shown. Overtime compares lowest tower HP and switches between "must deal
   damage" and "defend the lead".
6. **Autoplay policy.** Plays only a clearly positive move that is stable
   across frames (or urgent), affordable with margin for bar-read error, rate
   limited, never the same card twice in a row.

## Adding a trained detector

Health bars give positions; a trained model gives identities immediately.
Train Ultralytics YOLO on Clash Royale screenshots (public datasets exist on
Roboflow Universe) and run with `--yolo weights.pt --yolo-classes classes.json`
where the JSON maps class names to `{"card": key, "side": "me"|"opp"|"auto"}`.

## Can this be a mobile app that plays on my phone?

- **Android, phone + PC:** yes, today. The PC runs `crsf play --emulator phone`
  (USB) or `--connect <ip>:5555` (Wi-Fi). The phone does nothing special.
- **Android, fully on-device:** technically possible (an AccessibilityService
  to tap, MediaProjection to capture, the engine ported to Kotlin or run via
  Chaquopy/Termux). It would never be allowed on the Play Store and would
  need sideloading. Not built here.
- **iOS:** no. No screen capture plus input injection without a jailbreak.

## Layout

```
crsf/
  cards.py        card database + "unknown" placeholder     crsf/data/cards.json
  state.py        GameState / Unit / Tower (18x32 tile grid) crsf/data/layout.json
  tracker.py      cycle + elixir tracking
  knowledge.py    loads knowledge/*.json
  learn.py        deploy events -> placement priors
  engine.py       evaluation, candidates, recommendations
  autoplay.py     when to actually play
  advisor.py      live loop, unit tracking, auto-labelling, commands
  overlay.py      Tk always-on-top window
  act/adb.py      ADB capture + taps (emulators, phones)
  vision/         capture, layout, elixir, hand, healthbars, unit_classifier, ocr, units(YOLO)
knowledge/        researched counters, placements, strategy, meta, learned priors
tests/            54 tests, synthetic frames included
templates/        your labelled card and unit crops (not committed)
data/events/      deploy event logs (not committed)
```
