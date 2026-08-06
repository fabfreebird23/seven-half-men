"""FAAB settlement: the cap decides who gets paid, not how much comes due."""
from __future__ import annotations

import pytest

from halfmen import config, pot

# The simulated 2029 spends. $238 of unspent budget across eight teams.
SPENDS = {"bijan": 100, "beant": 96, "amonra": 83, "taco": 74,
          "clay": 91, "whig": 62, "later": 11, "nabers": 45}


def test_every_unspent_dollar_comes_due():
    s = pot.settle(SPENDS)
    assert s.total == sum(100 - v for v in SPENDS.values()) == 238


def test_a_full_budget_owes_nothing():
    s = pot.settle(SPENDS)
    assert s.owed("bijan") == 0


def test_the_quitter_owes_the_most():
    s = pot.settle(SPENDS)
    assert s.owed("later") == 89
    assert max(b.owed for b in s.bills) == 89


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


def test_overflow_rejoins_the_bracket_in_the_payout_proportions():
    s = pot.settle(SPENDS, chase_winner="clay", champion="taco")
    assert s.to_chase == 120, "capped at third-place money"
    assert (s.to_champion, s.to_second, s.to_third) == (70, 30, 18)
    assert s.to_chase + s.overflow == s.total


def test_a_pot_smaller_than_the_cap_goes_entirely_to_the_chase_winner():
    """Which is right: a small pot means everybody actually played, and that is
    the year the consolation prize most needs the help."""
    s = pot.settle({"a": 90, "b": 95, "c": 100})
    assert s.total == 15 and s.to_chase == 15
    assert s.overflow == 0


def test_the_rounding_remainder_goes_to_the_champion():
    """Rather than leaving somebody to count out change at the bar."""
    s = pot.settle(SPENDS)
    assert s.to_chase + s.to_champion + s.to_second + s.to_third == s.total


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
    tight = {k: 95 for k in SPENDS}          # $40 total
    s = pot.settle(tight)
    assert s.total == 40
    assert s.to_chase == 40 and s.to_champion == 0


def test_overspending_never_produces_a_negative_bill():
    s = pot.settle({"a": 120, "b": 50})
    assert s.owed("a") == 0
    assert s.total == 50


def test_bills_are_sorted_biggest_spender_first():
    s = pot.settle(SPENDS)
    assert [b.owner_id for b in s.bills][0] == "bijan"


def test_burndown_is_cumulative():
    weekly = {"a": [10, 0, 5, 0, 20]}
    assert pot.burndown(weekly)["a"] == [10, 10, 15, 15, 35]


def test_settlement_uses_the_configured_budget_and_cap():
    fr = config.faab_rules()
    assert fr["budget"] == 100 and fr["pot_cap"] == "third_place"
    s = pot.settle({"a": 0})
    assert s.owed("a") == fr["budget"]
    assert s.cap == pot.cap_amount()[0], "the cap is derived, not read straight off config"
