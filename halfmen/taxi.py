"""The taxi bay.

Two slots, two-year clocks, any rookie you drafted that year, and
promotion is permanent. The interesting part is not the rules - it is the
squeeze: a team holding last year's stash a second season has nowhere to put
this year's rookie picks, and that tension is what this module surfaces.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from . import config, sleeper


@dataclass
class Pod:
    player_id: str
    name: str
    position: str
    drafted_season: int
    year: int                    # 1 or 2 of the clock

    @property
    def expiring(self) -> bool:
        return self.year >= int(config.taxi_rules()["years"])


@dataclass
class Bay:
    owner_id: str
    pods: List[Pod]
    incoming_picks: int = 0

    @property
    def slots(self) -> int:
        return int(config.taxi_rules()["slots"])

    @property
    def free(self) -> int:
        return max(0, self.slots - len(self.pods))

    @property
    def expiring(self) -> List[Pod]:
        return [p for p in self.pods if p.expiring]

    @property
    def squeeze(self) -> int:
        """How many incoming rookies have nowhere to go if nothing moves.
        Expiring pods don't count as occupied for next year - they have to
        resolve one way or the other."""
        room = self.free + len(self.expiring)
        return max(0, self.incoming_picks - room)


def build(league_id: str = None, season: int = None) -> Dict[str, Bay]:
    """Read the taxi squads off Sleeper's rosters."""
    league_id = league_id or config.league_id()
    season = int(season or config.season())
    players = {}
    try:
        players = sleeper.get_players()
    except Exception:
        players = {}

    bays: Dict[str, Bay] = {}
    for r in sleeper.get_rosters(league_id):
        owner = str(r.get("owner_id") or "")
        if not owner:
            continue
        pods = []
        for pid in (r.get("taxi") or []):
            meta = players.get(str(pid)) or {}
            pods.append(Pod(player_id=str(pid),
                            name=meta.get("full_name") or str(pid),
                            position=meta.get("position") or "",
                            drafted_season=season,
                            year=1))
        bays[owner] = Bay(owner_id=owner, pods=pods)
    return bays


def keeps_rookie_status(pod_year: int) -> bool:
    """Does promoting this player off taxi cost him the rookie-keeper tag?

    No. He was an NFL rookie you drafted and you never stopped holding him, so
    the chain the rookie-keeper rule cares about is unbroken. Promotion moves him
    from costing nothing to costing a ROOKIE keeper slot at the last-round price,
    still with no three-year clock.

    Config can tighten this to `second_year_only` if the league decides an early
    promotion should forfeit it.
    """
    mode = str(config.taxi_rules().get("promotion_keeps_rookie_status", "any_year"))
    if mode == "second_year_only":
        return int(pod_year) >= int(config.taxi_rules()["years"])
    return True


def promotion_cost(pod_year: int) -> str:
    """What promoting actually costs, in the league's own terms."""
    if keeps_rookie_status(pod_year):
        return "a rookie keeper slot"
    return "a regular keeper slot, on the three-year clock"


def promote_cost_note() -> str:
    return ("Promoting is permanent - he cannot go back. What it costs you is a "
            "rookie keeper slot, not a regular one: he keeps the designation, the "
            "last-round price and the no-clock, he just stops being free.")


def eligibility_note() -> str:
    t = config.taxi_rules()
    return ("Any rookie you drafted that year, off either board. %d slots, %d-year "
            "clock, never startable. Declared before the first kickoff and locked "
            "after it. They do not count against your bench and they carry over "
            "free." % (int(t["slots"]), int(t["years"])))


def compliance(bays: Dict[str, Bay], hist) -> Dict[str, List[Pod]]:
    """Players sitting on a taxi squad who should not be there.

    Eligibility is any rookie YOU DRAFTED that season, off either board. What
    disqualifies a player is being a veteran, or arriving by waiver or trade
    rather than by draft - not which of our two boards he came off.

    This checked rookie-draft provenance until 2026-08-31, which was the old
    rule and would have flagged a legal stash: a rookie taken in the 12th of
    the veteran draft is exactly as eligible as one taken 1.01 in the rookie
    draft. From 2027 there is one draft and the distinction stops existing.

    Sleeper cannot do this for us either way. It polices taxi by NFL
    experience - `taxi_allow_vets: 0` blocks veterans and nothing else - so it
    will happily let someone stash a player they picked up off waivers.

    `hist` is a history.History; passed in rather than imported so this module
    stays free of the draft-history machinery.

    A player whose rookie status we could not establish is NOT reported. This
    block names people in public, and it did exactly that on the strength of a
    5MB player map failing to load - every rookie taken in the veteran draft
    lost his eligibility at once and three managers were told to drop legal
    stashes. Silence is the right failure here.
    """
    out: Dict[str, List[Pod]] = {}
    known = getattr(hist, "rookie_status_is_known", None)
    for owner, bay in bays.items():
        bad = [p for p in bay.pods
               if (known is None or known(str(p.player_id)))
               and not hist.is_rookie_keeper_eligible(str(p.player_id))]
        if bad:
            out[owner] = bad
    return out


def farm_size(bay: Bay, rookie_keepers: int) -> int:
    """Cheap young assets a team is carrying: taxi costs no keeper slot, so a
    full bay plus a full pair of rookie keepers is four of them at once."""
    return len(bay.pods) + int(rookie_keepers)
