"""The draft, when it happened in a room instead of on Sleeper.

Every live surface in this app reads rosters from Sleeper: the value board, the
wire, the taxi bay, every keeper price. A draft held offline and never keyed in
leaves all of that permanently empty - not for a week, forever. This is the way
the results get in without anyone re-entering 120 picks into Sleeper's UI first.

Locally recorded picks are a FALLBACK, never an override. The moment Sleeper has
real rosters they win, because they are the thing the league actually plays on
and this file is only ever a transcription of it.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from . import config, sleeper, storage
from .names import normalize_name

VETERAN = "veteran"
ROOKIE = "rookie"


# --------------------------------------------------------------------------
# reading and writing
# --------------------------------------------------------------------------

def load(kind: str = VETERAN, season: int = None) -> List[dict]:
    return list((storage.load(season) or {}).get("picks", {}).get(kind) or [])


def save(kind: str, picks: List[dict], season: int = None) -> List[dict]:
    data = storage.load(season)
    data.setdefault("picks", {})[kind] = list(picks)
    storage.save(data, season)
    return picks


def clear(kind: str, season: int = None) -> None:
    save(kind, [], season)


def board_seats(order: List[str], rounds: int, snake: bool = True) -> List[dict]:
    """Every seat on the board, in the order picks are actually made.

    `label` is the pick number within its round, NOT the seat number. In a snake
    those are opposites on even rounds, and mixing them is how a board ends up
    labelled one way and read out another.
    """
    seats = []
    n = len(order)
    for rnd in range(1, rounds + 1):
        row = list(order) if (not snake or rnd % 2 == 1) else list(reversed(order))
        for i, owner in enumerate(row):
            seats.append({"round": rnd, "pick": i + 1, "owner_id": owner,
                          "label": "%d.%02d" % (rnd, i + 1)})
    return seats


def add(kind: str, player: dict, order: List[str], rounds: int,
        snake: bool = True, season: int = None) -> dict:
    """Put one player in the next open seat. Returns the pick, or {} if full."""
    made = load(kind, season)
    seats = board_seats(order, rounds, snake)
    if len(made) >= len(seats):
        return {}
    seat = seats[len(made)]
    pick = {"round": seat["round"], "pick": seat["pick"], "owner_id": seat["owner_id"],
            "player_id": str(player["id"]), "name": player["name"],
            "position": player.get("position", ""), "team": player.get("team", "")}
    save(kind, made + [pick], season)
    return pick


def undo(kind: str, season: int = None) -> dict:
    """Take the last pick back. Somebody will say the wrong name."""
    made = load(kind, season)
    if not made:
        return {}
    last = made[-1]
    save(kind, made[:-1], season)
    return last


def taken_ids(kind: str = None, season: int = None) -> set:
    kinds = (kind,) if kind else (ROOKIE, VETERAN)
    return {str(p["player_id"]) for k in kinds for p in load(k, season)}


def recorded(season: int = None) -> int:
    return sum(len(load(k, season)) for k in (ROOKIE, VETERAN))


# --------------------------------------------------------------------------
# parsing what someone pastes in
# --------------------------------------------------------------------------

_LINE = re.compile(
    r"""^\s*
    (?:(?P<rnd>\d+)\s*[.\-:]\s*(?P<pick>\d+))?   # 3.05 / 3-5 / 3:5, optional
    \s*[.\)\-]?\s*
    (?P<name>[^,|\t]+?)                          # the player
    \s*(?:[,|\t]\s*(?P<owner>.+?))?              # optional owner after a comma
    \s*$""", re.X)


def parse(text: str, order: List[str], rounds: int, snake: bool = True,
          players: Dict[str, dict] = None) -> Dict[str, object]:
    """Turn pasted draft results into picks.

    Deliberately forgiving about format - people will paste from a spreadsheet,
    a group chat or a notes app - but strict about the two things that matter:
    a name has to resolve to a real player, and every pick has to land on a real
    slot. Anything it cannot place comes back in `problems` rather than being
    silently dropped, because a draft quietly missing three picks is worse than
    one that refuses to import.

    Picks are assigned in the order given, walking the board, unless a line
    carries its own round and pick number.
    """
    players = players if players is not None else _player_index()
    n = len(order)
    seats = []
    for rnd in range(1, rounds + 1):
        row = list(order) if (not snake or rnd % 2 == 1) else list(reversed(order))
        for i, owner in enumerate(row):
            seats.append({"round": rnd, "pick": i + 1, "owner_id": owner})

    picks: List[dict] = []
    problems: List[str] = []
    cursor = 0
    for raw in text.splitlines():
        if not raw.strip():
            continue
        m = _LINE.match(raw)
        if not m:
            problems.append("could not read: %s" % raw.strip())
            continue
        name = (m.group("name") or "").strip()
        if not name or name.lower() in ("player", "name", "pick"):
            continue

        hit = players.get(normalize_name(name))
        if not hit:
            problems.append("no such player: %s" % name)
            continue

        if m.group("rnd") and m.group("pick"):
            rnd, pk = int(m.group("rnd")), int(m.group("pick"))
            seat = next((s for s in seats if s["round"] == rnd and s["pick"] == pk), None)
            if not seat:
                problems.append("no slot %d.%02d on this board: %s" % (rnd, pk, name))
                continue
        else:
            if cursor >= len(seats):
                problems.append("more picks than slots, stopped at: %s" % name)
                break
            seat = seats[cursor]
        cursor = seats.index(seat) + 1

        picks.append({"round": seat["round"], "pick": seat["pick"],
                      "owner_id": seat["owner_id"], "player_id": hit["id"],
                      "name": hit["name"], "position": hit.get("position", "")})

    seen = {}
    for p in picks:
        key = (p["round"], p["pick"])
        if key in seen:
            problems.append("two players on %d.%02d: %s and %s" % (
                key[0], key[1], seen[key], p["name"]))
        seen[key] = p["name"]

    dupes = {}
    for p in picks:
        dupes.setdefault(p["player_id"], []).append(p["name"])
    for pid, names in dupes.items():
        if len(names) > 1:
            problems.append("%s drafted %d times" % (names[0], len(names)))

    return {"picks": picks, "problems": problems, "slots": len(seats)}


def _player_index() -> Dict[str, dict]:
    try:
        pmap = sleeper.get_players()
    except Exception:
        return {}
    out: Dict[str, dict] = {}
    for pid, meta in (pmap or {}).items():
        full = (meta or {}).get("full_name")
        if not full or (meta.get("position") or "") not in ("QB", "RB", "WR", "TE"):
            continue
        out.setdefault(normalize_name(full),
                       {"id": str(pid), "name": full, "position": meta.get("position")})
    return out


# --------------------------------------------------------------------------
# what the rest of the app reads
# --------------------------------------------------------------------------

def rosters(season: int = None) -> Dict[str, List[str]]:
    """owner_id -> player ids, from whichever draft results exist locally.

    Only consulted when Sleeper has nothing. See the module docstring.
    """
    out: Dict[str, List[str]] = {}
    for kind in (ROOKIE, VETERAN):
        for p in load(kind, season):
            out.setdefault(str(p["owner_id"]), []).append(str(p["player_id"]))
    return out


def draft_rows(season: int = None) -> List[dict]:
    """Flat pick list tagged with which draft it came from, for history."""
    season = int(season or config.season())
    rows = []
    for kind in (ROOKIE, VETERAN):
        for p in load(kind, season):
            rows.append(dict(p, draft=kind, season=season))
    return rows
