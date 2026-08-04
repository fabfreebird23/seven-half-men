"""The consolation pot, funded by unspent FAAB.

Whatever waiver budget you did not spend by the end of the season, you owe.
Every dollar comes due - the cap does not forgive anything, it only decides who
gets paid: the first $cap goes to the Chase-bracket winner and everything above
it goes to the league champion. That way the consolation prize can never rival
the title while a quiet October still costs you.
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

    def owed(self, owner_id: str) -> int:
        for b in self.bills:
            if b.owner_id == owner_id:
                return b.owed
        return 0


def settle(spend_by_owner: Dict[str, int], *, chase_winner: str = None,
           champion: str = None) -> Settlement:
    fr = config.faab_rules()
    budget, cap = int(fr["budget"]), int(fr["pot_cap"])
    bills = [Bill(owner_id=str(o), spent=int(s), owed=max(0, budget - int(s)))
             for o, s in sorted(spend_by_owner.items(), key=lambda kv: -int(kv[1]))]
    total = sum(b.owed for b in bills)
    to_chase = min(total, cap)
    return Settlement(bills=bills, total=total, to_chase=to_chase,
                      to_champion=total - to_chase, cap=cap,
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
