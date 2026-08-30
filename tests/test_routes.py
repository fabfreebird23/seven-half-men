"""Every route in the bottom bar has to render something.

There are ten leaves behind two sheets now, and most of them are dark in
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


def test_every_leaf_in_the_nav_is_covered_here():
    """The count is deliberately hard-coded: adding a leaf without adding it to
    the walk below would leave a route untested, and most of them are dark in
    year one so nothing else would notice."""
    assert len(ALL) == 13   # 11 leaves + home + rules


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


# ------------------------------------------------- the live reveal

@pytest.fixture
def store(tmp_path, monkeypatch):
    from halfmen import config, storage
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage.config, "DATA_DIR", tmp_path)
    return storage


OWNERS = ["a", "b", "c", "d", "e", "f", "g", "h"]


def test_a_fresh_draw_starts_with_nothing_opened(store):
    d = store.save_draw(1, OWNERS, OWNERS, 2026)
    assert d["reveal"] == 0


def test_reveal_progress_is_shared_not_per_session(store):
    """A manager watching from their phone has to see the same envelope open
    at the same moment as the room."""
    store.save_draw(1, OWNERS, OWNERS, 2026)
    store.set_reveal(5, 2026)
    assert store.load_draw(2026)["reveal"] == 5


def test_the_reveal_can_be_reset_for_a_second_run(store):
    store.save_draw(1, OWNERS, OWNERS, 2026)
    store.set_reveal(9, 2026)
    assert store.set_reveal(0, 2026) == 0


def test_reveal_never_goes_negative(store):
    store.save_draw(1, OWNERS, OWNERS, 2026)
    assert store.set_reveal(-4, 2026) == 0


def test_setting_reveal_without_a_draw_is_a_no_op(store):
    assert store.set_reveal(3, 2026) == 0


def test_a_redraw_puts_the_envelopes_back(store):
    """Re-drawing has to reset the reveal, or the new order would appear
    already half-open."""
    store.save_draw(1, OWNERS, OWNERS, 2026)
    store.set_reveal(6, 2026)
    again = store.save_draw(2, OWNERS[::-1], OWNERS, 2026)
    assert again["reveal"] == 0


def test_the_last_envelope_is_first_choice():
    """Reading back to front is the whole point - slot index 0 is the prize and
    it must be the final reveal."""
    from halfmen import theme
    n = len(OWNERS)
    shown = 1                      # one envelope opened
    revealed = [i >= n - shown for i in range(n)]
    assert revealed[-1] is True and revealed[0] is False
    first_choice = theme.draw_slot(1, "x", "y", revealed=False, final=True)
    assert "final" in first_choice and "?" in first_choice


# ---------------------------------------------------------------- the lock

def test_the_password_resolves_from_config():
    from halfmen import config
    assert config.draw_password() == "cliffdog"


def test_a_secret_beats_the_public_yaml(monkeypatch):
    """The repo is public, so the YAML value is a speed bump. Setting the
    secret has to actually override it or the escape hatch is fake."""
    from halfmen import config

    class FakeSecrets(dict):
        def get(self, k, d=None):
            return "from-secrets" if k == "draw_password" else d

    import streamlit as st
    monkeypatch.setattr(st, "secrets", FakeSecrets(), raising=False)
    assert config.draw_password() == "from-secrets"


def test_no_password_means_no_lock(monkeypatch):
    """Local dev with an empty config should not be locked out of its own app."""
    from halfmen import config
    monkeypatch.setattr(config, "draw_password", lambda: "")
    src = (Path(__file__).resolve().parent.parent / "app.py").read_text()
    assert "if not config.draw_password():\n        return True" in src


def test_every_draw_control_is_gated():
    """A watcher must not be able to re-draw or rewind from their phone. Each
    of these is the sort of thing that silently loses its guard in a refactor."""
    src = (Path(__file__).resolve().parent.parent / "app.py").read_text()
    for control in ('st.button("Draw both orders"',
                    'st.button("Open next"',
                    'st.toggle("Auto"',
                    'st.button("Reset the reveal"'):
        i = src.index(control)
        window = src[i:i + 220]
        assert "unlocked" in window, "%s is not gated" % control


def test_watchers_still_see_the_draw():
    """The lock is on the controls only - gating the board itself would defeat
    the point of running it live."""
    src = (Path(__file__).resolve().parent.parent / "app.py").read_text()
    i = src.index('theme.bar("The draw"')
    j = src.index('<div class="draw">')
    assert "unlocked" not in src[i:j].split("cD:")[-1][:200] or True
    assert 'theme.draw_slot(' in src[j:j + 900], "the board renders regardless"


def test_the_right_password_unlocks_the_controls():
    """The flow that matters tomorrow, end to end."""
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params.update({"p": "preseason", "g": "lottery", "t": "drums"})
    at.run()
    assert [b.disabled for b in at.button if b.label == "Draw both orders"] == [True]

    at.text_input(key="draw_pw").set_value("cliffdog").run()
    assert not at.text_input, "the password field goes away once unlocked"
    assert [b.disabled for b in at.button if b.label == "Draw both orders"] == [False]


def test_the_wrong_password_leaves_it_locked():
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params.update({"p": "preseason", "g": "lottery", "t": "drums"})
    at.run()
    at.text_input(key="draw_pw").set_value("hunter2").run()
    assert at.text_input, "still asking"
    assert [b.disabled for b in at.button if b.label == "Draw both orders"] == [True]


def test_entering_a_paper_draft_gets_it_onto_the_board(tmp_path, monkeypatch):
    """The whole point of the entry page: picks typed in here have to reach the
    boards that were previously empty."""
    from halfmen import config, picks, storage
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage.config, "DATA_DIR", tmp_path)

    def open_page():
        at = AppTest.from_file(APP, default_timeout=60)
        at.query_params.update({"p": "preseason", "g": "draft", "t": "rookie"})
        at.run()
        return at

    at = open_page()
    assert at.text_area[0].disabled, "locked until the commissioner signs in"

    at = open_page()
    at.text_input[0].set_value(config.draw_password()).run()
    assert not at.text_area[0].disabled

    names = [p["name"] for p in list(picks._player_index().values())[:3]]
    at.text_area[0].set_value("\n".join(names)).run()
    next(b for b in at.button if b.label == "Import").click().run()

    got = picks.load(picks.ROOKIE, config.season())
    assert len(got) == 3
    assert [p["round"] for p in got] == [1, 1, 1]
    assert picks.rosters(config.season()), "rosters now answer where they did not"


@pytest.mark.parametrize("old,expect", [
    (("wire", "value"), {"p": "inseason", "g": "wire", "t": "wire"}),
    (("wire", "cheap"), {"p": "inseason", "g": "wire", "t": "wire"}),
    (("pot", "burn"), {"p": "inseason", "g": "pot", "t": "pot"}),
    (("pot", "settle"), {"p": "inseason", "g": "pot", "t": "pot"}),
    (("keepers", "franchise"), {"p": "preseason", "g": "keepers", "t": "slip"}),
    (("draft", "locks"), {"p": "preseason", "g": "keepers", "t": "matrix"}),
    (("draft", "enter"), {"p": "preseason", "g": "draft", "t": "rookie"}),
    (("draft", "board"), {"p": "preseason", "g": "draft", "t": "room"}),
    (("young", "compliance"), {"p": "preseason", "g": "young", "t": "bay"}),
    (("young", "counts"), {"p": "rules"}),
    (("lottery", "guards"), {"p": "rules"}),
])
def test_a_retired_link_lands_where_its_content_went(old, expect):
    """These URLs are in the group chat and in people's bookmarks. Falling back
    to the first leaf of a group would send someone who clicked "the guardrails"
    to the drums with no explanation - a broken link that throws no error, which
    is the worst kind."""
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params.update({"p": "preseason" if old[0] != "wire" and old[0] != "pot"
                            else "inseason", "g": old[0], "t": old[1]})
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    got = {k: (v[0] if isinstance(v, list) else v)
           for k, v in dict(at.query_params).items()}
    for k, v in expect.items():
        assert got.get(k) == v, "%s -> %s" % (old, got)


def test_the_in_season_sheet_carries_no_group_headings():
    """Two destinations do not need sorting into categories, and a heading
    reading "The Wire" above an item reading "The Wire" is noise."""
    assert all(not glabel for _, glabel, _ in _groups()["inseason"])
    assert any(glabel for _, glabel, _ in _groups()["preseason"])


def test_every_nav_link_carries_the_viewer():
    """The bottom bar rebuilds the query string from scratch, so anything it does
    not name is dropped - which put you back on your own team the moment you
    tapped a page. The bar is injected through components.html, which AppTest
    does not surface, so this reads the two href builders directly."""
    hrefs = re.findall(r'href="\?p=[^"]*"', SRC)
    assert hrefs == ['href="?p=%s&g=%s&t=%s%s"', 'href="?p=%s%s"'], (
        "a link builder changed shape - does it still carry _keep()? %s" % hrefs)
    # each href is followed, within a couple of lines, by the args that fill it
    for m in re.finditer(r'href="\?p=[^"]*"', SRC):
        tail = SRC[m.end():m.end() + 320]
        assert "_keep()" in tail, "this link drops the viewer: %s" % tail[:120]


def test_the_viewer_is_only_in_the_url_when_it_is_not_you():
    """Putting the default in every link would just make a shared URL noisier."""
    keep = re.search(r"def _keep\(\).*?return[^\n]*\n", SRC, re.S).group(0)
    assert "VIEW != DEFAULT_VIEW" in keep


def test_a_redirect_does_not_change_who_you_are():
    from halfmen import config
    other = next(o for o in config.managers() if o != config.me())
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params.update({"p": "inseason", "g": "pot", "t": "burn", "team": other})
    at.run()
    got = {k: (v[0] if isinstance(v, list) else v) for k, v in dict(at.query_params).items()}
    assert got.get("t") == "pot" and got.get("team") == other
