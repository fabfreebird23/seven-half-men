"""Keeper pricing.

The whole ruleset in one place:

  regular keepers    yr1  cheaper of (drafted round, current ADP round)
                     yr2  cheaper of (drafted round - 3, current ADP round)
                     yr3  ADP, no choice
                     yr4  the wall - gone unless franchised

  rookie keepers     your last pick, then the one before it (R14, R13).
                     No clock. Must have been DRAFTED in his NFL rookie season,
                     in either draft. Trading him converts him to a regular
                     keeper at his original draft round with the clock at yr 1.

  franchise          one player, years 4 and 5, price frozen at the most
                     EXPENSIVE (earliest) round you have ever paid for him.
                     Gone after year 5.

  owning the pick    a keeper has to land on a pick you actually hold. If his
                     round is gone he bumps to the next-EARLIEST round you own,
                     and two keepers can never share a round. The price itself
                     travels with the player on a trade - the bump is recomputed
                     for whoever owns him at submission time.

"Cheaper" always means the LATER round. Round 1 is the most expensive pick on
the board, round 14 the least.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from . import config

WALL = object()  # sentinel: no legal price, the player has aged out

# A player who came in through the ROOKIE draft has no veteran draft round to
# price against, so this stands in for one. In year one it is FLAT - no ADP
# option, no cheaper-of. From year two the normal ladder resumes with it as the
# anchor: 5 -> 2 -> ADP. Tunable in config; this is only the default.
R5_ROOKIE_PREMIUM = 5


def rookie_draft_premium() -> int:
    return int(config.keeper_rules().get("rookie_draft_premium_round", R5_ROOKIE_PREMIUM))


def waiver_anchor(last_round: int = None) -> int:
    """An undrafted pickup has no draft round either, but he gets no premium -
    he prices off your last available pick, same as he always has."""
    return int(last_round if last_round else config.veteran_rounds())


@dataclass
class Price:
    """What one player costs one manager this offseason."""
    player_id: str
    name: str
    position: str
    kind: str                      # regular | rookie | franchise
    year: int                      # keeper year this would be (1-based)
    base_round: Optional[int]      # the rule's price before any bump
    final_round: Optional[int]     # where he actually lands
    adp_round: Optional[int]
    options: List[int] = field(default_factory=list)   # legal choices before bumping
    bumped: bool = False
    eligible: bool = True
    reason: str = ""
    from_rookie_draft: bool = False   # priced off the rookie-draft premium

    @property
    def surplus(self) -> Optional[int]:
        """Rounds of value: what the market says minus what you pay. Positive is
        good - paying a 9th for a 2nd-round player is +7."""
        if self.final_round is None or self.adp_round is None:
            return None
        return self.final_round - self.adp_round


# --------------------------------------------------------------------------
# the price rules
# --------------------------------------------------------------------------

def regular_options(anchor_round: Optional[int], year: int, adp_round: Optional[int],
                    *, from_rookie_draft: bool = False) -> List[int]:
    """Legal prices for a regular keeper entering `year` (1-based). Empty means
    he has hit the wall.

    `anchor_round` is the round the ladder is computed from - a player's veteran
    draft round normally, or the rookie-draft premium for someone who never had
    one. Pass `from_rookie_draft=True` and `anchor_round` is ignored.
    """
    kr = config.keeper_rules()
    if year > int(kr["max_years"]):
        return []

    # ORDER MATTERS. A rookie-draft player has no veteran round to feed the
    # cheaper-of branch below, so this has to be resolved first or that branch
    # gets None and either raises or silently prices him wrong.
    if from_rookie_draft:
        anchor_round = rookie_draft_premium()
        if year == 1:
            return [anchor_round]          # flat. No ADP option, no choice.

    if anchor_round is None:
        anchor_round = waiver_anchor()

    allow_adp = bool(kr.get("adp_discount", True))
    # The ADP option is RELIEF FROM THE LADDER, not a discount below what he
    # cost you. It may never price a drafted player later than the round he
    # was drafted in.
    #
    # Without the floor, a player who fell after the draft got cheaper than he
    # was drafted: Wan'Dale Robinson went in the 9th, the market moved him to
    # a 14th, and the board offered him back at R14 - a last-round price. The
    # last round is for two things only, a rookie-designated keeper and a
    # player who was never drafted here at all, and he is neither. Keeping a
    # 9th-rounder costs a 9th-round pick.
    floor = anchor_round if bool(kr.get("adp_never_beats_draft_round", True)) else None

    def relief(adp: Optional[int]) -> Optional[int]:
        if not (allow_adp and adp):
            return None
        return min(adp, floor) if floor else adp

    if year == 1:
        opts = [anchor_round, relief(adp_round)]
    elif year == 2:
        bumped = max(1, anchor_round - int(kr["year2_bump"]))
        opts = [bumped, relief(adp_round)]
    else:  # year three takes the market, no choice
        opts = [adp_round] if adp_round else [anchor_round]

    # dedupe, cheapest (latest round) first
    return sorted(set(r for r in opts if r), reverse=True)


def recommended(options: Sequence[int]) -> Optional[int]:
    """The cheapest legal price - the latest round."""
    return max(options) if options else None


def franchise_price(peak_round: int) -> int:
    """Frozen at the most expensive round ever paid. Earlier round = higher price,
    so the peak is the MINIMUM round number."""
    return int(peak_round)


def franchise_years() -> Sequence[int]:
    fr = config.franchise_rules()
    start = int(config.keeper_rules()["max_years"]) + 1
    return list(range(start, start + int(fr["extra_years"])))


def rookie_cost_rounds(count: int, last_round: int) -> List[int]:
    """Rookie keepers cost your last picks, cheapest first: R14, then R13."""
    return [last_round - i for i in range(count)]


# --------------------------------------------------------------------------
# owning the pick
# --------------------------------------------------------------------------

def adjust_to_owned(round_: int, owned: Counter, taken: Counter = None) -> Optional[int]:
    """Move `round_` to the next-EARLIEST round this manager still owns and has
    not already spent on another keeper. Returns None if nothing is left.

    Bumping goes UP the board (7 -> 6 -> 5), which costs the manager a more
    valuable pick. That is the intended penalty for having traded the round away.
    """
    taken = taken or Counter()
    r = int(round_)
    while r >= 1:
        if owned.get(r, 0) - taken.get(r, 0) > 0:
            return r
        r -= 1
    return None


def allocate(prices: List[Price], owned: Optional[Counter]) -> List[Price]:
    """Settle a whole slip at once.

    Order matters: the most expensive keepers claim their rounds first, so a
    cheap keeper is the one that gets pushed, not the stud. Mutates and returns
    the same Price objects.
    """
    if owned is None or not config.keeper_rules().get("enforce_owned_picks", True):
        for p in prices:
            p.final_round = p.base_round
        return prices

    taken: Counter = Counter()
    # earliest base round first == most expensive first
    for p in sorted([x for x in prices if x.base_round], key=lambda x: x.base_round):
        landed = adjust_to_owned(p.base_round, owned, taken)
        if landed is None:
            p.final_round = None
            p.eligible = False
            p.reason = "no owned pick left to land on"
        else:
            p.final_round = landed
            p.bumped = landed != p.base_round
            taken[landed] += 1
    return prices


# --------------------------------------------------------------------------
# building a Price
# --------------------------------------------------------------------------

def price_regular(player_id: str, name: str, position: str, *,
                  draft_round: Optional[int], year: int, adp_round: Optional[int],
                  from_rookie_draft: bool = False) -> Price:
    opts = regular_options(draft_round, year, adp_round, from_rookie_draft=from_rookie_draft)
    base = recommended(opts)
    p = Price(player_id=player_id, name=name, position=position, kind="regular",
              year=year, base_round=base, final_round=base, adp_round=adp_round,
              options=list(opts), from_rookie_draft=from_rookie_draft)
    if not opts:
        p.eligible = False
        p.reason = "year %d - past the three-year wall, franchise him or lose him" % year
    return p


def price_rookie(player_id: str, name: str, position: str, *, slot: int,
                 last_round: int, adp_round: Optional[int]) -> Price:
    """`slot` is 0 for the first rookie keeper, 1 for the second."""
    rd = last_round - slot
    return Price(player_id=player_id, name=name, position=position, kind="rookie",
                 year=0, base_round=rd, final_round=rd, adp_round=adp_round,
                 options=[rd])


def price_franchise(player_id: str, name: str, position: str, *, peak_round: int,
                    year: int, adp_round: Optional[int]) -> Price:
    fr = config.franchise_rules()
    p = Price(player_id=player_id, name=name, position=position, kind="franchise",
              year=year, base_round=franchise_price(peak_round),
              final_round=franchise_price(peak_round), adp_round=adp_round,
              options=[franchise_price(peak_round)])
    if year >= int(fr["final_year"]):
        p.eligible = False
        p.base_round = p.final_round = None
        p.reason = "year %d - the franchise tag runs out after year %d" % (
            year, int(fr["final_year"]) - 1)
    return p


def convert_traded_rookie(original_draft_round: Optional[int] = None, *,
                          from_rookie_draft: bool = False) -> Dict[str, object]:
    """A rookie keeper who gets traded loses the rookie-keeper status forever.
    For his new owner he is a regular keeper with the clock back at year 1.

    What he costs depends on where he came from. If he was a veteran-draft
    rookie, it is the round he was drafted in. If he came through the rookie
    draft he still has no veteran round, so the premium stands in - the same
    R%d it would have been for the team that drafted him. Keeping the premium
    across a trade is what stops a swap being used to reprice him.
    """ % rookie_draft_premium()
    if from_rookie_draft:
        return {"draft_round": rookie_draft_premium(), "year": 1,
                "from_rookie_draft": True}
    return {"draft_round": int(original_draft_round), "year": 1,
            "from_rookie_draft": False}


# --------------------------------------------------------------------------
# slip validation
# --------------------------------------------------------------------------

def validate(prices: List[Price]) -> List[str]:
    """Problems with a submitted slip, in plain language. There are no position
    caps in this league, so the only real constraints are the slot counts, the
    wall, and owning the picks."""
    kr = config.keeper_rules()
    errs: List[str] = []

    regs = [p for p in prices if p.kind in ("regular", "franchise")]
    rooks = [p for p in prices if p.kind == "rookie"]
    if len(regs) > int(kr["regular"]):
        errs.append("%d regular keepers - you get %d." % (len(regs), int(kr["regular"])))
    if len(rooks) > int(kr["rookie"]):
        errs.append("%d rookie keepers - you get %d." % (len(rooks), int(kr["rookie"])))
    if len(prices) > int(kr["total"]):
        errs.append("%d keepers - the cap is %d." % (len(prices), int(kr["total"])))

    fr = [p for p in prices if p.kind == "franchise"]
    if len(fr) > int(config.franchise_rules()["slots"]):
        errs.append("%d franchise tags - you only have one." % len(fr))

    for p in prices:
        if not p.eligible:
            errs.append("%s: %s" % (p.name, p.reason))

    rounds = Counter(p.final_round for p in prices if p.final_round)
    for rd, n in rounds.items():
        if n > 1:
            errs.append("%d keepers priced at R%d - you only own one." % (n, rd))
    return errs


def total_surplus(prices: List[Price]) -> int:
    return sum(p.surplus or 0 for p in prices)


def best_slip(candidates: List[Price], *, regular: int = None, rookie: int = None) -> List[Price]:
    """Greedy pick of the highest-surplus legal slip. Surplus is additive and the
    slots don't interact, so greedy is optimal here - the only coupling is the
    owned-pick bump, which `allocate` resolves afterwards."""
    kr = config.keeper_rules()
    regular = int(kr["regular"]) if regular is None else regular
    rookie = int(kr["rookie"]) if rookie is None else rookie

    def key(p: Price) -> int:
        return -(p.surplus if p.surplus is not None else -99)

    regs = sorted([p for p in candidates if p.kind in ("regular", "franchise") and p.eligible], key=key)
    rooks = sorted([p for p in candidates if p.kind == "rookie" and p.eligible], key=key)
    return regs[:regular] + rooks[:rookie]
