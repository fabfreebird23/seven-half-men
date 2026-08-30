"""What every player on every roster would cost his owner to keep next year.

This is the one screen that is worth opening mid-season. Every other surface in
the app answers an offseason question; this one answers "should I bid on him"
in week 6, because in a keeper league a waiver claim is not a rental - it is the
first year of a three-year contract at a price the round decides.

Composes the pieces rather than re-deriving them: history says how a player
arrived and how long he has been held, adp_board says what the market thinks,
and engine prices the two together.
"""
from __future__ import annotations

from collections import Counter
from typing import Dict, List, Optional

from . import adp_board, config, draftboard, engine, history, picks, sleeper
from .names import normalize_name


def _roster_players(league_id: str) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for r in sleeper.get_rosters(league_id) or []:
        owner = str(r.get("owner_id") or "")
        if owner:
            out[owner] = [str(p) for p in (r.get("players") or [])]
    if any(out.values()):
        return out
    # Sleeper has nobody rostered. If the draft was held offline and keyed in
    # here, use that - otherwise every board in the app stays permanently empty.
    # Sleeper always wins when it has anything, because it is what the league
    # actually plays on.
    return picks.rosters() or out


def price_for(pid: str, *, hist, pmap: dict, owner: str = None,
              last_round: int = None, slot: Optional[int] = None) -> Optional[engine.Price]:
    """One player, priced for whoever holds him, in the coming offseason.

    `slot` is which ROOKIE KEEPER slot he is being held in - 0 for the first,
    1 for the second, and None for "not in one". It has to be decided by the
    caller, because there are only %s of them and which two a manager spends
    them on is a fact about the whole roster, not about the player.

    Passing None for a rookie-eligible player is not a mistake: his third-best
    rookie can still be kept, just in a REGULAR slot at the normal price. That
    is the difference between "cannot be kept" and "cannot be kept cheaply".
    """
    meta = pmap.get(str(pid)) or {}
    name = meta.get("full_name") or str(pid)
    pos = meta.get("position") or ""
    adp = adp_board.adp_round_for_player(meta) if meta else None
    last_round = int(last_round or config.veteran_rounds())

    if slot is not None and hist.is_rookie_keeper_eligible(str(pid)):
        return engine.price_rookie(str(pid), name, pos, slot=int(slot),
                                   last_round=last_round, adp_round=adp)

    year = hist.keeper_year(str(pid)) + 1
    anchor = hist.keeper_anchor(str(pid))
    return engine.price_regular(
        str(pid), name, pos,
        draft_round=anchor if anchor else hist.draft_round(str(pid)),
        year=year, adp_round=adp,
        from_rookie_draft=hist.has_rookie_draft_provenance(str(pid)))


def _plausible_slip(priced: List["engine.Price"], slot_of: Dict[str, int],
                    kr: dict) -> List["engine.Price"]:
    """The players a manager would actually put on next year's slip.

    Best `rookie` rookies into the rookie slots and best `regular` of everyone
    else, ranked by surplus - the number that decides whether a slot is worth
    spending at all. This is a projection, not the manager's decision, and it
    exists only so the bump has a realistic set of players to compete over.
    """
    def by_surplus(p):
        return -(p.surplus if p.surplus is not None else -99)

    rookies = [p for p in priced if str(p.player_id) in slot_of]
    others = sorted([p for p in priced if str(p.player_id) not in slot_of], key=by_surplus)
    return sorted(rookies, key=by_surplus)[:int(kr["rookie"])] + others[:int(kr["regular"])]


def _market_rank(pid: str, pmap: dict) -> float:
    """Where the market has him. Unranked players sort last, so a slot is never
    spent on somebody nobody has heard of while a ranked rookie misses out."""
    meta = pmap.get(str(pid)) or {}
    row = adp_board.table().get(normalize_name(meta.get("full_name") or ""))
    return float(row["rank"]) if row and row.get("rank") else 1e9


def rows(league_id: str = None, season: int = None, hist=None) -> List[dict]:
    """Every rostered player in the league, priced and sorted by surplus.

    Empty before the draft, which is the honest answer rather than a placeholder
    - nobody is on a roster yet, so nobody has a price yet.
    """
    league_id = league_id or config.league_id()
    season = int(season or config.season())

    # Bail before any of the expensive work if nobody is rostered - which is the
    # whole of year one until the draft. Fetching pick ownership and the 5MB
    # player map to price an empty league is pure waste.
    rosters = _roster_players(league_id)
    if not any(rosters.values()):
        return []

    hist = hist or history.build(league_id)
    try:
        pmap = sleeper.get_players()
    except Exception:
        pmap = {}

    owned = draftboard.owned_rounds(league_id, season)
    kr = config.keeper_rules()
    slots = int(kr["rookie"])
    out: List[dict] = []
    for owner, pids in rosters.items():
        # There are only `slots` rookie keeper slots. Every rookie on the
        # roster used to be priced as though he were in the first one, which
        # started four players on the same round and let the bump scatter them
        # down the board to R12, R10, R7 - rounds that correspond to no rule at
        # all. Assign the slots to the best rookies by market, and price the
        # rest on the regular path, which is what keeping them actually costs.
        eligible = [str(x) for x in pids if hist.is_rookie_keeper_eligible(str(x))]
        eligible.sort(key=lambda x: _market_rank(x, pmap))
        slot_of = {pid: i for i, pid in enumerate(eligible[:slots])}
        priced = [p for p in (price_for(pid, hist=hist, pmap=pmap, owner=owner,
                                        slot=slot_of.get(str(pid)))
                              for pid in pids) if p]

        # Bumping is competitive - two keepers cannot share a round - but it is
        # competition among the players a manager would actually KEEP, not among
        # all sixteen on his roster. Allocating the whole roster meant sixteen
        # players claiming rounds off a fourteen-round board: the first rookie
        # took R14, the next R13, and by the fourth there was nothing left, so
        # the board printed R12, R10 and "no pick left" for players whose real
        # price is R14, R13 and R5.
        #
        # The slip is `regular` + `rookie` deep. Everyone outside it is priced
        # in isolation, which is the honest answer to "what would he cost me" -
        # he is not competing with anyone because he is not being kept.
        slip = _plausible_slip(priced, slot_of, kr)
        engine.allocate(slip, owned.get(owner, Counter()))
        for p in priced:
            if p not in slip:
                p.final_round = p.base_round
                p.bumped = False
        for p in priced:
            out.append({
                "owner_id": owner, "player_id": p.player_id, "name": p.name,
                "position": p.position, "kind": p.kind, "year": p.year,
                "cost": p.final_round, "base": p.base_round, "bumped": p.bumped,
                "adp": p.adp_round, "surplus": p.surplus,
                "eligible": p.eligible, "reason": p.reason,
                "from_rookie_draft": p.from_rookie_draft,
            })
    out.sort(key=lambda r: (-(r["surplus"] if r["surplus"] is not None else -99),
                            r["cost"] or 99))
    return out


