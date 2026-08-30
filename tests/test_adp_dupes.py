"""One player must not occupy two rows on the consensus board.

Seven ADP sources cannot agree how to spell a name. When six of them say "Ken
Walker" and one says "Kenneth Walker III", the board grew two rows for one
player: the six-source consensus under a key nothing matched, and the
single-source row under the key Sleeper's roster resolved to. Two things broke
at once, both silently - he appeared on the wire as a never-drafted free agent
while sitting on a roster, and every keeper price for him came off the rank
one source believed instead of the rank six did.

The failure mode is that nothing errors. A split entry just quietly prices a
player wrong, so it has to be asserted rather than noticed.
"""
from __future__ import annotations

import re
from collections import defaultdict

from halfmen import adp_board, config, sleeper
from halfmen.names import normalize_name


def _surname_groups():
    groups = defaultdict(list)
    for key, row in adp_board.table().items():
        parts = [p for p in re.sub(r"[^A-Za-z ]", "", row["name"]).split() if p]
        if len(parts) < 2:
            continue
        last = parts[-1].lower()
        if last in ("jr", "sr", "ii", "iii", "iv") and len(parts) > 2:
            last = parts[-2].lower()
        groups[last].append((key, row, parts[0].lower()))
    return groups


def test_no_nickname_splits_the_consensus_board():
    """"Ken" and "Kenneth" behind one surname are one player, not two rows."""
    offenders = []
    for _last, rows in _surname_groups().items():
        for akey, arow, afirst in rows:
            for bkey, brow, bfirst in rows:
                if akey == bkey or afirst == bfirst:
                    continue
                # One first name a prefix of the other: Ken/Kenneth, Mike/
                # Michael, Cam/Cameron. Two genuinely different players almost
                # never collide this way behind a shared surname.
                if len(afirst) >= 2 and bfirst.startswith(afirst):
                    offenders.append("%s (%s src) / %s (%s src)" % (
                        arow["name"], arow["sources"], brow["name"], brow["sources"]))
    assert not offenders, (
        "one player on two rows - add an alias in names.py: " + "; ".join(sorted(set(offenders))))


def test_a_collision_keeps_the_better_sourced_row():
    """Aliasing two spellings onto one key is only half a fix. The rows still
    collide, and resolving that on CSV order hands the board to whichever
    source happened to be written last."""
    thin = {"name": "x", "rank": 5.0, "sources": 1}
    thick = {"name": "x", "rank": 40.0, "sources": 6}
    assert adp_board._rank_beats(thick, thin), "more sources must win"
    assert not adp_board._rank_beats(thin, thick)
    # Same backing, better rank wins.
    assert adp_board._rank_beats({"rank": 5.0, "sources": 3}, {"rank": 9.0, "sources": 3})


def test_every_rostered_player_resolves_to_the_board():
    """A rostered player the board cannot find is priced as if he were free,
    which is the exact bug this file exists for. Skips when Sleeper is
    unreachable rather than failing the suite on a network blip."""
    try:
        pmap = sleeper.get_players()
        rosters = sleeper.get_rosters(config.league_id())
    except Exception:                                   # pragma: no cover
        return
    if not rosters or not any(r.get("players") for r in rosters):
        return
    table = adp_board.table()
    if not table:
        return
    missing = []
    for r in rosters:
        for pid in (r.get("players") or []):
            full = (pmap.get(str(pid)) or {}).get("full_name")
            if full and normalize_name(full) not in table:
                missing.append(full)
    assert not missing, "not on the consensus board: %s" % ", ".join(sorted(set(missing))[:10])
