"""Keeper pricing, the wall, the franchise tag and the owned-pick bump."""
from __future__ import annotations

from collections import Counter

import pytest

from halfmen import config, engine


# ---------------------------------------------------------------- regular

def test_year_one_takes_the_cheaper_of_draft_round_and_adp():
    # drafted R6, market says R4 -> R6 is later, so R6 is cheaper
    assert engine.recommended(engine.regular_options(6, 1, 4)) == 6
    # drafted R2, market says R7 -> the market is cheaper
    assert engine.recommended(engine.regular_options(2, 1, 7)) == 7


def test_year_two_costs_your_draft_round_minus_three():
    assert engine.recommended(engine.regular_options(12, 2, 7)) == 9   # 12-3=9 beats R7
    assert engine.recommended(engine.regular_options(7, 2, 2)) == 4    # 7-3=4 beats R2


def test_year_two_floors_at_round_one():
    assert engine.regular_options(3, 2, None) == [1]


def test_year_three_is_adp_with_no_choice():
    opts = engine.regular_options(4, 3, 9)
    assert opts == [9]


def test_year_three_can_move_against_you():
    # drafted R4, market has cooled to R9: year three you pay R9 and it is a loss
    p = engine.price_regular("1", "Cam Skattebo", "RB", draft_round=4, year=3, adp_round=9)
    assert p.final_round == 9
    assert p.surplus == 0
    p2 = engine.price_regular("2", "x", "RB", draft_round=4, year=3, adp_round=2)
    assert p2.surplus == 0, "year three always pays market, so surplus is zero by construction"


def test_year_four_is_the_wall():
    assert engine.regular_options(5, 4, 1) == []
    p = engine.price_regular("1", "Quinshon Judkins", "RB", draft_round=9, year=4, adp_round=1)
    assert not p.eligible
    assert "wall" in p.reason


# ---------------------------------------------------------------- rookie

def test_rookie_keepers_cost_your_last_picks():
    assert engine.rookie_cost_rounds(2, 14) == [14, 13]
    assert engine.rookie_cost_rounds(2, 13) == [13, 12]   # year one, 13-round draft


def test_rookie_keeper_has_no_clock_and_huge_surplus():
    p = engine.price_rookie("1", "Jeremiah Smith", "WR", slot=0, last_round=14, adp_round=1)
    assert p.final_round == 14
    assert p.surplus == 13


def test_traded_rookie_becomes_a_regular_keeper_at_his_original_round():
    got = engine.convert_traded_rookie(3)
    assert got["draft_round"] == 3 and got["year"] == 1
    assert got["from_rookie_draft"] is False


# ---------------------------------------------------------------- franchise

def test_franchise_freezes_at_the_most_expensive_round_ever_paid():
    # peaked at R5, market now says R1 -> you keep paying R5
    p = engine.price_franchise("1", "Quinshon Judkins", "RB", peak_round=5, year=4, adp_round=1)
    assert p.final_round == 5
    assert p.surplus == 4


def test_franchise_is_worth_nothing_on_a_career_first_rounder():
    p = engine.price_franchise("1", "Ashton Jeanty", "RB", peak_round=1, year=4, adp_round=1)
    assert p.surplus == 0


def test_franchise_runs_out_after_year_five():
    p = engine.price_franchise("1", "x", "RB", peak_round=5, year=6, adp_round=1)
    assert not p.eligible


# ---------------------------------------------------------------- owned picks

def test_keeper_bumps_up_to_the_next_round_you_own():
    owned = Counter({r: 1 for r in range(1, 15)})
    del owned[7]                       # traded the 7th
    assert engine.adjust_to_owned(7, owned) == 6


def test_bump_skips_multiple_missing_rounds():
    owned = Counter({r: 1 for r in range(1, 15)})
    for r in (5, 6, 7):
        del owned[r]
    assert engine.adjust_to_owned(7, owned) == 4


def test_two_keepers_cannot_share_a_round():
    owned = Counter({r: 1 for r in range(1, 15)})
    prices = [
        engine.price_regular("a", "A", "RB", draft_round=9, year=1, adp_round=None),
        engine.price_regular("b", "B", "WR", draft_round=9, year=1, adp_round=None),
    ]
    engine.allocate(prices, owned)
    assert sorted(p.final_round for p in prices) == [8, 9]


def test_the_cheap_keeper_is_the_one_that_gets_pushed():
    """Allocation runs most-expensive-first so a stud never gets bumped off his
    own round by a late-round flier."""
    owned = Counter({r: 1 for r in range(1, 15)})
    del owned[4]
    prices = [
        engine.price_regular("cheap", "Cheap", "WR", draft_round=4, year=1, adp_round=None),
        engine.price_regular("stud", "Stud", "RB", draft_round=3, year=1, adp_round=None),
    ]
    engine.allocate(prices, owned)
    by = {p.player_id: p.final_round for p in prices}
    assert by["stud"] == 3
    assert by["cheap"] == 2 and next(p for p in prices if p.player_id == "cheap").bumped


