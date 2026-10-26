"""The weekly cover: every layout renders, and a sliced photo is pinned."""
from __future__ import annotations

import pytest

from halfmen import cover


def _img(hard=None):
    def img(owner, look):
        return "data:image/webp;base64,AAAA", {"hard": dict(hard or {})}
    return img


BASE = dict(week=7, month="OCT 2026", lines=["A", "B", "C"])
STORIES = [
    dict(BASE, kind="biggest", owner="1", first="Devin", pts="149.9", star="CMC.", star_pts="29.7", buried="THAD'S BENCH"),
    dict(BASE, kind="chase", owner="1", first="Lucas", rec="2–10", team="Maybe Later", cap=120),
    dict(BASE, kind="mover", owner="1", first="Clayton", rec="10–2", moved_word="Seven"),
    dict(BASE, kind="gotw", a="1", b="2", team_a="Taco Bandit", team_b="Bijan", stakes=36, photos=["x", "y"]),
    dict(BASE, kind="bench", owner="1", first="Thad", pts=31.2),
    dict(BASE, kind="lucky", owner="1", first="Brandon", pts="125.0", beaten=3, team="Clayton's Kids"),
]


@pytest.mark.parametrize("story", STORIES, ids=lambda s: s["kind"])
def test_every_layout_renders(story):
    out = cover.render(story, _img())
    assert out.startswith('<div class="kx wc"') and 'class="cut"' in out and "7½ MEN" in out or "7½ Men" in out


def test_an_unknown_story_renders_nothing():
    assert cover.render(dict(BASE, kind="nope"), _img()) == ""


def test_a_whole_cut_out_is_centred():
    out = cover.render(STORIES[0], _img())
    assert "translateX(-50%)" in out.split('class="cut"')[1].split(">")[0]


def test_a_photo_sliced_on_the_right_is_pinned_flush_right():
    tag = cover.render(STORIES[0], _img({"right": 0.6})).split('class="cut"')[1].split(">")[0]
    assert "right:0" in tag and "translateX" not in tag


def test_a_shallow_slice_is_left_to_its_fade_and_not_pinned():
    tag = cover.render(STORIES[0], _img({"right": 0.1})).split('class="cut"')[1].split(">")[0]
    assert "right:0" not in tag


def test_the_bench_numerals_move_off_a_manager_pinned_right():
    out = cover.render(STORIES[4], _img({"right": 0.6}))
    assert 'class="stack" style="left:5%' in out


def test_cover_text_is_escaped():
    s = dict(STORIES[1], team="<script>x</script>")
    assert "<script>x" not in cover.render(s, _img())
