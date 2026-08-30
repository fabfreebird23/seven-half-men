"""Draft history and the keeper ledger, rebuilt from Sleeper season by season.

In year one this is nearly empty - that is the point. Everything downstream
(what a player would cost you next year, whether he is rookie-keeper eligible,
which year of his clock he is on) reads from here rather than guessing, so the
same code works in 2026 and in 2033.

Sleeper's own `is_keeper` flag is unreliable across seasons in the user's other
leagues, so keeper years are counted from our own submitted ledger
(storage.load) and only fall back to Sleeper's flag when we have nothing.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from . import config, picks as local_picks, sleeper, storage
from .engine import rookie_draft_premium


@dataclass
class PlayerSeason:
    season: int
    owner_id: str
    round: Optional[int]
    pick_no: Optional[int]
    draft_type: str          # rookie | veteran | first_season
    was_rookie: bool         # an actual NFL rookie that season
    kept: bool = False
    rookie_kept: bool = False


@dataclass
class History:
    seasons: List[int] = field(default_factory=list)
    by_player: Dict[str, List[PlayerSeason]] = field(default_factory=lambda: defaultdict(list))
    drafted_as_rookie: Dict[str, int] = field(default_factory=dict)   # pid -> season
    rookie_draft_round: Dict[str, int] = field(default_factory=dict)  # pid -> round
    ever_regular_keeper: Set[str] = field(default_factory=set)

    # ---------------------------------------------------------------- queries
    def latest(self, pid: str) -> Optional[PlayerSeason]:
        rows = self.by_player.get(pid) or []
        return max(rows, key=lambda r: r.season) if rows else None

    def keeper_year(self, pid: str) -> int:
        """How many seasons in a row this player has been kept as a REGULAR
        keeper. 0 means the coming season would be his first."""
        rows = sorted(self.by_player.get(pid) or [], key=lambda r: r.season)
        streak = 0
        for r in rows:
            if r.kept and not r.rookie_kept:
                streak += 1
            elif r.rookie_kept:
                continue          # rookie years don't advance the clock
            else:
                streak = 0
        return streak

    def peak_round(self, pid: str) -> Optional[int]:
        """The most EXPENSIVE round ever paid for him - the franchise price."""
        rounds = [r.round for r in self.by_player.get(pid) or [] if r.round]
        return min(rounds) if rounds else None

    def draft_round(self, pid: str) -> Optional[int]:
        r = self.latest(pid)
        return r.round if r else None

    def _last_draft(self, pid: str) -> Optional[PlayerSeason]:
        rows = [r for r in (self.by_player.get(pid) or []) if r.draft_type]
        return max(rows, key=lambda r: r.season) if rows else None

    def has_rookie_draft_provenance(self, pid: str) -> bool:
        """Did he enter through the ROOKIE draft and not pass back through the
        veteran pool since?

        This is the predicate the R%d premium hangs off, and it is deliberately
        about provenance rather than age. Do not reach for `years_exp == 0` here:
        a player stashed two years on taxi and then promoted is no longer a
        rookie by that field, but he still has no veteran draft round and still
        prices at the premium. Pool passage is what resets it - once he has been
        redrafted in the veteran draft he has a real round and the premium no
        longer applies.
        """ % rookie_draft_premium()
        last = self._last_draft(pid)
        return bool(last and last.draft_type == "rookie")

    def keeper_anchor(self, pid: str) -> Optional[int]:
        """The round the regular-keeper ladder computes from. None means the
        caller should use the rookie-draft premium (see the flag above) or, for
        an undrafted pickup, the last available round."""
        if self.has_rookie_draft_provenance(pid):
            return None
        return self.draft_round(pid)

    def is_rookie_keeper_eligible(self, pid: str) -> bool:
        """Any NFL rookie you DRAFTED, in either draft. Not a waiver pickup, and
        not once he has been traded or converted to a regular keeper.

        Time on the taxi squad is deliberately not a factor. The rule turns on
        having drafted him as a rookie and never stopped holding him, and a taxi
        stint is still holding him - so promoting a stashed player off taxi, in
        year one or year two, leaves the designation intact. He simply stops
        being free and starts costing a rookie keeper slot.
        """
        if pid in self.ever_regular_keeper:
            return False
        return pid in self.drafted_as_rookie


def _draft_kind(draft: dict, first_season: bool) -> str:
    """Rookie draft or veteran draft.

    `player_type` is asked first because it is what Sleeper actually enforces -
    1 means a rookie-only board. Round count was the original test and it is not
    safe: the 2026 rookie draft went up configured for 16 rounds instead of 16
    picks, which made it look like a veteran draft to this function and would
    have priced every rookie against a veteran round with no R5 premium and no
    rookie-keeper status.
    """
    st = draft.get("settings") or {}
    if int(st.get("player_type", 0)) == 1:
        return "rookie"
    rounds = int(st.get("rounds") or 0)
    if rounds and rounds <= config.rookie_rounds():
        return "rookie"
    return "first_season" if first_season else "veteran"


def _picks_for(draft: dict, kind: str = None) -> List[dict]:
    """Picks that count, which is not always the picks that happened.

    Sleeper would not let the rookie draft be set to two rounds, so it runs long
    and gets stopped by hand. Anything past the rulebook's round count is not a
    pick in this league, and letting it through would put players on rosters and
    keeper clocks that nobody agreed to.
    """
    picks = sleeper.get_draft_picks(str(draft["draft_id"])) or []
    cap = config.rookie_rounds() if kind == "rookie" else None
    if cap:
        picks = [p for p in picks if int(p.get("round") or 0) <= cap]
    return picks


def _real_drafts(league_id: str) -> List[dict]:
    """The drafts that count, in board order, per `drafts.sleeper_drafts`.

    Falls back to everything Sleeper returns when nothing is configured, which
    is the right behaviour for a past season keyed in before the setting
    existed and for any league that never had a junk draft.
    """
    drafts = sleeper.get_drafts(league_id) or []
    want = []
    for ids in (config.drafts().get("sleeper_drafts") or {}).values():
        want.extend(str(x) for x in (ids or []))
    if not want:
        return drafts
    by_id = {str(d.get("draft_id")): d for d in drafts}
    got = [by_id[i] for i in want if i in by_id]
    return got or drafts


def build(league_id: str = None) -> History:
    league_id = league_id or config.league_id()
    hist = History()
    chain = sleeper.league_chain(league_id)
    players = {}
    try:
        players = sleeper.get_players()
    except Exception:
        players = {}

    # If the drafts were held offline and keyed in, they are the only record of
    # who drafted whom - which is what every keeper price and the R5 premium
    # hang off. Merged before Sleeper's own drafts so real data still wins.
    for row in local_picks.draft_rows():
        pid = str(row["player_id"])
        meta = players.get(pid) or {}
        season = int(row["season"])
        was_rookie = _was_rookie(meta, season)
        hist.by_player[pid].append(PlayerSeason(
            season=season, owner_id=str(row["owner_id"]), round=int(row["round"]),
            pick_no=int(row["pick"]), draft_type=row["draft"], was_rookie=was_rookie))
        if row["draft"] == "rookie" and pid not in hist.drafted_as_rookie:
            hist.drafted_as_rookie[pid] = season
            hist.rookie_draft_round[pid] = int(row["round"])
        elif was_rookie and pid not in hist.drafted_as_rookie:
            hist.drafted_as_rookie[pid] = season

    for link in sorted(chain, key=lambda c: c["season"]):
        season = int(link["season"])
        hist.seasons.append(season)
        first = config.is_first_season(season)
        ledger = storage.load(season)          # our own submitted keepers
        kept = set(ledger.get("kept", []))
        rookie_kept = set(ledger.get("rookie_kept", []))

        # Only the drafts the rulebook says are real. Five exist on Sleeper
        # for 2026 and two are junk - the never-started veteran board and the
        # rookie draft that went live at 16 ROUNDS and was abandoned. The junk
        # rookie draft holds the same first sixteen picks as the real one, so
        # reading every draft recorded each of those players TWICE, which
        # inflates anything that counts seasons held.
        drafts = _real_drafts(link["league_id"])
        for d in drafts:
            kind = _draft_kind(d, first)
            for pick in _picks_for(d, kind):
                pid = str(pick.get("player_id") or "")
                if not pid:
                    continue
                owner = str(pick.get("picked_by") or "")
                rnd = pick.get("round")
                meta = players.get(pid) or {}
                was_rookie = _was_rookie(meta, season)
                ps = PlayerSeason(season=season, owner_id=owner,
                                  round=int(rnd) if rnd else None,
                                  pick_no=pick.get("pick_no"), draft_type=kind,
                                  was_rookie=was_rookie,
                                  kept=pid in kept, rookie_kept=pid in rookie_kept)
                hist.by_player[pid].append(ps)

                if was_rookie and pid not in hist.drafted_as_rookie:
                    hist.drafted_as_rookie[pid] = season
                    if ps.round:
                        hist.rookie_draft_round[pid] = ps.round
                if ps.kept and not ps.rookie_kept:
                    hist.ever_regular_keeper.add(pid)

    return hist


def _was_rookie(player_meta: dict, season: int) -> bool:
    """An NFL rookie in `season`. Sleeper carries `years_exp` as of *now*, so we
    back-date it against the current season rather than trusting it directly."""
    if not player_meta:
        return False
    yrs = player_meta.get("years_exp")
    if yrs is None:
        return False
    try:
        yrs = int(yrs)
    except (TypeError, ValueError):
        return False
    return (config.season() - season) == yrs