def test_an_extra_pick_acquired_by_trade_absorbs_a_second_keeper():
    owned = Counter({r: 1 for r in range(1, 15)})
    owned[9] = 2                        # traded for a second 9th
    prices = [
        engine.price_regular("a", "A", "RB", draft_round=9, year=1, adp_round=None),
        engine.price_regular("b", "B", "WR", draft_round=9, year=1, adp_round=None),
    ]
    engine.allocate(prices, owned)
    assert [p.final_round for p in prices] == [9, 9]


def test_running_out_of_picks_makes_a_keeper_ineligible():
    owned = Counter({1: 0, 2: 0, 3: 1})
    p = engine.price_regular("a", "A", "RB", draft_round=2, year=1, adp_round=None)
    engine.allocate([p], owned)
    assert not p.eligible


# ---------------------------------------------------------------- slips

def test_no_position_caps_in_this_league():
    prices = [
        engine.price_regular("q1", "QB One", "QB", draft_round=6, year=1, adp_round=4),
        engine.price_rookie("q2", "QB Two", "QB", slot=0, last_round=14, adp_round=6),
        engine.price_regular("t1", "TE One", "TE", draft_round=9, year=1, adp_round=7),
    ]
    assert engine.validate(prices) == []


def test_slot_counts_are_enforced():
    prices = [engine.price_regular(str(i), "P%d" % i, "RB", draft_round=i + 2,
                                   year=1, adp_round=None) for i in range(4)]
    errs = engine.validate(prices)
    assert any("regular keepers" in e for e in errs)


def test_best_slip_maximises_surplus():
    cands = [
        engine.price_regular("a", "A", "RB", draft_round=9, year=1, adp_round=2),   # +7
        engine.price_regular("b", "B", "WR", draft_round=3, year=1, adp_round=3),   # 0
        engine.price_regular("c", "C", "TE", draft_round=12, year=1, adp_round=6),  # +6
        engine.price_regular("d", "D", "WR", draft_round=5, year=1, adp_round=4),   # +1
        engine.price_rookie("e", "E", "WR", slot=0, last_round=14, adp_round=1),    # +13
        engine.price_rookie("f", "F", "QB", slot=1, last_round=14, adp_round=6),    # +7
        engine.price_rookie("g", "G", "RB", slot=0, last_round=14, adp_round=12),   # +2
    ]
    slip = engine.best_slip(cands)
    assert sorted(p.player_id for p in slip) == ["a", "c", "d", "e", "f"]
    assert engine.total_surplus(slip) == 7 + 6 + 1 + 13 + 7


def test_total_surplus_counts_the_bumped_price_not_the_base():
    owned = Counter({r: 1 for r in range(1, 15)})
    del owned[7]
    p = engine.price_regular("a", "Ollie Gordon II", "RB", draft_round=7, year=1, adp_round=5)
    assert p.surplus == 2
    engine.allocate([p], owned)
    assert p.final_round == 6 and p.bumped
    assert p.surplus == 1, "bumping up a round costs you a round of surplus"


# ------------------------------------------- the rookie-draft premium (R5)

def test_a_rookie_draft_pick_costs_the_flat_premium_in_year_one():
    p = engine.price_regular("a", "1.01 pick", "WR", draft_round=None, year=1,
                             adp_round=1, from_rookie_draft=True)
    assert p.final_round == engine.rookie_draft_premium() == 5


def test_the_premium_is_flat_regardless_of_where_he_went_in_the_rookie_draft():
    """1.01 and 2.08 cost the same. Flat is flat."""
    first = engine.price_regular("a", "1.01", "WR", draft_round=None, year=1,
                                 adp_round=1, from_rookie_draft=True)
    last = engine.price_regular("b", "2.08", "RB", draft_round=None, year=1,
                                adp_round=1, from_rookie_draft=True)
    assert first.final_round == last.final_round == 5


def test_year_one_takes_no_adp_option_even_when_adp_is_cheaper():
    """The case that will get reported as a bug: a rookie the market has at R9
    still costs R5, because year one is flat."""
    p = engine.price_regular("a", "quiet rookie", "TE", draft_round=None, year=1,
                             adp_round=9, from_rookie_draft=True)
    assert p.options == [5]
    assert p.final_round == 5
    assert p.surplus == -4, "you are paying a 5th for a 9th-round player"


def test_year_two_resumes_the_ladder_with_the_premium_as_the_anchor():
    """5 minus 3 is 2 - and the cheaper-of option is back on from year two."""
    assert engine.regular_options(None, 2, 1, from_rookie_draft=True) == [2, 1]
    assert engine.recommended(engine.regular_options(None, 2, 1, from_rookie_draft=True)) == 2


