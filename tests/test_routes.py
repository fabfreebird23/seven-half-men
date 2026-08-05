"""Every route in the bottom bar has to render something.

There are sixteen leaves behind two popovers now, and most of them are dark in
year one - an empty roster, no transactions, no keepers. A route that raises or
renders nothing would be invisible until the season started, so this walks all
of them with Streamlit's own harness.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")
SRC = Path(APP).read_text()


def _groups():
    ns = {}
    exec(re.search(r"GROUPS = \{.*?\n\}\n", SRC, re.S).group(0), ns)
    return ns["GROUPS"]


def routes():
    yield {"p": "home"}
    yield {"p": "rules"}
    for section, groups in _groups().items():
        for gk, _glabel, leaves in groups:
            for lk, _llabel in leaves:
                yield {"p": section, "g": gk, "t": lk}


ALL = list(routes())


def test_there_are_sixteen_leaves_plus_two_flat_pages():
    assert len(ALL) == 18


@pytest.mark.parametrize("qp", ALL, ids=lambda q: "/".join(q.values()))
def test_route_renders_without_raising(qp):
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params.update(qp)
    at.run()
    assert not at.exception, "%s raised: %s" % (qp, [e.value for e in at.exception])


@pytest.mark.parametrize("qp", ALL, ids=lambda q: "/".join(q.values()))
def test_route_renders_actual_content(qp):
    """Not just 'no crash' - a leaf that silently renders nothing is the failure
    mode this refactor could plausibly introduce."""
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params.update(qp)
    at.run()
    body = "".join(m.value for m in at.markdown)
    assert len(body) > 400, "%s rendered %d chars" % (qp, len(body))


# ---------------------------------------------------------------- the draw

def test_the_draw_survives_the_session_that_ran_it(tmp_path, monkeypatch):
    """It lived in st.session_state, which is per-browser-session: the
    commissioner would have seen the order and everyone else 'nothing drawn
    yet', and a refresh would have wiped it."""
    from halfmen import config, storage
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage.config, "DATA_DIR", tmp_path)

    assert storage.load_draw(2026) == {}
    storage.save_draw(42, ["a", "b"], ["b", "a"], 2026)
    got = storage.load_draw(2026)
    assert got["rookie"] == ["a", "b"] and got["veteran"] == ["b", "a"]
    assert got["seed"] == 42 and got["drawn_at"]


def test_the_draw_is_reproducible_from_its_seed():
    """The seed is the whole reason this can be run in front of people: any of
    them can re-enter it and get the same order back."""
    from halfmen import lottery
    owners = ["a", "b", "c", "d", "e", "f", "g", "h"]
    first = lottery.first_season_order(owners, seed=42)
    assert lottery.first_season_order(owners, seed=42) == first
    assert lottery.first_season_order(owners, seed=43) != first


def test_the_two_drafts_get_different_orders_from_one_seed():
    """Same seed for both would give the same order twice, which nobody would
    accept as a draw."""
    from halfmen import lottery
    owners = ["a", "b", "c", "d", "e", "f", "g", "h"]
    assert (lottery.first_season_order(owners, seed=7)
            != lottery.first_season_order(owners, seed=8))


def test_saving_a_draw_leaves_submitted_keepers_alone(tmp_path, monkeypatch):
    from halfmen import config, storage
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage.config, "DATA_DIR", tmp_path)
    storage.submit("owner1", [{"player_id": "1", "kind": "keeper", "round": 3}], 2026)
    storage.save_draw(5, ["a"], ["a"], 2026)
    assert storage.entries_for("owner1", 2026), "the draw must not clobber the ledger"
    assert storage.load_draw(2026)["seed"] == 5
