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
