"""The consolation pot, funded by unspent FAAB.

Whatever waiver budget you did not spend by the end of the season, you owe.
Every dollar comes due - the cap does not forgive anything, it only decides who
gets paid.

The cap is the THIRD-PLACE PRIZE rather than a fixed number (league vote,
2026-08-06). Deriving it is the point: at a flat $200 against an $800 pool, a
bubble team in week 14 was roughly indifferent between sneaking into the bracket
and missing on purpose to play for the pot, which is a tanking incentive sitting
in the foundation. Pinned to third place it cannot outrank a playoff finish at
any buy-in, and it needs no re-vote when the buy-in changes.

Whatever is left over rejoins the prize pool in the same proportions as the
payout instead of landing entirely on the champion, so an unspent-FAAB year
lifts the whole bracket.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from . import config, sleeper


@dataclass
class Bill:
    owner_id: str
    spent: int
    owed: int

    @property
    def share(self) -> float:
        return 0.0


@dataclass
class Settlement:
    bills: List[Bill]
    total: int
    to_chase: int
    to_champion: int
    cap: int
    chase_winner: Optional[str] = None
    champion: Optional[str] = None
    to_second: int = 0
    to_third: int = 0
    cap_is_derived: bool = False

    def owed(self, owner_id: str) -> int:
        for b in self.bills:
            if b.owner_id == owner_id:
                return b.owed
        return 0

    @property
    def overflow(self) -> int:
        return self.to_champion + self.to_second + self.to_third


def pool() -> Optional[float]:
    """Total prize money, or None while the buy-in is unsettled."""
    b = config.buy_in()
    return None if b is None else b * int(config.league()["teams"])


def prize(place: str) -> Optional[float]:
    """What first / second / third pays, before any pot overflow."""
    p = pool()
    if p is None:
        return None
    return p * config.payout_split().get(place, 0) / 100.0


def cap_amount() -> tuple:
    """(cap in dollars, whether it was derived from the payout).

    `pot_cap: third_place` is the voted rule. It can only be computed once the
    buy-in exists, so until then this falls back to the old fixed number rather
    than silently capping at zero - which would hand the whole pot to the
    champion and look like a rule nobody agreed to.
    """
    fr = config.faab_rules()
    setting = fr.get("pot_cap")
    if str(setting) == "third_place":
        third = prize("third")
        if third is None:
            return int(fr.get("pot_cap_fallback", 200)), False
        return int(round(third)), True
    return int(setting), False


def _share(amount: int, split: Dict[str, float]) -> Dict[str, int]:
    """Split whole dollars by percentage. Rounding remainder goes to the
    champion, because somebody counting out change at the bar is worse than
    the champion being a dollar up."""
    out = {k: int(round(amount * v / 100.0)) for k, v in split.items()}
    out["first"] += amount - sum(out.values())
    return out


def settle(spend_by_owner: Dict[str, int], *, chase_winner: str = None,
           champion: str = None) -> Settlement:
    fr = config.faab_rules()
    budget = int(fr["budget"])
    cap, derived = cap_amount()
    bills = [Bill(owner_id=str(o), spent=int(s), owed=max(0, budget - int(s)))
             for o, s in sorted(spend_by_owner.items(), key=lambda kv: -int(kv[1]))]
    total = sum(b.owed for b in bills)
    to_chase = min(total, cap)
    over = total - to_chase

    if str(fr.get("overflow_to")) == "bracket":
        cut = _share(over, config.payout_split())
        first, second, third = cut["first"], cut["second"], cut["third"]
    else:
        first, second, third = over, 0, 0

    return Settlement(bills=bills, total=total, to_chase=to_chase,
                      to_champion=first, to_second=second, to_third=third,
                      cap=cap, cap_is_derived=derived,
                      chase_winner=chase_winner, champion=champion)


# --------------------------------------------------------------------------
# live tracking
# --------------------------------------------------------------------------

def weekly_spend(league_id: str, weeks: Sequence[int]) -> Dict[str, List[int]]:
    """FAAB spent per owner per week, from Sleeper's transaction log.

    Only completed waiver claims carry a bid. Free-agent adds cost nothing, and
    failed claims are `status != 'complete'`, so neither should count against a
    manager's burn.
    """
    roster_owner = {int(r["roster_id"]): str(r.get("owner_id"))
                    for r in sleeper.get_rosters(league_id)}
    out: Dict[str, List[int]] = {o: [0] * len(weeks) for o in roster_owner.values() if o}

    for i, wk in enumerate(weeks):
        for txn in sleeper.get_transactions(league_id, wk) or []:
            if txn.get("status") != "complete" or txn.get("type") != "waiver":
                continue
            bid = int((txn.get("settings") or {}).get("waiver_bid") or 0)
            if not bid:
                continue
            for rid in txn.get("roster_ids") or []:
                owner = roster_owner.get(int(rid))
                if owner and owner in out:
                    out[owner][i] += bid
    return out


def burndown(weekly: Dict[str, List[int]]) -> Dict[str, List[int]]:
    """Cumulative spend, which is what the chart plots. The gap between a line
    and the budget ceiling in the final week is the bill."""
    return {o: _cumulative(v) for o, v in weekly.items()}


def _cumulative(xs: Sequence[int]) -> List[int]:
    total, out = 0, []
    for x in xs:
        total += int(x)
        out.append(total)
    return out


def spend_from_rosters(league_id: str) -> Dict[str, int]:
    """Sleeper tracks remaining budget on the roster itself
    (`settings.waiver_budget_used`), which is the authoritative number once the
    season is over - use it rather than replaying transactions."""
    out: Dict[str, int] = {}
    for r in sleeper.get_rosters(league_id):
        owner = str(r.get("owner_id") or "")
        if not owner:
            continue
        out[owner] = int((r.get("settings") or {}).get("waiver_budget_used") or 0)
    return out
