"""Who owns which pick, and what is already spoken for.

Two things go on the board: picks traded away, and picks eaten by keepers. A
keeper always lands on a round its owner actually holds (engine.allocate does
the bumping), so the board and the keeper slip can never disagree.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from . import config, sleeper


@dataclass
class Cell:
    round: int
    slot: int                 # 1-based column
    owner_id: str
    pick_label: str
    kind: str = "open"        # open | traded | keeper | rookie | franchise
    player: str = ""
    note: str = ""


def owned_rounds(league_id: str = None, season: int = None) -> Dict[str, Counter]:
    """owner_id -> Counter of rounds they hold in `season`'s veteran draft.

    Starts from one pick per round per team, then applies Sleeper's traded-pick
    log: the original owner loses it and the new owner gains it.
    """
    league_id = league_id or config.league_id()
    season = int(season or config.season())
    rounds = config.veteran_rounds(season)

    roster_owner = {int(r["roster_id"]): str(r.get("owner_id") or "")
                    for r in sleeper.get_rosters(league_id)}
    owned: Dict[str, Counter] = {o: Counter({r: 1 for r in range(1, rounds + 1)})
                                 for o in roster_owner.values() if o}

    for tp in sleeper.get_traded_picks(league_id) or []:
        if int(tp.get("season") or 0) != season:
            continue
        rnd = int(tp.get("round") or 0)
        if not (1 <= rnd <= rounds):
            continue
        loser = roster_owner.get(int(tp.get("previous_owner_id") or 0)) \
            or roster_owner.get(int(tp.get("roster_id") or 0))
        winner = roster_owner.get(int(tp.get("owner_id") or 0))
        if loser in owned and owned[loser][rnd] > 0:
            owned[loser][rnd] -= 1
        if winner in owned:
            owned[winner][rnd] += 1
    return owned


def traded_away(league_id: str = None, season: int = None) -> Dict[str, List[int]]:
    """owner_id -> rounds where they hold nothing."""
    out = {}
    for owner, counter in owned_rounds(league_id, season).items():
        rounds = config.veteran_rounds(season)
        out[owner] = [r for r in range(1, rounds + 1) if counter.get(r, 0) <= 0]
    return out


def order_from_selection(selection_order: Sequence[str],
                         chosen_slots: Dict[str, int] = None) -> List[str]:
    """The lottery produces a SELECTION order; managers then choose slots. Until
    they do, show the provisional board as selection order == slot order."""
    chosen_slots = chosen_slots or {}
    if not chosen_slots:
        return list(selection_order)
    n = len(selection_order)
    board: List[Optional[str]] = [None] * n
    for owner, slot in chosen_slots.items():
        if 1 <= int(slot) <= n:
            board[int(slot) - 1] = owner
    for owner in selection_order:
        if owner in chosen_slots:
            continue
        for i in range(n):
            if board[i] is None:
                board[i] = owner
                break
    return [o for o in board if o]


def grid(order: Sequence[str], *, season: int = None,
         keepers: Dict[str, List[dict]] = None,
         league_id: str = None) -> List[List[Cell]]:
    """rounds x teams. Columns stay with the same team all the way down; the
    snake only changes the pick NUMBER, not who owns the column."""
    season = int(season or config.season())
    rounds = config.veteran_rounds(season)
    keepers = keepers or {}
    gone = traded_away(league_id, season)

    board: List[List[Cell]] = []
    for rnd in range(1, rounds + 1):
        row: List[Cell] = []
        for i, owner in enumerate(order):
            pick = i + 1 if rnd % 2 else len(order) - i
            cell = Cell(round=rnd, slot=i + 1, owner_id=owner,
                        pick_label="%d.%02d" % (rnd, pick))
            k = next((x for x in keepers.get(owner, []) if int(x.get("round") or 0) == rnd), None)
            if k:
                cell.kind = k.get("kind") or "keeper"
                cell.player = k.get("name") or ""
                cell.note = k.get("note") or ""
            elif rnd in gone.get(owner, []):
                cell.kind = "traded"
            row.append(cell)
        board.append(row)
    return board


def capital(order: Sequence[str], keepers: Dict[str, List[dict]] = None,
            season: int = None, league_id: str = None) -> List[dict]:
    """Per-team summary: how many live picks are actually left."""
    season = int(season or config.season())
    rounds = config.veteran_rounds(season)
    keepers = keepers or {}
    owned = owned_rounds(league_id, season)
    out = []
    for owner in order:
        held = sum(max(0, c) for c in owned.get(owner, Counter()).values())
        eaten = len(keepers.get(owner, []))
        out.append({"owner_id": owner, "rounds": rounds, "held": held,
                    "eaten": eaten, "live": max(0, held - eaten),
                    "rookie_picks": config.rookie_rounds()})
    return out


def rookie_grid(order: Sequence[str], season: int = None) -> List[List[Cell]]:
    """The rookie draft board: rounds x teams, in the order the drum settled.

    Its own function rather than a flag on grid(): the rookie draft has its own
    round count, its own snake setting, and no keepers to burn in - a keeper
    costs a VETERAN pick, so nothing is ever struck off this board.
    """
    season = int(season or config.season())
    rounds = config.rookie_rounds()
    snake = bool(config.drafts().get("rookie_snake", True))
    n = len(order)

    board: List[List[Cell]] = []
    for rnd in range(1, rounds + 1):
        row: List[Cell] = []
        for i, owner in enumerate(order):
            pick = (n - i) if (snake and rnd % 2 == 0) else (i + 1)
            row.append(Cell(round=rnd, slot=i + 1, owner_id=owner, kind="open",
                            pick_label="%d.%02d" % (rnd, pick)))
        board.append(row)
    return board


def rookie_pick_count(season: int = None) -> int:
    return config.rookie_rounds() * len(config.managers())
