"""The two drums.

Both drafts are ordered by lottery, but they are weighted on different things:

  rookie drum   regular-season record, worst first
  veteran drum  final standing including the Chase bracket, worst first

Either way the champion is forced to the smallest weight no matter what their
record was. Three guardrails sit on top:

  1. no sweep          the rookie drum draws first; whoever wins first choice
                       there cannot win first choice in the veteran drum
  2. no back-to-back   PER DRUM, and first choice only. Win first choice of the
                       rookie draft and you cannot win it again next year - but
                       you are still free to win first choice of the veteran
                       draft that same year, and vice versa. Acquiring a pick by
                       TRADE doesn't burn your eligibility; only winning it does.
  3. champion floor    see above

What comes out is a SELECTION ORDER, not a draft slot. Whoever holds choice 1
takes any spot on the board they want, choice 2 takes any that is left. This
module deliberately does not model that human decision.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

from . import config


@dataclass
class Seat:
    owner_id: str
    weight: int
    label: str = ""
    champion: bool = False
    locked_out: bool = False   # won first choice of THIS drum last year


def build_drum(standings: Sequence[dict], basis: str, *,
               weights: Sequence[int] = None,
               locked_out: Iterable[str] = ()) -> List[Seat]:
    """`standings` is one dict per team:
        {owner_id, wins, final_rank, champion}
    `final_rank` is 1 for the champion through N for the Chase bracket's last
    place. Lower wins / higher final_rank == worse == more balls.
    """
    lr = config.lottery_rules()
    weights = list(weights or config.lottery_weights())
    locked = set(str(x) for x in locked_out)

    champ = next((t for t in standings if t.get("champion")), None)
    rest = [t for t in standings if not t.get("champion")]

    if basis == "final":
        rest.sort(key=lambda t: -int(t["final_rank"]))     # worst final finish first
    else:
        rest.sort(key=lambda t: (int(t["wins"]), int(t.get("final_rank", 0)) * -1))

    ordered = rest + ([champ] if champ and lr.get("champion_floor", True) else [])
    if champ and not lr.get("champion_floor", True):
        ordered = sorted(standings, key=lambda t: int(t["wins"]))

    seats = []
    for i, t in enumerate(ordered):
        w = weights[i] if i < len(weights) else weights[-1]
        seats.append(Seat(owner_id=str(t["owner_id"]), weight=int(w),
                          champion=bool(t.get("champion")),
                          locked_out=str(t["owner_id"]) in locked))
    return seats


def _weighted_pick(seats: Sequence[Seat], rng: random.Random) -> Seat:
    total = sum(s.weight for s in seats)
    r = rng.random() * total
    for s in seats:
        r -= s.weight
        if r <= 0:
            return s
    return seats[-1]


def draw(seats: Sequence[Seat], *, lottery_slots: int = None, protect_top: int = None,
         ban_first: str = None, rng: random.Random = None) -> List[str]:
    """One drawing. Returns owner ids in selection order.

    `lottery_slots` is how many selections the drum actually randomises;
    everyone after that falls in ball-weight order. `protect_top` is how many of
    those a locked-out team is barred from - one, so a team that won first
    choice last year can still win SECOND choice this year.
    """
    lr = config.lottery_rules()
    lottery_slots = int(lottery_slots if lottery_slots is not None else lr.get("lottery_slots", 2))
    protect_top = int(protect_top if protect_top is not None else lr.get("no_repeat_top", 1))
    rng = rng or random

    pool = list(seats)
    order: List[str] = []
    for slot in range(1, lottery_slots + 1):
        eligible = [s for s in pool if not (s.locked_out and slot <= protect_top)]
        if slot == 1 and ban_first:
            eligible = [s for s in eligible if s.owner_id != ban_first]
        if not eligible:                      # everyone left is barred; fall back
            eligible = list(pool)
        hit = _weighted_pick(eligible, rng)
        order.append(hit.owner_id)
        pool = [s for s in pool if s.owner_id != hit.owner_id]
    for s in sorted(pool, key=lambda s: -s.weight):
        order.append(s.owner_id)
    return order


def draw_both(rookie_seats: Sequence[Seat], vet_seats: Sequence[Seat],
              rng: random.Random = None) -> Dict[str, List[str]]:
    """The rookie drum runs first. Its winner is held out of first choice in the
    veteran drum so nobody sweeps both boards in the same year.

    The two drums carry their own lock-out sets - build them with the previous
    year's first-choice winner for THAT drum, not for both.
    """
    lr = config.lottery_rules()
    rng = rng or random
    rookie = draw(rookie_seats, rng=rng)
    ban = rookie[0] if lr.get("no_sweep", True) else None
    vet = draw(vet_seats, ban_first=ban, rng=rng)
    return {"rookie": rookie, "veteran": vet}


def simulate(rookie_seats: Sequence[Seat], vet_seats: Sequence[Seat], n: int = 20000,
             seed: int = None) -> Dict[str, object]:
    """Monte Carlo. Returns per-owner slot distributions for both drums plus a
    sweep count, which should be zero whenever `no_sweep` is on."""
    rng = random.Random(seed)
    size = len(rookie_seats)
    tallies = {
        "rookie": {s.owner_id: [0] * size for s in rookie_seats},
        "veteran": {s.owner_id: [0] * size for s in vet_seats},
    }
    sweeps = 0
    for _ in range(n):
        res = draw_both(rookie_seats, vet_seats, rng=rng)
        for drum, order in res.items():
            key = "rookie" if drum == "rookie" else "veteran"
            for slot, owner in enumerate(order):
                tallies[key][owner][slot] += 1
        if res["rookie"][0] == res["veteran"][0]:
            sweeps += 1

    def pct(d):
        return {o: [c / n * 100 for c in counts] for o, counts in d.items()}

    return {"n": n, "sweeps": sweeps,
            "rookie": pct(tallies["rookie"]), "veteran": pct(tallies["veteran"])}


def median_slot(row: Sequence[float]) -> int:
    cum = 0.0
    for i, p in enumerate(row):
        cum += p
        if cum >= 50:
            return i + 1
    return len(row)


def first_season_order(owner_ids: Sequence[str], seed: int = None) -> List[str]:
    """Year one has no standings, so both orders are drawn flat at random."""
    ids = list(owner_ids)
    random.Random(seed).shuffle(ids)
    return ids
