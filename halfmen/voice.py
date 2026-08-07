"""Turning what somebody said into a player.

The matching lives in Python rather than in the browser so it can be tested
against how speech actually mangles these names, which is badly and predictably.
The browser only captures audio and hands over a transcript.

Two rules the hard way, both from watching the first version get it wrong:

  * Compare word by word, never against one flattened string. "puka nakua"
    concatenates to "pukanakua", which contains "kanak" - and a board that
    drafted Jaren Kanak off that would be very hard to explain.
  * Use the first name to break surname ties. "amon ra saint brown" hits Brown
    twice over, and A.J. Brown is not who anyone meant.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from .names import normalize_name

# Commit outright at or above this, when nothing else is close.
SURE = 0.80
SURE_MARGIN = 0.08
# Below this it is not a guess worth offering at all.
FLOOR = 0.62


def _lev(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a or not b:
        return max(len(a), len(b))
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return 1.0 - _lev(a, b) / float(max(len(a), len(b)))


def tokens(text: str) -> List[str]:
    """Spoken words, plus every adjacent pair joined.

    Speech splits names as readily as it runs them together - "Achane" comes
    back as "a shane", "St. Brown" as "saint brown" - so the joins have to be
    candidates too or half the roster is unsayable.
    """
    raw = [normalize_name(w) for w in re.split(r"[^A-Za-z']+", text.lower())]
    raw = [w for w in raw if w]
    out = [w for w in raw if len(w) > 2]
    out += [raw[i] + raw[i + 1] for i in range(len(raw) - 1)]
    return out


def match(text: str, players: List[Dict], exclude=()) -> Optional[Dict]:
    """Best player for a transcript, or None.

    Returns {player, score, margin, sure}. `sure` is the caller's licence to act
    without asking: a strong match that nothing else came close to.
    """
    said = normalize_name(text)
    if len(said) < 3:
        return None
    words = tokens(text)
    if not words:
        return None
    gone = {str(x) for x in exclude}

    best = None
    best_score = 0.0
    runner_up = 0.0
    for p in players:
        if str(p.get("id", p.get("name"))) in gone:
            continue
        parts = [normalize_name(x) for x in str(p["name"]).split()]
        parts = [x for x in parts if x]
        if not parts:
            continue
        last, first = parts[-1], parts[0]

        if said.find(normalize_name(p["name"])) >= 0:
            score = 1.0
        else:
            last_score = max((similarity(w, last) for w in words), default=0.0)
            if last_score < 0.75:          # the surname has to land
                continue
            first_score = max((similarity(w, first) for w in words), default=0.0)
            score = (last_score * 0.7 + first_score * 0.3) if first_score \
                else last_score * 0.8

        if score > best_score:
            runner_up = best_score
            best_score, best = score, p
        elif score > runner_up:
            runner_up = score

    if best is None or best_score < FLOOR:
        return None
    margin = best_score - runner_up
    return {"player": best, "score": best_score, "margin": margin,
            "sure": best_score >= SURE and margin >= SURE_MARGIN}
