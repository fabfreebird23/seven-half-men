"""Draft board, taxi squeeze and the ADP round mapping."""
from __future__ import annotations

from collections import Counter

import pytest

from halfmen import adp_board, config, draftboard, taxi

OWNERS = ["a", "b", "c", "d", "e", "f", "g", "h"]


# ---------------------------------------------------------------- the board

def test_columns_stay_with_the_same_team_all_the_way_down(monkeypatch):
    monkeypatch.setattr(draftboard, "traded_away", lambda *a, **k: {})
    board = draftboard.grid(OWNERS, season=2026, keepers={})
    for row in board:
        assert [c.owner_id for c in row] == OWNERS


def test_snake_reverses_the_pick_numbers_not_the_columns(monkeypatch):
    monkeypatch.setattr(draftboard, "traded_away", lambda *a, **k: {})
    board = draftboard.grid(OWNERS, season=2026, keepers={})
    assert [c.pick_label for c in board[0]][:3] == ["1.01", "1.02", "1.03"]
    assert [c.pick_label for c in board[1]][:3] == ["2.08", "2.07", "2.06"]


def test_the_board_fills_the_active_roster_exactly(monkeypatch):
    """14 rounds, because the two rookie-draft picks go to taxi before the
    veteran draft and taxi does not count against the 14 active spots. The board
    starts empty and fills it exactly - no dangling spot, nobody one over."""
    from halfmen import config
    monkeypatch.setattr(draftboard, "traded_away", lambda *a, **k: {})
    rounds = len(draftboard.grid(OWNERS, season=2026, keepers={}))
    assert rounds == config.active_roster_size() == 14
    assert rounds == config.veteran_rounds(2026)


def test_keepers_land_on_the_board(monkeypatch):
    monkeypatch.setattr(draftboard, "traded_away", lambda *a, **k: {})
    keepers = {"a": [{"round": 5, "name": "Quinshon Judkins", "kind": "franchise"}]}
    board = draftboard.grid(OWNERS, season=2026, keepers=keepers)
    cell = board[4][0]
    assert cell.kind == "franchise" and cell.player == "Quinshon Judkins"


def test_traded_rounds_show_as_traded(monkeypatch):
    monkeypatch.setattr(draftboard, "traded_away", lambda *a, **k: {"b": [7]})
    board = draftboard.grid(OWNERS, season=2026, keepers={})
    assert board[6][1].kind == "traded"
    assert board[6][0].kind == "open"


def test_capital_counts_live_picks(monkeypatch):
    monkeypatch.setattr(draftboard, "owned_rounds",
                        lambda *a, **k: {o: Counter({r: 1 for r in range(1, 14)}) for o in OWNERS})
    caps = draftboard.capital(OWNERS, {"a": [{"round": 1}, {"round": 2}]}, 2026)
    a = next(c for c in caps if c["owner_id"] == "a")
    assert a["held"] == 13 and a["eaten"] == 2 and a["live"] == 11


# ---------------------------------------------- selection order -> slots

def test_selection_order_is_the_provisional_board():
    assert draftboard.order_from_selection(OWNERS) == OWNERS


def test_first_choice_can_take_any_slot():
    """Whoever wins the drum picks a spot; everyone else falls into what's left
    in selection order."""
    got = draftboard.order_from_selection(OWNERS, {"a": 8})
    assert got[7] == "a"
    assert got[:3] == ["b", "c", "d"]


# ---------------------------------------------------------------- taxi

def test_two_full_slots_and_two_incoming_picks_is_a_squeeze():
    bay = taxi.Bay(owner_id="a", pods=[
        taxi.Pod("1", "Jadyn Davis", "QB", 2029, 2),
        taxi.Pod("2", "Justice Haynes", "RB", 2029, 1),
    ], incoming_picks=2)
    assert bay.free == 0
    assert len(bay.expiring) == 1
    assert bay.squeeze == 1, "the expiring pod frees one slot, the other rookie has nowhere to go"


def test_an_empty_bay_absorbs_both_picks():
    bay = taxi.Bay(owner_id="a", pods=[], incoming_picks=2)
    assert bay.squeeze == 0


def test_both_pods_expiring_means_no_squeeze():
    bay = taxi.Bay(owner_id="a", pods=[
        taxi.Pod("1", "A", "QB", 2029, 2),
        taxi.Pod("2", "B", "RB", 2029, 2),
    ], incoming_picks=2)
    assert bay.squeeze == 0


def test_slot_count_comes_from_config():
    assert taxi.Bay("a", []).slots == int(config.taxi_rules()["slots"]) == 2


# ---------------------------------------------------------------- adp

def test_rank_maps_to_an_eight_team_round():
    assert adp_board.rank_to_round(1) == 1
    assert adp_board.rank_to_round(8) == 1
    assert adp_board.rank_to_round(9) == 2
    assert adp_board.rank_to_round(64) == 8


def test_undraftable_players_clamp_to_the_last_round():
    """Nobody is free to keep - a player past the board still costs a last pick."""
    assert adp_board.rank_to_round(9999) == config.veteran_rounds()


def test_the_board_loaded():
    assert adp_board.size() > 100
    assert adp_board.adp_round("Bijan Robinson") == 1


# ------------------------------------------- promotion keeps the designation

def test_promoting_off_taxi_keeps_the_rookie_keeper_designation():
    """A taxi stint is still holding him, so the chain the rookie-keeper rule
    cares about is unbroken — in year one or year two."""
    assert taxi.keeps_rookie_status(1) is True
    assert taxi.keeps_rookie_status(2) is True


def test_promotion_costs_a_rookie_slot_not_a_regular_one():
    assert taxi.promotion_cost(2) == "a rookie keeper slot"


