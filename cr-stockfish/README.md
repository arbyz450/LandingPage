# CR Stockfish — a Clash Royale analysis engine and live advisor

`crsf` watches a Clash Royale match on your screen (emulator or mirrored phone),
reconstructs the game state, and tells you the best play — Stockfish-style:
every candidate card × placement is scored in elixir-equivalents, with reasons.

```
eval +3.2   (towers +0.0, elixir +4.0, field -0.8)
you 8.0  |  opp ~2.0  |  2:05 single
hand: Skeleton Army, The Log, Inferno Tower, Hog Rider
threats: Giant (left, 3.8), Witch (left, 3.8)

1. Inferno Tower -> left defensive pocket (in front of tower)  [+14.2]
      counters Giant (93%); counters Witch (98%)
2. Skeleton Army -> left defensive pocket (in front of tower)  [+8.9]
      counters Giant (91%)

Opp hand: Zap, Skeleton Army, Musketeer, Mini P.E.K.K.A
Opp cycling back: Giant, Witch
```

It reads only pixels and never touches the game (no input automation, no memory
reading, no modified client). Even so, Supercell's Terms of Service forbid
third-party tools that give an advantage in live play; use this for practice,
replay review and friendly battles, at your own risk.

## What it does today

| Layer | Status |
|---|---|
| Engine: move generation, counter model, elixir management, cycle/elixir tracking, 1-ply opponent response, position eval | Working, tested (`tests/`) |
| Vision: 9:16 game-frame detection, elixir bar, 4 hand slots + next card (template matching), greyed-card detection | Working, tested on synthetic frames; needs one-time card labelling on your setup |
| Vision: tower HP and clock | Works when Tesseract is installed; otherwise towers are assumed full and a wall-clock timer is used |
| Vision: troops on the arena | Pluggable. Ships with a YOLO wrapper (`--yolo`) but no trained weights; without it you place units by hand (`x balloon opp right`) or get cycle/elixir/push-timing advice only |
| Opponent plays | Typed in (`o hog`) — two keystrokes per opponent card; the tracker does the rest |
| Overlay | Always-on-top Tk window, or terminal mode (`--no-overlay`) |

## Install

```bash
cd cr-stockfish
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# optional
pip install pytesseract pygetwindow                # + install the Tesseract binary
python -m pytest tests -q
```

Python 3.10+. On Linux, `tkinter` may need `sudo apt install python3-tk`.

## Quick start (no screen needed)

Analyse a position from JSON, exactly like feeding Stockfish a FEN:

```bash
python -m crsf analyze examples/state_giant_push.json
python -m crsf analyze examples/state_quiet_punish.json --json
python -m crsf cards musk            # browse the card database
```

See `crsf/state.py` for the schema. Coordinates are arena tiles: x 0..18
(left→right), y 0..32 (your king tower → theirs), river at y = 16.

## Live advisor setup

1. **Run the game** in an emulator (BlueStacks, LDPlayer, Google Play Games) or
   mirror your phone (scrcpy). Keep the game window fully visible.
2. **Calibrate** — take a screenshot during a battle and check the HUD boxes:
   ```bash
   python -m crsf calibrate --monitor 1 --out calibration_preview.png
   ```
   Open the preview. Green boxes must sit on the four hand cards, the cyan box on
   the elixir bar, yellow boxes on tower-HP numbers. If the game frame was
   detected wrongly, pass `--bbox x,y,w,h --no-auto-frame` (the command prints
   its guess). If boxes are slightly off, copy `crsf/data/layout.json`, adjust
   the fractions and pass `--layout my_layout.json` to every command.
3. **Teach it your cards** (once per deck). While playing or on a screenshot:
   ```bash
   python -m crsf learn-cards --monitor 1          # saves unknown slot crops
   python -m crsf label templates/unlabeled/slot1_1700000000.png hog_rider
   ```
   Label each of your 8 cards (and the next-card slot). Templates live in
   `templates/cards/<card_key>.png`; card keys come from `python -m crsf cards`.
4. **Advise**:
   ```bash
   python -m crsf advise --monitor 1                # overlay window
   python -m crsf advise --monitor 1 --no-overlay   # terminal
   python -m crsf advise --window "BlueStacks"      # by window title (pygetwindow)
   ```

### During a match

Type into the overlay's box (or the terminal):

| Command | Meaning |
|---|---|
| `o hog` | opponent played Hog Rider (prefix/fuzzy names work) |
| `u` | undo the last opponent play |
| `d giant,witch,zap,...` | set the opponent's deck if you already know it |
| `m hog,musk,log,...` | set your deck (enables "cycle toward win condition") |
| `e 4` | override the opponent's elixir estimate |
| `t 2:30` / `t 1:00 ot` | set the clock when OCR is unavailable |
| `x balloon opp right` | place an enemy unit manually (no detector) |
| `c` | clear manual units |
| `r` | reset for a new match |

Everything else is automatic: your elixir, your hand, your cycle (detected from
hand changes), the opponent's cycle and elixir estimate, and the recommendations.

### Replaying screenshots

```bash
python -m crsf advise --monitor 1 --record recordings/
python -m crsf replay recordings/ -c "d giant,witch,zap"
```

## How the engine thinks

* **Threats** — each enemy unit gets a weight: remaining elixir value × how
  close it is to your towers (siege buildings and anything past the river count
  as urgent).
* **Counter score** (0–1) — a duel model (time-to-kill both ways, with overkill,
  ranged free hits and building pull) plus categorical rules: splash vs swarm,
  swarm vs splash, resets vs charges/infernos, anti-air vs air, buildings vs
  building-targeters.
* **Defense** — Σ counter × lane fit × threat value, plus the tower damage prevented.
* **Offense** — win conditions at the bridge are worth more when the opponent's
  *predicted hand* has no counter, when they are low on elixir, into a weak
  tower, or behind a surviving tank. Tanks at the back start slow pushes in
  single elixir; cheap cards cycle toward your win condition.
* **Elixir management** — leak penalties, "keep enough to answer their Golem",
  over-commit penalties, spell cycling at 10 elixir, tower-finish detection.
* **Opponent response** — a 1-ply look at what they can play back from their
  predicted hand within their estimated elixir.
* **Cycle tracking** — the four most recently played distinct cards are out of
  hand; everything else known is in hand; the oldest comes back next.

Weights are in `crsf/engine.Weights`; card stats and roles are in
`crsf/data/cards.json` (level-11 approximations — edit freely).

## Adding unit detection

Train a YOLO model on Clash Royale screenshots (several labelled datasets exist
on Roboflow; Ultralytics trains one in an afternoon on a consumer GPU), then:

```bash
pip install ultralytics
python -m crsf advise --monitor 1 --yolo weights.pt --yolo-classes classes.json
```

`classes.json` maps model class names to cards and sides:
`{"giant": {"card": "giant", "side": "auto"}, "opp_hog": {"card": "hog_rider", "side": "opp"}}`.
With `"auto"`, the side comes from the health-bar colour above the box.

## Layout

```
crsf/
  cards.py      card database + lookup          crsf/data/cards.json  stats (edit me)
  state.py      GameState / Unit / Tower         crsf/data/layout.json HUD regions (calibrate me)
  tracker.py    cycle + elixir tracking
  engine.py     evaluation and recommendations
  advisor.py    live loop, commands, text rendering
  overlay.py    Tk always-on-top window
  vision/       capture, layout, elixir, hand, ocr, units
tests/          pytest suite with synthetic frames
examples/       state JSON files for `analyze`
templates/      your labelled card crops (not committed)
```
