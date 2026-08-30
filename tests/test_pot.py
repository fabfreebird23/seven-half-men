"""FAAB settlement: the cap decides who gets paid, not how much comes due.

You owe what you SPEND (league decision, 2026-08-30). It ran the other way
round until then - unspent budget was the thing that came due - and the two
rules point managers in opposite directions, so the inversion is asserted here
rather than left to the module docstring.
"""
from __future__ import annotations

import pytest

from halfmen import config, pot

# The simulated 2029 spends. $562 of real money across eight teams.
SPENDS = {"bijan": 100, "beant": 96, "amonra": 83, "taco": 74,
          "clay": 91, "whig": 62, "later": 11, "nabers": 45}


def test_every_dollar_you_spend_comes_due():
    s = pot.settle(SPENDS)
    assert s.total == sum(SPENDS.values()) == 562


def test_an_untouched_budget_owes_nothing():
    """The headline consequence of the inversion. Sitting on your budget is
    free; it used to be the most expensive thing you could do."""
    s = pot.settle({"a": 0, "b": 0, "c": 0})
    assert s.total == 0
    assert s.owed("a") == 0
    assert s.to_chase == 0 and s.overflow == 0, "an empty pot pays nobody"


def test_spending_the_whole_budget_owes_the_whole_budget():
    s = pot.settle(SPENDS)
    assert s.owed("bijan") == 100


def test_the_big_spender_owes_the_most():
    s = pot.settle(SPENDS)
    assert s.owed("later") == 11, "barely bid, barely billed"
    assert max(b.owed for b in s.bills) == 100


def test_the_cap_is_the_third_place_prize():
    """Voted 2026-08-06. A fixed $200 against an $800 pool left a bubble team
    roughly indifferent between sneaking into the bracket and missing on purpose
    to play for the pot. Pinned to third place it cannot outrank a playoff
    finish, and it re-derives itself if the buy-in ever changes."""
    cap, derived = pot.cap_amount()
    assert derived, "the buy-in is set, so it should not be falling back"
    assert cap == pot.prize("third") == 120


def test_the_cap_falls_back_rather_than_capping_at_zero(monkeypatch):
    """An unset buy-in must not silently hand the whole pot to the champion."""
    monkeypatch.setattr(config, "buy_in", lambda: None)
    cap, derived = pot.cap_amount()
    assert not derived and cap == 200


def test_overflow_is_split_four_ways():
    s = pot.settle(SPENDS, chase_winner="clay", champion="taco")
    assert s.to_chase == 120, "capped at third-place money"
    over = s.to_champion + s.to_second + s.to_third + s.to_chase_bonus
    assert over == s.total - s.to_chase
    assert s.to_chase + s.overflow == s.total


def test_the_chase_winner_and_third_place_take_home_the_same_amount():
    """The point of the matching 10/10 at the bottom of the overflow split: once
    the pot clears the cap, the consolation TIES a playoff finish exactly."""
    for spends in ({"a": 100, "b": 60, "c": 20, "d": 30},
                   {"a": 100, "b": 100, "c": 100, "d": 100}):
        s = pot.settle(spends)
        assert s.total > s.cap, "this case is meant to clear the cap"
        assert s.chase_total == s.third_total, spends


def test_below_the_cap_the_chase_winner_takes_less_than_third_place():
    """Not a wrinkle - it is the right way round. A small pot means everyone
    played, and the consolation should not out-earn a playoff finish for it."""
    s = pot.settle({"a": 30, "b": 20, "c": 15})
    assert s.total == 65 < s.cap
    assert s.chase_total == s.total < s.third_total


def test_a_pot_smaller_than_the_cap_goes_entirely_to_the_chase_winner():
    """Which is right: a small pot means everybody actually played, and that is
    the year the consolation prize most needs the help."""
    s = pot.settle({"a": 5, "b": 4, "c": 6})
    assert s.total == 15 and s.to_chase == 15
    assert s.overflow == 0


def test_the_rounding_remainder_goes_to_the_champion():
    """Rather than leaving somebody to count out change at the bar."""
    s = pot.settle(SPENDS)
    assert (s.to_chase + s.to_champion + s.to_second + s.to_third
            + s.to_chase_bonus) == s.total


def test_champion_only_overflow_still_works(monkeypatch):
    """The old behaviour is still one config value away."""
    fr = dict(config.faab_rules(), overflow_to="champion")
    monkeypatch.setattr(config, "faab_rules", lambda: fr)
    s = pot.settle(SPENDS)
    assert s.to_second == s.to_third == 0
    assert s.to_chase + s.to_champion == s.total


def test_nothing_stays_with_the_owners():
    s = pot.settle(SPENDS)
    assert s.to_chase + s.overflow == sum(b.owed for b in s.bills)


def test_a_pot_under_the_cap_leaves_the_champion_nothing():
    tight = {k: 5 for k in SPENDS}           # $40 total
    s = pot.settle(tight)
    assert s.total == 40
    assert s.to_chase == 40 and s.to_champion == 0


def test_a_bill_can_never_exceed_the_budget():
    """Sleeper should never report more spent than the budget allows, but a
    bill for $120 against a $100 budget would be a real invoice to a real
    person, so it is clamped rather than trusted."""
    s = pot.settle({"a": 120, "b": 50})
    assert s.owed("a") == 100
    assert s.total == 150


def test_bills_are_sorted_biggest_spender_first():
    s = pot.settle(SPENDS)
    assert [b.owner_id for b in s.bills][0] == "bijan"


def test_burndown_is_cumulative():
    weekly = {"a": [10, 0, 5, 0, 20]}
    assert pot.burndown(weekly)["a"] == [10, 10, 15, 15, 35]


def test_settlement_uses_the_configured_budget_and_cap():
    fr = config.faab_rules()
    assert fr["budget"] == 100 and fr["pot_cap"] == "third_place"
    s = pot.settle({"a": fr["budget"]})
    assert s.owed("a") == fr["budget"]
    assert s.cap == pot.cap_amount()[0], "the cap is derived, not read straight off config"
