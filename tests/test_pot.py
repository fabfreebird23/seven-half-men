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


# ------------------------------------------------- FAAB moved by trade

def test_traded_faab_is_not_spend():
    """A transfer is not a purchase. The money has only changed hands, so it
    creates no liability until somebody actually bids it."""
    s = pot.settle({"seller": 0, "buyer": 0}, traded={"buyer": 50, "seller": -50})
    assert s.total == 0
    assert s.owed("seller") == 0 and s.owed("buyer") == 0


def test_a_manager_who_bought_budget_is_billed_for_all_of_it():
    """The leak this fixes. The bill used to be capped at a flat budget, so a
    manager who traded in $50 and spent $150 was billed $100 - and the $50 he
    bought went to the seller instead of into the pot."""
    s = pot.settle({"buyer": 150}, traded={"buyer": 50})
    assert s.owed("buyer") == 150, "every dollar bid comes due, bought or not"
    assert s.total == 150


def test_selling_budget_lowers_what_you_can_be_billed():
    """He can no longer bid it, so he can no longer owe it."""
    s = pot.settle({"seller": 100}, traded={"seller": -40})
    b = next(x for x in s.bills if x.owner_id == "seller")
    assert b.entitlement == 60
    assert b.owed == 60, "a $100 figure against a $60 entitlement is bad data"


def test_a_trade_moves_the_bill_but_not_the_pot_total():
    """The league spends what the league spends. Who owes it changes; how much
    reaches the Chase does not."""
    no_trade = pot.settle({"a": 80, "b": 60})
    traded = pot.settle({"a": 40, "b": 100}, traded={"b": 40, "a": -40})
    assert no_trade.total == traded.total == 140


def test_the_bill_still_cannot_exceed_what_he_could_have_bid():
    """The cap is not gone, it just knows about trades now. An invoice to a
    real person should never exceed his entitlement."""
    s = pot.settle({"a": 999}, traded={"a": 25})
    assert s.owed("a") == 125


def test_the_trade_columns_are_reported_for_the_page():
    s = pot.settle({"a": 10}, traded={"a": 30})
    b = next(x for x in s.bills if x.owner_id == "a")
    assert (b.received, b.sent, b.entitlement) == (30, 0, 130)
    s2 = pot.settle({"a": 10}, traded={"a": -30})
    b2 = next(x for x in s2.bills if x.owner_id == "a")
    assert (b2.received, b2.sent, b2.entitlement) == (0, 30, 70)


def test_settle_without_a_trade_log_behaves_exactly_as_before():
    """Every existing caller passes no `traded`, and must be unaffected."""
    assert pot.settle(SPENDS).total == pot.settle(SPENDS, traded={}).total


def test_the_trade_log_reads_sleepers_waiver_budget_array(monkeypatch):
    """Sleeper records a traded budget on the TRADE, not as a waiver claim."""
    monkeypatch.setattr(pot.sleeper, "get_rosters", lambda lid: [
        {"roster_id": 1, "owner_id": "alice"}, {"roster_id": 2, "owner_id": "bob"}])
    monkeypatch.setattr(pot.sleeper, "get_transactions", lambda lid, wk: (
        [{"type": "trade", "status": "complete",
          "waiver_budget": [{"sender": 1, "receiver": 2, "amount": 25}]}] if wk == 3 else []))
    moves = pot.faab_trades("x", weeks=range(1, 6))
    assert moves == [{"week": 3, "amount": 25, "from": "alice", "to": "bob"}]
    assert pot.traded_net("x", weeks=range(1, 6)) == {"bob": 25, "alice": -25}


def test_an_incomplete_trade_moves_nothing(monkeypatch):
    monkeypatch.setattr(pot.sleeper, "get_rosters", lambda lid: [
        {"roster_id": 1, "owner_id": "alice"}, {"roster_id": 2, "owner_id": "bob"}])
    monkeypatch.setattr(pot.sleeper, "get_transactions", lambda lid, wk: [
        {"type": "trade", "status": "failed",
         "waiver_budget": [{"sender": 1, "receiver": 2, "amount": 25}]}])
    assert pot.faab_trades("x", weeks=[1]) == []
