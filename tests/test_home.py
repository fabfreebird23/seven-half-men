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


def test_before_a_game_is_played_the_band_carries_the_two_settled_numbers(monkeypatch):
    """A lone em-dash in an empty band reads as broken, so there is always an
    honest pair. Once the draft is done the two settled things going into week
    one are what you can spend and what you are holding."""
    monkeypatch.setattr(sleeper, "get_rosters", lambda lid: roster())
    body = home()
    assert "FAAB" in body and "$100" in body
    assert "Rostered" in body
    assert "Week 1" in body


def test_the_draft_slots_are_gone_from_the_band_once_the_boards_are_full(monkeypatch):
    """These were your rookie-draft and veteran-draft selection slots. They
    stopped meaning anything the moment both boards filled, and a drawn slot
    sitting on the in-season front page is just clutter from a finished
    event."""
    monkeypatch.setattr(sleeper, "get_rosters", lambda lid: roster())
    ids = list(config.managers().keys())
    rookie = [ids[3]] + [i for i in ids if i != ids[3]]
    veteran = [i for i in ids if i != ME] + [ME]
    storage.save_draw(11, rookie, veteran, config.season())
    body = home()
    assert "Rookie slot" not in body
    assert "Veteran slot" not in body
    assert "Teams in the drum" not in body


def test_midseason_shows_the_record_and_what_is_left_of_the_budget(monkeypatch):
    monkeypatch.setattr(sleeper, "get_rosters",
                        lambda lid: roster(wins=6, losses=3, waiver_budget_used=71))
    body = home()
    assert "6\u20133" in body
    assert "Standing" in body and "1st" in body, "one roster, so it is top of the table"
    assert "$29" in body
    assert "owed to the pot at year end" in body
    # Derived, not hardcoded: the regular season is 13 weeks now (Sleeper runs
    # the playoffs from week 14 at two weeks a round), and a test that pinned
    # the number would have to be edited every time the schedule moves.
    left = config.regular_season_weeks() - 9
    assert "Week 9" in body and "%d to play" % left in body


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
    assert "on your slip" in body
    assert "2<small>/%d</small>" % config.keeper_rules()["total"] in body


def test_it_names_the_best_and_worst_contract_on_your_roster(monkeypatch):
    """The two facts a manager actually wants off this screen: which hold is
    printing money and which one is about to cost them a real pick."""
    from halfmen import valueboard
    monkeypatch.setattr(sleeper, "get_rosters",
                        lambda lid: roster(wins=6, losses=3, waiver_budget_used=40))
    monkeypatch.setattr(valueboard, "rows", lambda *a, **k: [
        {"owner_id": ME, "player_id": "1", "name": "Bargain Bill", "position": "RB",
         "kind": "regular", "year": 1, "cost": 11, "adp": 3, "surplus": 8,
         "eligible": True, "reason": "", "drafted_round": 3},
        {"owner_id": ME, "player_id": "2", "name": "Albatross Andy", "position": "WR",
         "kind": "regular", "year": 2, "cost": 2, "adp": 9, "surplus": -7,
         "eligible": True, "reason": "", "drafted_round": 9},
        {"owner_id": "someone-else", "player_id": "3", "name": "Not Yours",
         "position": "TE", "kind": "regular", "year": 1, "cost": 5, "adp": 5,
         "drafted_round": 5,
         "surplus": 0, "eligible": True, "reason": ""},
    ])
    body = home()
    # Measured against the round this league drafted him in, not against ADP -
    # the only ADP the app has is the preseason board everyone drafted off, so
    # in-season it reads ~0 for nearly everyone and picked a winner at random.
    assert "Bargain Bill" in body and "best contract" in body
    assert "+8" in body, "drafted R3, keeps at R11 - eight rounds gained"
    assert "Albatross Andy" in body and "worst contract" in body
    assert "-7" in body or "\u22127" in body, "drafted R9, keeps at R2"
    # Another manager's contract is not part of YOUR card. It can legitimately
    # appear further down the page, in the league-wide best-contracts block,
    # which is labelled as such so the two cannot be confused.
    mine = body.split("Best contracts in the league")[0]
    assert "Not Yours" not in mine, "your card is about your roster"


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
    assert "Contracts appear here once the draft has been held" in body


def test_an_expiring_taxi_pod_does_not_look_like_a_healthy_one(monkeypatch):
    """"2 of 2" and "2 of 2 with a decision due" must not render identically -
    the second one is the whole reason to look at the card in August."""
    from halfmen import taxi
    monkeypatch.setattr(sleeper, "get_rosters", lambda lid: roster(wins=6, losses=3))
    pods = [taxi.Pod(player_id="1", name="A", position="RB", drafted_season=2026, year=2),
            taxi.Pod(player_id="2", name="B", position="WR", drafted_season=2027, year=1)]
    monkeypatch.setattr(taxi, "build", lambda *a, **k: {
        ME: taxi.Bay(owner_id=ME, pods=pods, incoming_picks=2)})
    body = home()
    assert "1 pod expiring" in body
    assert "var(--warn)" in body, "the expiring pod is coloured apart from the live one"
    assert "incoming rookie" in body, "and the squeeze is called out"


def test_no_squeeze_means_no_warning(monkeypatch):
    from halfmen import taxi
    monkeypatch.setattr(sleeper, "get_rosters", lambda lid: roster(wins=6, losses=3))
    monkeypatch.setattr(taxi, "build", lambda *a, **k: {
        ME: taxi.Bay(owner_id=ME, pods=[], incoming_picks=2)})
    body = home()
    assert "nowhere to go" not in body
    assert "bay is empty" in body


def test_the_record_says_whether_you_are_in_the_bracket(monkeypatch):
    """"6-3" on its own is a number. Whether it puts you in the top four is the
    thing the number is for."""
    monkeypatch.setattr(sleeper, "get_rosters", lambda lid: [
        {"owner_id": ME, "players": [],
         "settings": {"wins": 2, "losses": 7, "ties": 0, "fpts": 900}},
    ] + [{"owner_id": "o%d" % i, "players": [],
          "settings": {"wins": 8 - i, "losses": 1 + i, "ties": 0, "fpts": 1200 - i}}
         for i in range(7)])
    body = home()
    assert "outside the top %d" % config.league()["playoff_teams"] in body


def test_a_contender_is_told_so(monkeypatch):
    monkeypatch.setattr(sleeper, "get_rosters", lambda lid: [
        {"owner_id": ME, "players": [],
         "settings": {"wins": 8, "losses": 1, "ties": 0, "fpts": 1400}},
    ] + [{"owner_id": "o%d" % i, "players": [],
          "settings": {"wins": 3, "losses": 6, "ties": 0, "fpts": 900 - i}}
         for i in range(7)])
    body = home()
    assert "in the playoff bracket" in body


def test_last_place_is_not_lit_up_like_a_prize(monkeypatch):
    monkeypatch.setattr(sleeper, "get_rosters", lambda lid: [
        {"owner_id": ME, "players": [],
         "settings": {"wins": 0, "losses": 9, "ties": 0, "fpts": 700}},
    ] + [{"owner_id": "o%d" % i, "players": [],
          "settings": {"wins": 6, "losses": 3, "ties": 0, "fpts": 1200 - i}}
         for i in range(7)])
    body = home()
    assert '<div class="st off">8th of 8</div>' in body
    assert 'class="head quiet"' in body
