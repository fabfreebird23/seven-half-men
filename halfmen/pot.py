"""The consolation pot, funded by FAAB actually spent.

Every waiver dollar you bid is a real dollar you owe at the end of the season.
Win a player for $30 of FAAB and you owe $30. Sit on your budget all year and
you owe nothing.

This was the other way round until 2026-08-30 - unspent budget was the thing
that came due - and the inversion matters, because the two rules point managers
in opposite directions. Charging for unspent money tells everyone to burn their
budget; charging for spend puts a real price on every claim, so a bid has to be
worth actual money rather than just worth more than the next guy's bid.

The cap does not forgive anything. It only decides who gets paid.

The cap is the THIRD-PLACE PRIZE rather than a fixed number (league vote,
2026-08-06). Deriving it is the point: at a flat $200 against an $800 pool, a
bubble team in week 14 was roughly indifferent between sneaking into the bracket
and missing on purpose to play for the pot, which is a tanking incentive sitting
in the foundation. Pinned to third place it cannot outrank a playoff finish at
any buy-in, and it needs no re-vote when the buy-in changes.

Whatever is left over rejoins the prize pool instead of landing entirely on the
champion, so a heavy-spending year lifts the whole bracket. The Chase winner
takes a slice of that too, and the arithmetic lands somewhere neat: their total
is the cap plus 10% of overflow, and third place is the third-place prize plus
10% of overflow - the same number, once the pot clears the cap. Below the cap
the Chase winner takes the whole (smaller) pot. So the consolation ties a
playoff finish at worst and never beats one.
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
    # FAAB moved by trade. `entitlement` is what this manager could legitimately
    # bid all season: the budget, plus anything traded in, minus anything traded
    # out. It is the cap on the bill - not a flat budget - because a manager who
    # bought $50 of someone else's FAAB can legitimately spend $150.
    received: int = 0
    sent: int = 0
    entitlement: int = 0

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
    to_chase_bonus: int = 0
    cap_is_derived: bool = False

    def owed(self, owner_id: str) -> int:
        for b in self.bills:
            if b.owner_id == owner_id:
                return b.owed
        return 0

    @property
    def overflow(self) -> int:
        return self.to_champion + self.to_second + self.to_third + self.to_chase_bonus

    @property
    def chase_total(self) -> int:
        """What the Chase winner actually walks away with."""
        return self.to_chase + self.to_chase_bonus

    @property
    def third_total(self) -> int:
        """Third place, prize plus their slice of overflow. Equal to
        `chase_total` once the pot clears the cap - see the module docstring."""
        base = prize("third")
        return int(round(base or 0)) + self.to_third


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
           champion: str = None, traded: Dict[str, int] = None) -> Settlement:
    """Who owes what. `traded` is owner -> NET FAAB received by trade, so a
    manager who bought budget is billed for all of it when he spends it.

    Without that, trading FAAB quietly drained the pot. The bill used to be
    capped at a flat budget, so a manager who traded in $50 and then spent $150
    was billed $100 - and the $50 he bought went to the seller instead of into
    the pot. It is still a cap, because an invoice to a real person should not
    exceed what he could possibly have bid; it just now knows what that is.
    """
    fr = config.faab_rules()
    budget = int(fr["budget"])
    cap, derived = cap_amount()
    net = {str(k): int(v) for k, v in (traded or {}).items()}

    def bill(owner: str, spent: int) -> Bill:
        n = net.get(str(owner), 0)
        ent = max(0, budget + n)
        return Bill(owner_id=str(owner), spent=max(0, int(spent)),
                    owed=min(ent, max(0, int(spent))),
                    received=max(0, n), sent=max(0, -n), entitlement=ent)

    bills = [bill(o, s)
             for o, s in sorted(spend_by_owner.items(), key=lambda kv: -int(kv[1]))]
    total = sum(b.owed for b in bills)
    to_chase = min(total, cap)
    over = total - to_chase

    if str(fr.get("overflow_to")) == "bracket":
        cut = _share(over, config.overflow_split())
        first, second, third, bonus = (cut["first"], cut["second"],
                                       cut["third"], cut["chase"])
    else:
        first, second, third, bonus = over, 0, 0, 0

    return Settlement(bills=bills, total=total, to_chase=to_chase,
                      to_champion=first, to_second=second, to_third=third,
                      to_chase_bonus=bonus, cap=cap, cap_is_derived=derived,
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


def faab_trades(league_id: str, weeks: Sequence[int] = None) -> List[dict]:
    """Every FAAB dollar moved between managers, from the transaction log.

    Sleeper records a traded budget as a `waiver_budget` array on the trade:
    [{"sender": roster_id, "receiver": roster_id, "amount": n}]. It is NOT a
    waiver claim and must never be counted as spend - the money has not been
    used yet, it has only changed hands.
    """
    roster_owner = {int(r["roster_id"]): str(r.get("owner_id") or "")
                    for r in sleeper.get_rosters(league_id)}
    weeks = list(weeks or range(1, 19))
    out: List[dict] = []
    for wk in weeks:
        try:
            rows = sleeper.get_transactions(league_id, wk) or []
        except Exception:
            continue
        for t in rows:
            if t.get("status") != "complete":
                continue
            for mv in (t.get("waiver_budget") or []):
                try:
                    amt = int(mv.get("amount") or 0)
                except (TypeError, ValueError):
                    continue
                if amt <= 0:
                    continue
                out.append({
                    "week": wk, "amount": amt,
                    "from": roster_owner.get(int(mv.get("sender") or -1), ""),
                    "to": roster_owner.get(int(mv.get("receiver") or -1), ""),
                })
    return out


def traded_net(league_id: str, weeks: Sequence[int] = None) -> Dict[str, int]:
    """owner -> net FAAB received by trade. Negative means they sold budget."""
    net: Dict[str, int] = {}
    for mv in faab_trades(league_id, weeks):
        if mv["to"]:
            net[mv["to"]] = net.get(mv["to"], 0) + mv["amount"]
        if mv["from"]:
            net[mv["from"]] = net.get(mv["from"], 0) - mv["amount"]
    return net


def spend_from_rosters(league_id: str) -> Dict[str, int]:
    """FAAB actually bid on waiver claims, per owner.

    Read off `settings.waiver_budget_used` rather than replayed from the log,
    because it is the number Sleeper itself settles on at season end.

    It counts WAIVER SPEND only. Budget moved by trade does not appear here,
    which is correct: a transfer is not a purchase. The trade shows up instead
    in `traded_net`, where it raises or lowers what that manager is allowed to
    spend - see settle().
    """
    out: Dict[str, int] = {}
    for r in sleeper.get_rosters(league_id):
        owner = str(r.get("owner_id") or "")
        if not owner:
            continue
        out[owner] = int((r.get("settings") or {}).get("waiver_budget_used") or 0)
    return out
