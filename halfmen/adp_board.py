"""Turn the consensus ADP table into the one number the engine needs: a round.

`data/adp_<season>.csv` is produced by scripts/refresh_adp.py (the scraper stack
carried over from the kreeper tool - it is league-independent). Everything here
is about mapping a player to "where would the market take him in OUR draft",
which depends on our team count and round count, not on anyone else's.
"""
from __future__ import annotations

import csv
import math
from functools import lru_cache
from typing import Dict, Optional

from . import config
from .names import normalize_name


@lru_cache(maxsize=4)
def _table(season: int) -> Dict[str, dict]:
    path = config.DATA_DIR / ("adp_%d.csv" % season)
    if not path.exists():
        return {}
    out: Dict[str, dict] = {}
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            key = normalize_name(row.get("name", ""))
            if not key:
                continue
            try:
                rank = float(row["consensus_rank"])
            except (KeyError, TypeError, ValueError):
                continue
            got = {"name": row.get("name", ""), "position": row.get("position", ""),
                   "rank": rank, "adp": _f(row.get("consensus_adp")),
                   "sources": _i(row.get("n_sources"))}
            # Two rows can normalize onto one key - a nickname the alias table
            # reconciles ("Ken Walker" and "Kenneth Walker III" are one player
            # on seven boards that cannot agree how to spell him). Last-write
            # -wins would settle that on CSV row order, which is arbitrary and
            # silent: the row backed by ONE source beat the row backed by six,
            # and every keeper price downstream came off the wrong rank. Keep
            # the better-sourced row, and break a tie on the better rank.
            old = out.get(key)
            if old is None or _rank_beats(got, old):
                out[key] = got
    return out


def _rank_beats(new: dict, old: dict) -> bool:
    """Is `new` the more trustworthy row for a key both rows claim?"""
    ns, os_ = new.get("sources") or 0, old.get("sources") or 0
    if ns != os_:
        return ns > os_
    return (new.get("rank") or 1e9) < (old.get("rank") or 1e9)


def _f(v) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v) -> Optional[int]:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def rank_to_round(rank: float, *, teams: int = None, rounds: int = None) -> int:
    """Overall consensus rank -> the round he'd go in an 8-team draft.

    Rank 1-8 is round 1, 9-16 round 2, and so on. Anything past the last round
    clamps to the last round: a player nobody would draft still costs a last
    pick to keep, he is never free.
    """
    teams = teams or int(config.league()["teams"])
    rounds = rounds or config.veteran_rounds()
    rd = int(math.ceil(float(rank) / teams))
    return max(1, min(rounds, rd))


def lookup(name: str, season: int = None) -> Optional[dict]:
    season = season or config.season()
    return _table(season).get(normalize_name(name))


def adp_round(name: str, season: int = None) -> Optional[int]:
    row = lookup(name, season)
    return rank_to_round(row["rank"]) if row else None


def adp_round_for_player(player: dict, season: int = None) -> Optional[int]:
    """`player` is a Sleeper player record."""
    full = player.get("full_name") or "%s %s" % (
        player.get("first_name", ""), player.get("last_name", ""))
    return adp_round(full.strip(), season)


def freshness(season: int = None) -> Optional[str]:
    import json
    season = season or config.season()
    p = config.DATA_DIR / ("adp_%d_meta.json" % season)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text()).get("generated_at")
    except ValueError:
        return None


def size(season: int = None) -> int:
    return len(_table(season or config.season()))


def table(season: int = None) -> Dict[str, dict]:
    """The whole consensus board, keyed by normalized name."""
    return dict(_table(season or config.season()))


def by_round(season: int = None) -> Dict[int, list]:
    """round -> the players the market has going in it, best first."""
    out: Dict[int, list] = {}
    for v in sorted(table(season).values(), key=lambda v: v["rank"]):
        out.setdefault(rank_to_round(v["rank"]), []).append(v)
    return out
