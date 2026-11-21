"""Download official card icons so the hand is recognised with no manual labelling.

Icons come from RoyaleAPI's public CDN (full card images with frame, which is
what the in-game hand slots show). Several URL patterns are tried per card;
cards that cannot be fetched are reported so they can be labelled by hand
with ``crsf learn-cards`` / ``crsf label``.
"""
from __future__ import annotations

import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from .cards import CardDB, default_db

SLUG_OVERRIDES = {
    "log": "the-log", "pekka": "pekka", "mini_pekka": "mini-pekka", "x_bow": "x-bow",
    "giant_snowball": "giant-snowball", "royal_delivery": "royal-delivery", "electro_wizard": "electro-wizard",
    "goblin_demolisher": "goblin-demolisher", "spirit_empress": "spirit-empress", "boss_bandit": "boss-bandit",
    "three_musketeers": "three-musketeers", "skeleton_army": "skeleton-army", "minion_giant": "minion-giant",
}
URL_PATTERNS = [
    "https://cdn.royaleapi.com/static/img/cards-150/{slug}.png",
    "https://cdn.royaleapi.com/static/img/cards/{slug}.png",
    "https://cdn.royaleapi.com/static/img/cards-75/{slug}.png",
]
UA = {"User-Agent": "Mozilla/5.0 (crsf card icon fetch)"}


def slugs_for(key: str) -> List[str]:
    base = SLUG_OVERRIDES.get(key, key.replace("_", "-"))
    out = [base]
    alt = key.replace("_", "")
    if alt not in out:
        out.append(alt)
    return out


def fetch_icons(dest: Path, db: CardDB = None, timeout: float = 8.0, only: Iterable[str] = ()) -> Tuple[List[str], Dict[str, str]]:
    db = db or default_db()
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    ok: List[str] = []
    failed: Dict[str, str] = {}
    keys = list(only) or [c.key for c in db if c.key != "unknown"]
    for key in keys:
        target = dest / f"{key}.png"
        if target.exists() and target.stat().st_size > 500:
            ok.append(key)
            continue
        err = ""
        for slug in slugs_for(key):
            for pat in URL_PATTERNS:
                url = pat.format(slug=slug)
                try:
                    req = urllib.request.Request(url, headers=UA)
                    with urllib.request.urlopen(req, timeout=timeout) as r:
                        data = r.read()
                    if len(data) > 500 and data[:4] == b"\x89PNG":
                        target.write_bytes(data)
                        ok.append(key)
                        break
                    err = "not a png"
                except Exception as exc:   # noqa: BLE001 - report and continue
                    err = str(exc)[:80]
            if target.exists():
                break
        if not target.exists():
            failed[key] = err or "no url worked"
    return ok, failed
