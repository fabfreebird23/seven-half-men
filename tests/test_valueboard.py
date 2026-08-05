"""Pricing every roster, the waiver board, and the franchise tag.

None of this can be exercised by hand until the draft happens, so the fixtures
below stand in for real rosters and history.
"""
from __future__ import annotations

from collections import Counter

import pytest

from halfmen import config, engine, valueboard


class FakeHistory:
    """Just enough history for pricing: how a player arrived and how long he
    has been held."""
    def __init__(self, rookie_keepers=(), rookie_draft=(), years=None,
                 anchors=None, peaks=None):
        self._rk = set(rookie_keepers)
        self._rd = set(rookie_draft)
        self._years = years or {}
        self._anchors = anchors or {}
        self._peaks = peaks or {}

    def is_rookie_keeper_eligible(self, pid): return pid in self._rk
    def has_rookie_draft_provenance(self, pid): return pid in self._rd
    def keeper_year(self, pid): return self._years.get(pid, 0)
    def keeper_anchor(self, pid): return self._anchors.get(pid)
    def draft_round(self, pid): return self._anchors.get(pid)
    def peak_round(self, pid): return self._peaks.get(pid)


PMAP = {
    "1": {"full_name": "Jahmyr Gibbs", "position": "RB"},
    "2": {"full_name": "Jeremiah Smith", "position": "WR"},
    "3": {"full_name": "Ollie Gordon II", "position": "RB"},
}


def test_a_rookie_keeper_prices_at_the_last_round():
    hist = FakeHistory(rookie_keepers={"2"})
    p = valueboard.price_for("2", hist=hist, pmap=PMAP)
    assert p.kind == "rookie" and p.final_round == config.veteran_rounds()


def test_a_rookie_draft_player_prices_at_the_premium():
    hist = FakeHistory(rookie_draft={"3"})
    p = valueboard.price_for("3", hist=hist, pmap=PMAP)
    assert p.from_rookie_draft and p.final_round == engine.rookie_draft_premium()


def test_an_ordinary_keeper_prices_off_his_draft_round():
    hist = FakeHistory(anchors={"1": 9}, years={"1": 0})
    p = valueboard.price_for("1", hist=hist, pmap=PMAP)
    assert p.year == 1 and p.base_round == 9


def test_the_board_is_empty_before_anyone_is_rostered(monkeypatch):
    """The honest answer pre-draft, rather than a placeholder."""
    monkeypatch.setattr(valueboard, "_roster_players", lambda lid: {})
    assert valueboard.rows("x", 2026, hist=FakeHistory()) == []


def test_the_board_sorts_by_surplus(monkeypatch):
    monkeypatch.setattr(valueboard, "_roster_players", lambda lid: {"o": ["1", "2", "3"]})
    monkeypatch.setattr(valueboard.sleeper, "get_players", lambda: PMAP)
    monkeypatch.setattr(valueboard.draftboard, "owned_rounds",
                        lambda *a, **k: {"o": Counter({r: 1 for r in range(1, 14)})})
    monkeypatch.setattr(valueboard.adp_board, "adp_round_for_player", lambda m, s=None: 2)
    got = valueboard.rows("x", 2026, hist=FakeHistory(rookie_keepers={"2"},
                                                      anchors={"1": 9, "3": 4}))
    surpluses = [r["surplus"] for r in got]
    assert surpluses == sorted(surpluses, reverse=True)
    assert got[0]["name"] == "Jeremiah Smith", "the R13 rookie keeper is the best value"


def test_prices_account_for_the_bump(monkeypatch):
    """Two keepers cannot share a round, so a price is only true in the context
    of the rest of that manager's slip."""
    monkeypatch.setattr(valueboard, "_roster_players", lambda lid: {"o": ["1", "3"]})
    monkeypatch.setattr(valueboard.sleeper, "get_players", lambda: PMAP)
    monkeypatch.setattr(valueboard.draftboard, "owned_rounds",
                        lambda *a, **k: {"o": Counter({r: 1 for r in range(1, 14)})})
    monkeypatch.setattr(valueboard.adp_board, "adp_round_for_player", lambda m, s=None: 2)
    got = valueboard.rows("x", 2026, hist=FakeHistory(anchors={"1": 9, "3": 9}))
    assert sorted(r["cost"] for r in got) == [8, 9]
    assert any(r["bumped"] for r in got)


# ---------------------------------------------------------------- franchise

