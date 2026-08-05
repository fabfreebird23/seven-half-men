"""The Home card has to be right in every state the season passes through.

It is the screen someone opens from a phone in week 6, so the failure that
matters is not a crash - it is the card confidently printing zeros that read as
facts. Each test here pins one state: nothing played, order drawn, mid-season.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from halfmen import config, sleeper, storage

APP = str(Path(__file__).resolve().parent.parent / "app.py")
ME = config.me()


@pytest.fixture(autouse=True)
def clean_caches(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def home(**_):
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params.update({"p": "home"})
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return " ".join(m.value for m in at.markdown)


def roster(**settings):
    base = {"wins": 0, "losses": 0, "ties": 0}
    base.update(settings)
    return [{"owner_id": ME, "players": [], "settings": base}]


def test_before_anything_happens_it_says_so_instead_of_printing_zeros(monkeypatch):
    monkeypatch.setattr(sleeper, "get_rosters", lambda lid: roster())
    body = home()
    assert "nothing played, and no draw yet" in body
    assert "$100" in body and "all of it still comes due in the pot" in body


def test_once_the_order_is_drawn_the_record_tile_becomes_your_slot(monkeypatch):
    monkeypatch.setattr(sleeper, "get_rosters", lambda lid: roster())
    ids = list(config.managers().keys())
    rookie = [ids[3]] + [i for i in ids if i != ids[3]]
    veteran = [i for i in ids if i != ME] + [ME]      # last of eight
    storage.save_draw(11, rookie, veteran, config.season())
    body = home()
    assert "Your slot" in body
    assert "8th veteran" in body


def test_midseason_shows_the_record_and_what_is_left_of_the_budget(monkeypatch):
    monkeypatch.setattr(sleeper, "get_rosters",
                        lambda lid: roster(wins=6, losses=3, waiver_budget_used=71))
    body = home()
    assert "6-3" in body
    assert "$29" in body
    assert "still owed to the pot" in body


def test_spending_out_is_reported_as_owing_nothing_not_as_zero_left(monkeypatch):
    """$0 left is the good outcome in this league - the pot is funded by what you
    DIDN'T spend - and the card has to say which way round that is."""
    monkeypatch.setattr(sleeper, "get_rosters",
                        lambda lid: roster(wins=1, losses=8, waiver_budget_used=100))
    body = home()
    assert "you owe the pot nothing" in body


def test_a_submitted_slip_is_counted(monkeypatch):
    monkeypatch.setattr(sleeper, "get_rosters", lambda lid: roster())
    storage.submit(ME, [{"player_id": "1", "kind": "regular", "round": 4},
                        {"player_id": "2", "kind": "rookie", "round": 13}],
                   config.season())
    body = home()
    assert "of %d on your slip" % config.keeper_rules()["total"] in body
    assert ">2<" in body.replace(" ", ""), "the count itself is on the tile"


def test_it_names_the_best_and_worst_contract_on_your_roster(monkeypatch):
    """The two facts a manager actually wants off this screen: which hold is
    printing money and which one is about to cost them a real pick."""
    from halfmen import valueboard
    monkeypatch.setattr(sleeper, "get_rosters",
                        lambda lid: roster(wins=6, losses=3, waiver_budget_used=40))
    monkeypatch.setattr(valueboard, "rows", lambda *a, **k: [
        {"owner_id": ME, "player_id": "1", "name": "Bargain Bill", "position": "RB",
         "kind": "regular", "year": 1, "cost": 11, "adp": 3, "surplus": 8,
         "eligible": True, "reason": ""},
        {"owner_id": ME, "player_id": "2", "name": "Albatross Andy", "position": "WR",
         "kind": "regular", "year": 2, "cost": 2, "adp": 9, "surplus": -7,
         "eligible": True, "reason": ""},
        {"owner_id": "someone-else", "player_id": "3", "name": "Not Yours",
         "position": "TE", "kind": "regular", "year": 1, "cost": 5, "adp": 5,
         "surplus": 0, "eligible": True, "reason": ""},
    ])
    body = home()
    assert "Bargain Bill" in body and "best value" in body
    assert "Albatross Andy" in body and "worst value" in body
    assert "Not Yours" not in body, "another manager's contract is not your business here"


def test_an_ineligible_player_is_not_offered_as_your_best_value(monkeypatch):
    """A player at the three-year wall has a surplus number, but it is not a
    contract you can take - offering it as your best value would be a lie."""
    from halfmen import valueboard
    monkeypatch.setattr(sleeper, "get_rosters", lambda lid: roster(wins=6, losses=3))
    monkeypatch.setattr(valueboard, "rows", lambda *a, **k: [
        {"owner_id": ME, "player_id": "1", "name": "At The Wall", "position": "RB",
         "kind": "regular", "year": 3, "cost": 1, "adp": 12, "surplus": 11,
         "eligible": False, "reason": "held three years"},
    ])
    body = home()
    assert "At The Wall" not in body
    assert "No priced keepers yet" in body
