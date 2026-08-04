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


def test_cap_splits_the_pot_between_chase_winner_and_champion():
    s = pot.settle(SPENDS, chase_winner="clay", champion="taco")
    assert s.to_chase == 200
    assert s.to_champion == 38
    assert s.to_chase + s.to_champion == s.total


def test_nothing_stays_with_the_owners():
    s = pot.settle(SPENDS)
    assert s.to_chase + s.to_champion == sum(b.owed for b in s.bills)


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
    assert fr["budget"] == 100 and fr["pot_cap"] == 200
    s = pot.settle({"a": 0})
    assert s.owed("a") == fr["budget"]
    assert s.cap == fr["pot_cap"]