def test_the_tag_is_worth_most_on_a_late_find(monkeypatch):
    """Frozen at the most EXPENSIVE round ever paid, so a player whose market
    ran away from a cheap peak banks the most."""
    monkeypatch.setattr(valueboard, "_roster_players", lambda lid: {"o": ["1", "3"]})
    monkeypatch.setattr(valueboard.sleeper, "get_players", lambda: PMAP)
    monkeypatch.setattr(valueboard.adp_board, "adp_round_for_player",
                        lambda m, s=None: 1)
    hist = FakeHistory(years={"1": 3, "3": 3}, peaks={"1": 5, "3": 1})
    got = valueboard.franchise_candidates("o", "x", hist=hist)
    assert got[0]["name"] == "Jahmyr Gibbs", "peak R5 against an R1 market wins"
    assert got[0]["banked"] == 4 * int(config.franchise_rules()["extra_years"])
    assert got[-1]["banked"] == 0, "a career first-rounder banks nothing"


def test_players_short_of_the_wall_rank_below_those_at_it(monkeypatch):
    monkeypatch.setattr(valueboard, "_roster_players", lambda lid: {"o": ["1", "3"]})
    monkeypatch.setattr(valueboard.sleeper, "get_players", lambda: PMAP)
    monkeypatch.setattr(valueboard.adp_board, "adp_round_for_player", lambda m, s=None: 1)
    hist = FakeHistory(years={"1": 0, "3": 3}, peaks={"1": 9, "3": 4})
    got = valueboard.franchise_candidates("o", "x", hist=hist)
    assert got[0]["at_the_wall"] and not got[1]["at_the_wall"]


# ------------------------------------------- dropping does not launder a price

def _fa_setup(monkeypatch, hist, adp_rows):
    monkeypatch.setattr(valueboard, "_roster_players", lambda lid: {})
    monkeypatch.setattr(valueboard.sleeper, "get_players", lambda: PMAP)
    monkeypatch.setattr(valueboard, "table_items", lambda: adp_rows.items())
    monkeypatch.setattr(valueboard.adp_board, "rank_to_round", lambda r: 2)
    monkeypatch.setattr(valueboard.adp_board, "adp_round_for_player", lambda m, s=None: 2)
    return valueboard.free_agents("x", limit=10, hist=hist)


ADP = {
    "jahmyrgibbs": {"name": "Jahmyr Gibbs", "position": "RB", "rank": 1.0},
    "olliegordon": {"name": "Ollie Gordon II", "position": "RB", "rank": 2.0},
}


def test_a_dropped_player_carries_the_round_he_was_drafted_in(monkeypatch):
    """The whole point of the rule: cutting him cannot reset his price to a
    last-round pick."""
    hist = FakeHistory(anchors={"1": 2})          # Gibbs drafted in the 2nd
    got = {r["name"]: r for r in _fa_setup(monkeypatch, hist, ADP)}
    assert got["Jahmyr Gibbs"]["cost"] == 2
    assert got["Jahmyr Gibbs"]["carried"] is True


def test_a_player_never_drafted_here_is_the_only_cheap_one(monkeypatch):
    hist = FakeHistory(anchors={"1": 2})          # Gordon has no history
    got = {r["name"]: r for r in _fa_setup(monkeypatch, hist, ADP)}
    assert got["Ollie Gordon II"]["cost"] == config.veteran_rounds()
    assert got["Ollie Gordon II"]["carried"] is False


def test_the_board_no_longer_calls_a_cut_second_rounder_a_last_round_pickup(monkeypatch):
    """This is the bug the rule clarification exposed - it would have told the
    league a dropped 2nd was an R13."""
    hist = FakeHistory(anchors={"1": 2})
    got = {r["name"]: r for r in _fa_setup(monkeypatch, hist, ADP)}
    assert got["Jahmyr Gibbs"]["cost"] != config.veteran_rounds()
    assert got["Jahmyr Gibbs"]["surplus"] < got["Ollie Gordon II"]["surplus"]


def test_a_dropped_players_clock_keeps_running(monkeypatch):
    """He does not come back as a fresh year-one keeper either."""
    hist = FakeHistory(anchors={"1": 9}, years={"1": 1})
    got = {r["name"]: r for r in _fa_setup(monkeypatch, hist, ADP)}
    assert got["Jahmyr Gibbs"]["cost"] == 6, "year two is 9 minus 3, not year one at 9"


def test_there_is_no_re_add_lockout_in_config():
    """The rule is enforced by carrying the price, not by policing a
    transaction log nobody was going to read."""
    assert "cut_lockout_days" not in config.faab_rules()
    assert config.faab_rules()["price_survives_a_drop"] is True
