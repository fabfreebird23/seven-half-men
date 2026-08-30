"""Who is allowed to sit on a taxi squad.

Sleeper cannot police this for us. It gates taxi on NFL experience
(`taxi_allow_vets: 0`) and nothing else, so it will happily let someone stash a
player they picked up off waivers. This is the check that catches it, and it
was checking the wrong thing until 2026-08-31.
"""
from __future__ import annotations

from halfmen import taxi


def pod(pid, name, position="RB", year=1):
    return taxi.Pod(player_id=pid, name=name, position=position,
                    drafted_season=2026, year=year)


class FakeHistory:
    """`eligible` is the taxi rule: any rookie you DRAFTED, either board."""
    def __init__(self, eligible=(), rookie_draft=()):
        self._e, self._rd = set(eligible), set(rookie_draft)

    def is_rookie_keeper_eligible(self, pid):
        return pid in self._e

    def has_rookie_draft_provenance(self, pid):
        return pid in self._rd


def test_a_rookie_taken_in_the_veteran_draft_is_a_legal_stash():
    """This checked rookie-draft provenance until 2026-08-31, which would have
    told a manager to drop a perfectly legal stash - a rookie taken in the 12th
    of the veteran draft is exactly as eligible as one taken 1.01 in the rookie
    draft. From 2027 there is one draft and the distinction stops existing."""
    hist = FakeHistory(eligible={"vet-rook", "early-rook"}, rookie_draft={"early-rook"})
    bay = taxi.Bay(owner_id="o", pods=[pod("vet-rook", "Late Rook"),
                                       pod("early-rook", "Early Rook")])
    assert taxi.compliance({"o": bay}, hist) == {}


def test_a_waiver_pickup_on_taxi_is_still_flagged():
    """What disqualifies him is arriving by waiver rather than by draft."""
    hist = FakeHistory(eligible=set())
    bay = taxi.Bay(owner_id="o", pods=[pod("wire-guy", "Wire Guy", "WR")])
    assert [p.name for p in taxi.compliance({"o": bay}, hist)["o"]] == ["Wire Guy"]


def test_a_legal_bay_reports_nobody():
    hist = FakeHistory(eligible={"a", "b"})
    bay = taxi.Bay(owner_id="o", pods=[pod("a", "A"), pod("b", "B")])
    assert taxi.compliance({"o": bay}, hist) == {}


def test_the_eligibility_note_says_either_board_and_the_kickoff_lock():
    """Two surfaces render this string. It told managers 'that year's rookie
    draft only' - the old rule - on both of them."""
    note = taxi.eligibility_note()
    assert "either board" in note
    assert "kickoff" in note