def free_agents(league_id: str = None, limit: int = 30, hist=None) -> List[dict]:
    """Unrostered consensus-board players, priced as if you claimed them today.

    Dropping a player does not launder his keeper price. So a name on the wire
    is only cheap if he has never been drafted in this league - anyone who has
    carries the round he was drafted in, and his clock, straight onto the roster
    of whoever claims him. Pricing every free agent at a last-round pick would
    have told eight managers that a cut 2nd-rounder was an R13, which is the
    single most expensive thing this board could get wrong.

    Matching is by normalized name because the ADP board is name-keyed and
    Sleeper is id-keyed.
    """
    league_id = league_id or config.league_id()
    hist = hist or history.build(league_id)
    try:
        pmap = sleeper.get_players()
    except Exception:
        pmap = {}

    by_name: Dict[str, str] = {}
    for pid, meta in pmap.items():
        full = (meta or {}).get("full_name")
        if full:
            by_name.setdefault(normalize_name(full), str(pid))

    rostered_keys = set()
    for pids in _roster_players(league_id).values():
        for pid in pids:
            meta = pmap.get(str(pid)) or {}
            if meta.get("full_name"):
                rostered_keys.add(normalize_name(meta["full_name"]))

    last = int(config.veteran_rounds())
    out = []
    for key, row in sorted(table_items(), key=lambda kv: kv[1]["rank"]):
        if key in rostered_keys:
            continue
        adp = adp_board.rank_to_round(row["rank"])
        pid = by_name.get(key)
        priced = price_for(pid, hist=hist, pmap=pmap, last_round=last) if pid else None
        if priced and priced.final_round:
            cost, kind = priced.final_round, priced.kind
            # He has a history here, so he is not a fresh last-round pickup.
            carried = bool(hist.draft_round(pid) or hist.keeper_year(pid))
        else:
            cost, kind, carried = engine.waiver_anchor(last), "waiver", False
        out.append({"name": row["name"], "position": row["position"], "player_id": pid,
                    "cost": cost, "adp": adp, "surplus": cost - adp,
                    "kind": kind, "carried": carried})
        if len(out) >= limit:
            break
    out.sort(key=lambda r: (-r["surplus"], r["cost"]))
    return out


def table_items():
    return adp_board.table().items()


# --------------------------------------------------------------------------
# the franchise tag
# --------------------------------------------------------------------------

def franchise_candidates(owner_id: str, league_id: str = None, hist=None) -> List[dict]:
    """Which of a manager's players the tag would be worth spending on.

    The tag freezes the price at the most EXPENSIVE round ever paid, so it is
    worth the most on a player whose market ran away from a cheap peak and
    literally nothing on a career first-rounder. Ranked by what it actually
    banks over the two extra years, which is the only number that decides it.
    """
    league_id = league_id or config.league_id()
    hist = hist or history.build(league_id)
    try:
        pmap = sleeper.get_players()
    except Exception:
        pmap = {}
    fr = config.franchise_rules()
    wall = int(config.keeper_rules()["max_years"])
    extra = int(fr["extra_years"])

    out = []
    for pid in _roster_players(league_id).get(str(owner_id), []):
        meta = pmap.get(str(pid)) or {}
        year = hist.keeper_year(str(pid)) + 1
        peak = hist.peak_round(str(pid))
        adp = adp_board.adp_round_for_player(meta) if meta else None
        if not peak or not adp:
            continue
        p = engine.price_franchise(str(pid), meta.get("full_name") or str(pid),
                                   meta.get("position") or "", peak_round=peak,
                                   year=max(year, wall + 1), adp_round=adp)
        per_year = (p.surplus or 0)
        out.append({"player_id": str(pid), "name": p.name, "position": p.position,
                    "year": year, "frozen": p.base_round, "adp": adp,
                    "per_year": per_year, "banked": per_year * extra,
                    "at_the_wall": year > wall, "eligible": p.eligible})
    out.sort(key=lambda r: (-r["at_the_wall"], -r["banked"]))
    return out