def test_year_two_can_still_take_adp_when_the_market_is_cheaper():
    got = engine.recommended(engine.regular_options(None, 2, 7, from_rookie_draft=True))
    assert got == 7, "R7 is later than R2, so it is the cheaper of the two"


def test_year_three_is_the_market_for_a_rookie_draft_player_too():
    assert engine.regular_options(None, 3, 3, from_rookie_draft=True) == [3]


def test_the_wall_still_applies_to_a_rookie_draft_player():
    assert engine.regular_options(None, 4, 3, from_rookie_draft=True) == []


def test_taxi_stash_then_promotion_is_year_one_at_the_premium():
    """Taxi years do not advance the clock. Two years stashed then promoted is
    year 1, not year 3."""
    p = engine.price_regular("a", "Jadyn Davis", "QB", draft_round=None, year=1,
                             adp_round=11, from_rookie_draft=True)
    assert p.year == 1 and p.final_round == 5


def test_a_rookie_keeper_converted_to_a_regular_slot_costs_the_premium():
    p = engine.price_regular("a", "Jeremiah Smith", "WR", draft_round=None, year=1,
                             adp_round=1, from_rookie_draft=True)
    assert p.final_round == 5, "not his R14 rookie-slot price, and not an R1"


def test_a_rookie_draft_pick_redrafted_out_of_the_pool_has_a_real_round():
    """Pool passage resets the clock, and a reset means he is an ordinary
    veteran-draft pick again."""
    p = engine.price_regular("a", "redrafted", "RB", draft_round=11, year=1,
                             adp_round=6, from_rookie_draft=False)
    assert p.final_round == 11


def test_an_undrafted_pickup_gets_no_premium():
    """No rookie-draft provenance, so he prices off your last available pick."""
    assert engine.waiver_anchor() == config.veteran_rounds()
    p = engine.price_regular("a", "waiver find", "WR", draft_round=None, year=1,
                             adp_round=4, from_rookie_draft=False)
    assert p.final_round == config.veteran_rounds()


def test_the_premium_still_has_to_land_on_a_pick_you_own():
    """R5 snaps UP to the nearest earlier owned pick, never down."""
    owned = Counter({r: 1 for r in range(1, 15)})
    for r in (4, 5):
        del owned[r]
    p = engine.price_regular("a", "rookie", "WR", draft_round=None, year=1,
                             adp_round=2, from_rookie_draft=True)
    engine.allocate([p], owned)
    assert p.base_round == 5
    assert p.final_round == 3 and p.bumped


def test_a_traded_rookie_keeper_keeps_the_premium():
    """Otherwise a swap could be used to reprice him."""
    got = engine.convert_traded_rookie(from_rookie_draft=True)
    assert got["draft_round"] == 5 and got["year"] == 1


def test_a_traded_veteran_draft_rookie_uses_his_real_round():
    got = engine.convert_traded_rookie(11)
    assert got["draft_round"] == 11 and got["year"] == 1


def test_the_premium_is_a_named_constant_not_a_literal():
    assert engine.R5_ROOKIE_PREMIUM == 5
    assert engine.rookie_draft_premium() == config.keeper_rules()["rookie_draft_premium_round"]


# ------------------------------------------- dropping gains you nothing

@pytest.mark.parametrize("adp", [1, 3, 8, 12])
def test_cutting_and_reclaiming_lands_on_the_same_price(adp):
    """The reason the twelve-month lock-out was never needed. Year one already
    offers the cheaper of the draft round and the current ADP, so a drop-and-
    reclaim cannot beat simply keeping him - there is no price to launder."""
    kept = engine.price_regular("a", "x", "RB", draft_round=2, year=1, adp_round=adp)
    reclaimed = engine.price_regular("a", "x", "RB", draft_round=2, year=1, adp_round=adp)
    assert kept.final_round == reclaimed.final_round


def test_a_dropped_players_clock_does_not_reset():
    """He comes back where he left off, not as a fresh year one."""
    yr2 = engine.price_regular("a", "x", "RB", draft_round=2, year=2, adp_round=8)
    yr1 = engine.price_regular("a", "x", "RB", draft_round=2, year=1, adp_round=8)
    assert yr2.year == 2 and yr1.year == 1
    assert yr2.final_round == 8, "year two: 2 minus 3 floors at R1, so ADP is cheaper"


def test_only_a_never_drafted_player_reaches_the_last_round():
    """The one genuinely cheap route onto a roster."""
    undrafted = engine.price_regular("a", "x", "WR", draft_round=None, year=1, adp_round=3)
    assert undrafted.final_round == config.veteran_rounds()
    drafted = engine.price_regular("b", "y", "WR", draft_round=2, year=1, adp_round=3)
    assert drafted.final_round < config.veteran_rounds()
