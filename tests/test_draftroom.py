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
    pw = next(i for i in at.text_input if i.key == "room_pw")
    pw.set_value(config.draw_password()).run()
    return at


def test_the_board_is_read_only_until_the_commissioner_signs_in():
    at = room()
    assert picker(at) is None, "no entry control while locked"
    assert any(i.key == "room_pw" for i in at.text_input)


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
    """The whole point of voice: say it and it is entered. The transcript is
    matched in Python, so that half is exercised here; the browser half only
    captures audio."""
    from halfmen import voice
    at = unlock(room())
    name = picker(at).options[0].split("  \u00b7")[0]
    pool = [{"id": "x", "name": name, "position": "RB", "team": "MIA"}]
    got = voice.match(name, pool)
    assert got and got["sure"] and got["player"]["name"] == name


def test_the_seats_label_by_pick_number_not_seat():
    """"2.08" is the eighth pick of round two, not seat eight. In a snake those
    are opposites, and mixing them is how a board gets read out wrong."""
    seats = picks.board_seats(["a", "b", "c", "d"], 2, snake=True)
    assert seats[4]["label"] == "2.01" and seats[4]["owner_id"] == "d"
    assert seats[7]["label"] == "2.04" and seats[7]["owner_id"] == "a"


VOICE_HTML = (Path(APP).parent / "halfmen" / "components" / "voice" / "index.html")


def test_voice_never_navigates_the_page():
    """Streamlit sandboxes component frames without allow-top-navigation, so
    `window.parent.location = ...` is silently dropped - recognition works, the
    transcript goes nowhere, and it looks exactly like a dead microphone. It
    also meant a full page load between picks. The value goes back over the
    websocket instead."""
    src = VOICE_HTML.read_text()
    assert "streamlit:setComponentValue" in src, "hand the value back, do not navigate"
    assert "location.href" not in src and "location =" not in src
    assert "streamlit:componentReady" in src, "the component has to announce itself"


def test_saying_the_same_name_twice_still_counts():
    """Streamlit swallows an unchanged component value, so a repeated transcript
    would silently do nothing the second time."""
    src = VOICE_HTML.read_text()
    assert "seq: ++seq" in src


def test_the_mic_reports_what_it_heard():
    """A silent failure is the worst outcome here - if it hears something and
    cannot deliver it, the button still has to show that it heard."""
    src = VOICE_HTML.read_text()
    assert "Mic blocked" in src and "Did not catch that" in src
    assert "Voice needs Chrome or Edge" in src


def test_holding_v_does_not_fire_while_somebody_is_typing_a_name():
    src = VOICE_HTML.read_text()
    assert "role') === 'combobox'" in src, "the player picker is a combobox, not an input"


def test_a_pick_never_uses_a_fragment_rerun_it_is_not_allowed_to():
    """`scope="fragment"` is only legal DURING a fragment rerun. On the first
    full run that renders the fragment it raises - so the very first pick of the
    night would have thrown instead of landing."""
    src = Path(APP).read_text()
    body = src[src.index("def room_controls"):src.index("def room_board")]
    assert 'st.rerun(scope="fragment")' not in body, "go through rerun_here()"
    assert body.count("rerun_here()") >= 3


def test_the_room_unlock_survives_a_full_page_load():
    """Voice hands its transcript back by navigating the page, and a new page is
    a new Streamlit session with an empty session_state. A session-only flag
    asked for the password after every single spoken pick."""
    at = unlock(room())
    key = {k: (v[0] if isinstance(v, list) else v)
           for k, v in dict(at.query_params).items()}.get("k")
    assert key, "unlocking has to leave something a reload can read"

    fresh = room(k=key)                       # brand new session, as after a navigation
    assert picker(fresh) is not None, "still unlocked"
    assert not any(i.key == "room_pw" for i in fresh.text_input)


def test_a_wrong_key_does_not_open_the_board():
    fresh = room(k="not-the-key")
    assert picker(fresh) is None


def test_the_room_key_does_not_unlock_the_lottery_draw():
    """Re-drawing the lottery is destructive, so that one stays session-only and
    does not travel in a pasted link."""
    at = unlock(room())
    key = {k: (v[0] if isinstance(v, list) else v)
           for k, v in dict(at.query_params).items()}["k"]
    lot = AppTest.from_file(APP, default_timeout=90)
    lot.query_params.update({"p": "preseason", "g": "lottery", "t": "drums", "k": key})
    lot.run()
    assert any(i.key == "draw_pw" for i in lot.text_input), "the draw still asks"


def test_no_html_entity_is_ever_passed_through_esc():
    """esc() on a string that already contains an entity escapes the ampersand,
    so "RB &middot;" renders as literal text under the player's name."""
    import re
    from pathlib import Path as P
    for f in list(P("halfmen").glob("*.py")) + [P("app.py")]:
        hits = re.findall(r"esc\([^()]*&[a-zA-Z]+;[^()]*\)", f.read_text())
        assert not hits, "%s escapes an entity: %s" % (f, hits[:2])


def test_a_recorded_pick_keeps_the_nfl_team():
    """The board shows "RB · MIA". Without the team it showed "RB ·" with a
    dangling separator and nothing after it."""
    got = picks.add(picks.VETERAN,
                    {"id": "1", "name": "De'Von Achane", "position": "RB", "team": "MIA"},
                    ["a", "b"], 1, snake=True, season=config.season())
    assert got["team"] == "MIA" and got["position"] == "RB"
    assert picks.load(picks.VETERAN, config.season())[0]["team"] == "MIA"


def test_a_pick_with_no_team_does_not_leave_a_dangling_separator():
    got = picks.add(picks.VETERAN, {"id": "2", "name": "Somebody", "position": "WR"},
                    ["a", "b"], 1, snake=True, season=config.season())
    assert got["team"] == ""
