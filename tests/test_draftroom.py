"""The room: say or type a name, it lands on the board.

This app is the record for the veteran draft, so the thing that must not break
is that a pick actually persists - the value board and every keeper price read
from the same file.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from halfmen import config, picks, storage

APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def room(**qp):
    at = AppTest.from_file(APP, default_timeout=90)
    at.query_params.update(dict({"p": "preseason", "g": "draft", "t": "room"}, **qp))
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def picker(at):
    """The player picker, not the "viewing as" one at the top of every page."""
    return next((s for s in at.selectbox if str(s.key or "").startswith("room_search")), None)


def unlock(at):
    pw = next(i for i in at.text_input if i.key == "draw_pw")
    pw.set_value(config.draw_password()).run()
    return at


def test_the_board_is_read_only_until_the_commissioner_signs_in():
    at = room()
    assert picker(at) is None, "no entry control while locked"
    assert any("password to run the board" in (i.placeholder or "") for i in at.text_input)


def test_a_pick_typed_in_lands_on_the_board_and_persists():
    at = unlock(room())
    assert picker(at) is not None, "the picker appears once unlocked"
    picker(at).set_value(picker(at).options[0]).run()
    next(b for b in at.button if "Lock it in" in b.label).click().run()

    made = picks.load(picks.VETERAN, config.season())
    assert len(made) == 1
    assert made[0]["round"] == 1 and made[0]["pick"] == 1
    assert made[0]["name"]


def test_undo_takes_the_last_one_back():
    at = unlock(room())
    picker(at).set_value(picker(at).options[0]).run()
    next(b for b in at.button if "Lock it in" in b.label).click().run()
    assert len(picks.load(picks.VETERAN, config.season())) == 1
    next(b for b in at.button if "Undo" in b.label).click().run()
    assert picks.load(picks.VETERAN, config.season()) == []


def test_a_drafted_player_cannot_be_taken_twice():
    at = unlock(room())
    first = picker(at).options[0]
    picker(at).set_value(first).run()
    next(b for b in at.button if "Lock it in" in b.label).click().run()
    at2 = unlock(room())
    assert first not in picker(at2).options


def test_speech_that_is_certain_drafts_without_asking():
    """The whole point of voice: say it and it is entered. The transcript comes
    back through the URL and Python does the matching, so the part that can get
    a pick wrong is the part that is unit-tested."""
    at = unlock(room())
    name = picker(at).options[0].split("  \u00b7")[0]
    at.query_params["say"] = name
    at.run()
    made = picks.load(picks.VETERAN, config.season())
    assert len(made) == 1 and made[0]["name"] == name


def test_the_seats_label_by_pick_number_not_seat():
    """"2.08" is the eighth pick of round two, not seat eight. In a snake those
    are opposites, and mixing them is how a board gets read out wrong."""
    seats = picks.board_seats(["a", "b", "c", "d"], 2, snake=True)
    assert seats[4]["label"] == "2.01" and seats[4]["owner_id"] == "d"
    assert seats[7]["label"] == "2.04" and seats[7]["owner_id"] == "a"
