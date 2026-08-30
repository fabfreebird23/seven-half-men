"""The season while it is being played: table, fixtures, money, moves, taxi.

Everything here reads Sleeper and returns plain dicts, so the Home page can be
laid out without any of this logic living in app.py and so each piece can be
tested against a fixture instead of against a live league in week 1.

Two things are deliberately NOT invented here:

  * There is no projections feed. Sleeper's matchup endpoint carries points
    already scored and nothing else, and the ADP file is season-long consensus
    rank with no weekly component. So `matchups` reports a favourite derived
    from preseason consensus and labels it as exactly that. A number called
    "projected 118.4" would be made up, and made-up precision is worse than no
    number at all - people believe it.
  * Nothing here writes. The taxi view reports who has not stashed their
    rookies; it does not move them, because that is a roster action in Sleeper
    and the app is not the thing that owns rosters.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from . import adp_board, config, sleeper
from .names import normalize_name

# Below this edge the two rosters are not distinguishable and the honest
# answer is to say so rather than print 50.2% as though it meant something.
_COINFLIP = 53.0


def _value(rank: float) -> float:
    """What a consensus rank is worth, on a curve that falls off like real
    fantasy value does: the gap between the 1st and 15th player is enormous
    and the gap between the 150th and 165th is nearly nothing. A linear
    `400 - rank` treats those as the same 15 places and flattens eight rosters
    into a dead heat at 50.0% every week."""
    return 100.0 / math.sqrt(max(1.0, rank))


def current_week(league_id: str = None) -> int:
    """The week Sleeper thinks it is. 1 before anything has been played."""
    try:
        lg = sleeper.get_league(league_id or config.league_id()) or {}
    except Exception:
        return 1
    return max(1, _int((lg.get("settings") or {}).get("leg"), 1))


def _int(v, default: int = 0) -> int:
    """Sleeper is the source for every number here and a missing field must not
    be able to take the page down. A roster row with no id is skipped; it is
    not worth a stack trace on the front page."""
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _owner_by_roster(rosters: List[dict]) -> Dict[int, str]:
    return {_int(r.get("roster_id"), -1): str(r.get("owner_id") or "")
            for r in rosters if r.get("roster_id") is not None}


# --------------------------------------------------------------------------
# the table
# --------------------------------------------------------------------------

def standings(league_id: str = None) -> List[dict]:
    """One row per team, best first.

    Sorted on wins, then points for - which is Sleeper's own tiebreak and the
    one the league plays under, so the order here matches the order in the app.

    `played` counts real games. With the league-median match switched on every
    week produces TWO results, so a team at 6-3 in week 4 is not a team that
    has played nine weeks, and dividing wins+losses by anything would report a
    season roughly twice as long as it is.
    """
    try:
        rosters = sleeper.get_rosters(league_id or config.league_id()) or []
    except Exception:
        return []
    per_week = 2 if config.median_match() else 1
    out = []
    for r in rosters:
        s = r.get("settings") or {}
        w, l, t = _int(s.get("wins")), _int(s.get("losses")), _int(s.get("ties"))
        pf = float(s.get("fpts") or 0) + float(s.get("fpts_decimal") or 0) / 100.0
        out.append({
            "owner_id": str(r.get("owner_id") or ""),
            "roster_id": _int(r.get("roster_id")),
            "wins": w, "losses": l, "ties": t,
            "record": "%d–%d%s" % (w, l, "–%d" % t if t else ""),
            "points_for": pf,
            "results": w + l + t,
            "played": (w + l + t) // per_week,
            "budget_left": max(0, int(config.faab_rules()["budget"])
                               - _int(s.get("waiver_budget_used"))),
            "moves": _int(s.get("total_moves")),
        })
    out.sort(key=lambda x: (-x["wins"], -x["points_for"]))
    for i, row in enumerate(out, 1):
        row["place"] = i
        row["in_bracket"] = i <= int(config.league()["playoff_teams"])
    return out


def nothing_played(rows: List[dict] = None) -> bool:
    """True while the table is eight rows of 0-0.

    Worth asking before rendering one: a standings block in week 1 is a header
    over no information, and the page is better off saying so than drawing it.
    """
    rows = standings() if rows is None else rows
    return not rows or all(r["results"] == 0 for r in rows)


# --------------------------------------------------------------------------
# roster strength, and what it is allowed to claim
# --------------------------------------------------------------------------

def _strength(player_ids: List[str], pmap: Dict[str, Any], table: Dict[str, dict],
              count: int = None) -> float:
    """A roster's preseason consensus weight, best `count` players only.

    Deliberately crude, and only ever compared against another roster's number
    from the same board. It is a ranking, not a score.
    """
    count = count or len(config.roster()["starters"])
    vals = []
    for pid in player_ids or []:
        full = (pmap.get(str(pid)) or {}).get("full_name")
        row = table.get(normalize_name(full)) if full else None
        if row and row.get("rank"):
            vals.append(_value(float(row["rank"])))
    vals.sort(reverse=True)
    return round(sum(vals[:count]), 1)


def matchups(week: int = None, league_id: str = None) -> List[dict]:
    """This week's fixtures, paired up, with who is favoured and by how much.

    `points` are real and zero until games are played. `edge` is the share of
    the two rosters' combined consensus weight held by the favourite, so 50%
    is a coin flip and 60% is a clear favourite. It is NOT a win probability
    and is not presented as one.
    """
    league_id = league_id or config.league_id()
    week = int(week or current_week(league_id))
    try:
        rows = sleeper.get_matchups(league_id, week) or []
        rosters = sleeper.get_rosters(league_id) or []
        pmap = sleeper.get_players()
    except Exception:
        return []
    owner = _owner_by_roster(rosters)
    players = {_int(r.get("roster_id"), -1): (r.get("players") or [])
               for r in rosters if r.get("roster_id") is not None}
    table = adp_board.table()

    groups: Dict[Any, List[dict]] = {}
    for m in rows:
        groups.setdefault(m.get("matchup_id"), []).append(m)

    out = []
    for mid, side in sorted(groups.items(), key=lambda kv: (kv[0] is None, kv[0])):
        if len(side) != 2:
            continue                      # a bye, or a broken week
        pair = []
        for m in side:
            rid = _int(m.get("roster_id"), -1)
            pair.append({
                "owner_id": owner.get(rid, ""),
                "roster_id": rid,
                "points": round(float(m.get("points") or 0), 2),
                "strength": _strength(players.get(rid, []), pmap, table),
            })
        total = sum(p["strength"] for p in pair) or 1.0
        fav = max(pair, key=lambda p: p["strength"])
        edge = round(100.0 * fav["strength"] / total, 1)
        out.append({
            "matchup_id": mid, "week": week, "sides": pair,
            "favourite": fav["owner_id"] if edge >= _COINFLIP else "",
            "edge": edge,
            "too_close": edge < _COINFLIP,
            "started": any(p["points"] for p in pair),
        })
    return out


# --------------------------------------------------------------------------
# the wire, as it actually happened
# --------------------------------------------------------------------------

_KINDS = {"free_agent": "added", "waiver": "claimed", "trade": "traded",
          "commissioner": "commish"}


def transactions(limit: int = 12, week: int = None, league_id: str = None) -> List[dict]:
    """Recent completed moves, newest first, walking back week by week.

    Sleeper keys transactions by week and gives no "latest" endpoint, so an
    empty current week means the last thing that happened was earlier - not
    that nothing has happened. Walk back until there is something to show.
    """
    league_id = league_id or config.league_id()
    week = int(week or current_week(league_id))
    try:
        rosters = sleeper.get_rosters(league_id) or []
        pmap = sleeper.get_players()
    except Exception:
        return []
    owner = _owner_by_roster(rosters)

    def name(pid: str) -> str:
        m = pmap.get(str(pid)) or {}
        return m.get("full_name") or str(pid)

    def pos(pid: str) -> str:
        return (pmap.get(str(pid)) or {}).get("position") or ""

    out: List[dict] = []
    for wk in range(week, 0, -1):
        try:
            got = sleeper.get_transactions(league_id, wk) or []
        except Exception:
            got = []
        for t in got:
            if t.get("status") != "complete":
                continue
            rids = [_int(x, -1) for x in (t.get("roster_ids") or [])]
            out.append({
                "week": wk,
                "kind": _KINDS.get(t.get("type"), t.get("type") or ""),
                "raw_kind": t.get("type") or "",
                "when": int(t.get("status_updated") or 0),
                "owners": [owner.get(r, "") for r in rids],
                "bid": _int((t.get("settings") or {}).get("waiver_bid")),
                "adds": [{"id": p, "name": name(p), "position": pos(p),
                          "owner_id": owner.get(_int(r, -1), "")}
                         for p, r in (t.get("adds") or {}).items()],
                "drops": [{"id": p, "name": name(p), "position": pos(p),
                           "owner_id": owner.get(_int(r, -1), "")}
                          for p, r in (t.get("drops") or {}).items()],
            })
        if len(out) >= limit:
            break
    out.sort(key=lambda x: x["when"], reverse=True)
    return out[:limit]


# --------------------------------------------------------------------------
# the taxi squad, league-wide
# --------------------------------------------------------------------------

def taxi(league_id: str = None) -> List[dict]:
    """Who is on taxi, everywhere, who has room, and who is wasting it.

    Eligibility is ANY rookie you drafted, off either board - a rookie taken in
    the 12th of the veteran draft qualifies exactly as much as one taken 1.01
    in the rookie draft. So an open slot is only worth flagging when the
    manager is actually holding a rookie who could fill it, and `parkable` is
    that list: rookies sitting on a bench, costing an active roster spot, who
    could be on taxi for free.

    That is the whole reason this view exists. Sleeper shows one roster at a
    time and has no league-wide taxi screen, so a wasted slot is invisible
    unless somebody opens eight rosters and cross-references a rookie list.
    """
    league_id = league_id or config.league_id()
    try:
        rosters = sleeper.get_rosters(league_id) or []
        pmap = sleeper.get_players()
    except Exception:
        return []
    slots = int(config.taxi_rules()["slots"])
    table = adp_board.table()

    def described(pid: str) -> dict:
        m = pmap.get(str(pid)) or {}
        full = m.get("full_name") or str(pid)
        row = table.get(normalize_name(full)) or {}
        return {"id": str(pid), "name": full,
                "position": m.get("position") or "",
                "team": m.get("team") or "",
                "rookie": _int(m.get("years_exp"), -1) == 0,
                "rank": row.get("rank")}

    out = []
    for r in rosters:
        ids = [str(x) for x in (r.get("taxi") or [])]
        men = [described(p) for p in ids]
        men.sort(key=lambda p: (p["rank"] is None, p["rank"] or 0))
        # Rookies on the active roster who could be on taxi instead. Only
        # meaningful while there is a slot free to put them in.
        onroster = [str(x) for x in (r.get("players") or []) if str(x) not in set(ids)]
        parkable = [p for p in (described(x) for x in onroster) if p["rookie"]]
        parkable.sort(key=lambda p: (p["rank"] is None, p["rank"] or 0))
        room = max(0, slots - len(men))
        out.append({
            "owner_id": str(r.get("owner_id") or ""),
            "players": men,
            "used": len(men),
            "slots": slots,
            "open": room,
            "empty": not men,
            "parkable": parkable[:room] if room else [],
            "wasting": bool(room and parkable),
        })
    # Wasted slots first - they are the only rows that need acting on.
    out.sort(key=lambda x: (not x["wasting"], x["used"], x["owner_id"]))
    return out


def taxi_gap(rows: List[dict] = None) -> List[str]:
    """Owners with a free slot AND a rookie who could be in it.

    Deliberately not "everyone with a free slot". A manager who drafted no
    rookies has nothing to fix and does not belong on a list of people holding
    the league up.
    """
    rows = taxi() if rows is None else rows
    return [r["owner_id"] for r in rows if r["wasting"]]

# --------------------------------------------------------------------------
# power rankings
# --------------------------------------------------------------------------

# How quickly results take over from roster strength. At week 0 the ranking is
# pure roster strength because there is nothing else; by this week it is pure
# results. Six is deliberate on a 13-week season: four or five games is enough
# that a hot start is no longer just a soft schedule, and waiting longer means
# the block is still arguing about the draft in November.
RESULTS_TAKE_OVER_BY = 6.0


def _pct(value: float, biggest: float) -> float:
    return (value / biggest) if biggest else 0.0


def power(league_id: str = None) -> List[dict]:
    """Ranked on a blend of what you have done and what you are holding.

    Two components, both scaled 0-1 against the best team in the league so they
    can be mixed at all:

      results   60% win rate, 40% points for. Win rate alone rewards a soft
                schedule; points alone ignores that the league plays games.
      strength  the roster's best nine ACTIVES against the consensus board.
                Taxi is excluded - a stashed rookie cannot score for you.

    The weight moves. In week 1 there are no results, so a blend that included
    them would just be roster strength with extra steps, and the honest thing
    is to say the ranking IS roster strength. By week `RESULTS_TAKE_OVER_BY`
    the roster component is gone entirely, because by then the season has
    opinions of its own and a preseason board does not get a vote.

    `moved` is against the preseason strength order rather than last week's
    ranking. That needs no stored history, and it answers the better question:
    not "who got hot this week" but "who is doing more than their draft said
    they would".
    """
    league_id = league_id or config.league_id()
    rows = standings(league_id)
    if not rows:
        return []
    try:
        rosters = sleeper.get_rosters(league_id) or []
        pmap = sleeper.get_players()
    except Exception:
        rosters, pmap = [], {}
    table = adp_board.table()

    actives = {}
    for r in rosters:
        owner = str(r.get("owner_id") or "")
        taxi_ids = {str(x) for x in (r.get("taxi") or [])}
        actives[owner] = [str(p) for p in (r.get("players") or [])
                          if str(p) not in taxi_ids]

    played = max(r["played"] for r in rows)
    weight = min(1.0, played / RESULTS_TAKE_OVER_BY) if played else 0.0

    for r in rows:
        r["strength"] = _strength(actives.get(r["owner_id"], []), pmap, table)
    best_strength = max((r["strength"] for r in rows), default=0.0)
    best_pf = max((r["points_for"] for r in rows), default=0.0)

    for r in rows:
        wins = r["wins"] + 0.5 * r["ties"]
        rate = (wins / r["results"]) if r["results"] else 0.0
        r["win_rate"] = rate
        r["results_score"] = 0.6 * rate + 0.4 * _pct(r["points_for"], best_pf)
        r["strength_score"] = _pct(r["strength"], best_strength)
        r["power"] = round(100.0 * (weight * r["results_score"]
                                    + (1.0 - weight) * r["strength_score"]), 1)

    # Where the draft said they should be, for the movement column.
    seed = sorted(rows, key=lambda x: -x["strength"])
    seeded = {r["owner_id"]: i + 1 for i, r in enumerate(seed)}

    out = sorted(rows, key=lambda x: (-x["power"], -x["points_for"]))
    for i, r in enumerate(out, 1):
        r["rank"] = i
        r["seed"] = seeded.get(r["owner_id"], i)
        r["moved"] = r["seed"] - i          # positive = climbing
        r["weight"] = round(weight, 3)
    return out


def power_basis(rows: List[dict] = None) -> str:
    """What the ranking is actually made of right now, in words. The block has
    to say this - a number blended from two things, labelled neither, invites
    everyone to assume it is the one they like least."""
    rows = power() if rows is None else rows
    if not rows:
        return ""
    w = rows[0].get("weight", 0.0)
    if w <= 0:
        return "roster strength only &mdash; nothing has been played"
    if w >= 1:
        return "record and points only"
    return "%d%% record, %d%% roster strength" % (round(w * 100), round((1 - w) * 100))
