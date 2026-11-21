"""crsf - a Stockfish-style analysis engine and live advisor for Clash Royale.

Package layout
--------------
cards    - card database (stats, roles) loaded from data/cards.json
state    - GameState / Unit / Towers data model
tracker  - opponent cycle + elixir tracking
engine   - move generation, evaluation and ranked recommendations
vision   - screen capture and HUD readers (elixir, hand, tower HP, clock)
advisor  - the live loop tying vision -> state -> engine -> overlay
"""

__version__ = "0.1.0"