def test_the_stricter_reading_is_one_config_flag(monkeypatch):
    """If the league later decides an early promotion should forfeit it."""
    rules = dict(config.taxi_rules())
    rules["promotion_keeps_rookie_status"] = "second_year_only"
    monkeypatch.setattr(config, "taxi_rules", lambda: rules)
    assert taxi.keeps_rookie_status(1) is False
    assert taxi.keeps_rookie_status(2) is True
    assert "three-year clock" in taxi.promotion_cost(1)


def test_a_full_farm_is_four_cheap_players():
    """Two on taxi costing nothing, plus two rookie keepers at the last rounds,
    with every regular slot still free."""
    bay = taxi.Bay("a", [taxi.Pod("1", "A", "WR", 2026, 1), taxi.Pod("2", "B", "RB", 2026, 1)])
    assert taxi.farm_size(bay, int(config.keeper_rules()["rookie"])) == 4


# --------------------------------------------------- taxi compliance policing

class _FakeHistory:
    """`eligible` is the taxi rule: any rookie you DRAFTED, off either board."""
    def __init__(self, eligible_ids):
        self._ok = set(eligible_ids)

    def is_rookie_keeper_eligible(self, pid):
        return str(pid) in self._ok

    def has_rookie_draft_provenance(self, pid):
        return str(pid) in self._ok


def test_compliance_passes_a_legal_bay():
    bays = {"a": taxi.Bay("a", [taxi.Pod("1", "Rookie Pick", "WR", 2026, 1)])}
    assert taxi.compliance(bays, _FakeHistory(["1"])) == {}


def test_compliance_allows_a_rookie_taken_in_the_veteran_draft():
    """A rookie taken in the 12th of the veteran draft is exactly as eligible
    as one taken 1.01 in the rookie draft - what qualifies him is that he is a
    rookie and you drafted him. This flagged him as illegal until 2026-08-31."""
    bays = {"a": taxi.Bay("a", [
        taxi.Pod("1", "Rookie Pick", "WR", 2026, 1),
        taxi.Pod("2", "Vet Draft Rookie", "RB", 2026, 1),
    ])}
    assert taxi.compliance(bays, _FakeHistory(["1", "2"])) == {}


def test_compliance_catches_a_player_who_was_never_drafted_by_you():
    """Sleeper gates taxi on NFL experience and nothing else, so it will let
    someone stash a rookie they picked up off waivers. This is the only thing
    standing between that rule and the honour system."""
    bays = {"a": taxi.Bay("a", [
        taxi.Pod("1", "Rookie Pick", "WR", 2026, 1),
        taxi.Pod("2", "Waiver Rookie", "RB", 2026, 1),
    ])}
    flagged = taxi.compliance(bays, _FakeHistory(["1"]))
    assert [p.player_id for p in flagged["a"]] == ["2"]


def test_compliance_only_reports_teams_with_a_problem():
    bays = {
        "a": taxi.Bay("a", [taxi.Pod("1", "Legal", "WR", 2026, 1)]),
        "b": taxi.Bay("b", [taxi.Pod("9", "Illegal", "TE", 2026, 1)]),
    }
    flagged = taxi.compliance(bays, _FakeHistory(["1"]))
    assert set(flagged) == {"b"}


# ---------------------------------------------------------------- rookie board

def test_the_rookie_board_is_two_rounds_of_eight():
    board = draftboard.rookie_grid(OWNERS)
    assert len(board) == config.rookie_rounds()
    assert all(len(r) == len(OWNERS) for r in board)
    assert draftboard.rookie_pick_count() == config.rookie_rounds() * len(config.managers())


def test_the_rookie_board_snakes_when_configured(monkeypatch):
    d = dict(config.drafts()); d["rookie_snake"] = True
    monkeypatch.setattr(config, "drafts", lambda: d)
    board = draftboard.rookie_grid(OWNERS)
    assert [c.pick_label for c in board[0]][:2] == ["1.01", "1.02"]
    assert [c.pick_label for c in board[1]][:2] == ["2.08", "2.07"]


def test_round_two_can_repeat_round_one_instead(monkeypatch):
    """The written rules never settled snake vs linear for the rookie draft."""
    d = dict(config.drafts()); d["rookie_snake"] = False
    monkeypatch.setattr(config, "drafts", lambda: d)
    board = draftboard.rookie_grid(OWNERS)
    assert [c.pick_label for c in board[1]][:2] == ["2.01", "2.02"]


def test_columns_stay_with_their_team_in_both_rounds():
    board = draftboard.rookie_grid(OWNERS)
    for row in board:
        assert [c.owner_id for c in row] == OWNERS


def test_no_keeper_ever_strikes_a_rookie_pick():
    """A keeper costs a VETERAN round, so nothing is burned off this board -
    the failure would be silently reusing grid() and eating picks."""
    board = draftboard.rookie_grid(OWNERS)
    assert all(c.kind == "open" for row in board for c in row)


def test_the_adp_refresh_entry_points_exist():
    """The daily job calls these by name. It silently failed every run against a
    missing config.current_season until somebody actually ran it."""
    assert config.current_season() == config.season()
    assert isinstance(config.adp_sources(), dict)


def test_year_one_parks_both_rookies_on_taxi_before_the_veteran_draft():
    """It is what makes 14 rounds the exact fit. Taxi does not count against the
    14 active spots, so the board starts empty - and doing it AFTER the draft
    would leave every team 16 deep on a 14-man roster mid-draft."""
    from halfmen import config
    assert config.auto_stash_rookies()
    rounds = config.veteran_rounds(2026)
    rookies = int(config.taxi_rules()["slots"])
    assert rounds == config.active_roster_size(), "the board fills the roster exactly"
    assert rookies == config.rookie_rounds(), "one taxi slot per rookie pick"
