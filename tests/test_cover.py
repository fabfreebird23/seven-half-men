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


MORE = [
    dict(BASE, kind="hitlist", owners=["1", "2"], rows=[["Clayton", "10–2", False], ["Lucas", "2–10", True]]),
    dict(BASE, kind="issue", owner="1", first="Corey", lines=["A", "B", "C", "D", "E"]),
    dict(BASE, kind="fights", owners=[str(i) for i in range(8)], pairs=[["DEVIN", "JOSH"], ["COREY", "ISIAH"]], count_word="TWO"),
    dict(BASE, kind="streak", owner="1", first="Clayton", n=5, rec="10–2", pf="925"),
    dict(BASE, kind="rip", owner="1", first="Lucas", through=12),
    dict(BASE, kind="field", through=14, rows=[[str(i), "M%d" % i, i + 1] for i in range(8)]),
    dict(BASE, kind="champion", owner="1", first="Josh", team="Bijan with the Wind", year=2026),
    dict(BASE, kind="blowout", owner="1", first="Isiah", loser="Thad", margin="61", pts_w="162.4", pts_l="101.0"),
    dict(BASE, kind="clinch", owner="1", first="Brandon"),
]


@pytest.mark.parametrize("story", MORE, ids=lambda s: s["kind"])
def test_every_new_layout_renders_with_a_photo(story):
    out = cover.render(story, _img())
    assert out.startswith('<div class="kx wc"') and "<img" in out and "7½ MEN" in out


def test_the_hit_list_crosses_out_only_the_dead():
    out = cover.render(MORE[0], _img())
    assert "<s>Lucas 2–10</s>" in out and "<s>Clayton" not in out


def test_the_field_puts_its_title_in_the_middle_of_the_grid():
    out = cover.render(MORE[5], _img())
    cells = out.split('<div class="grid9">')[1].split('<svg class="wc-mast"')[0]
    assert cells.count("<i>") == 8 and cells.index('class="mid"') > cells.index("4 · M3")


def test_two_covers_on_one_page_never_share_an_svg_id():
    a = cover.render(dict(MORE[3], week=8), _img())
    b = cover.render(dict(MORE[6], week=9), _img())
    import re
    ids = lambda h: set(re.findall(r'id="([^"]+)"', h))
    assert not ids(a) & ids(b)


def test_every_look_the_covers_ask_for_is_printed_for_every_manager():
    """A look missing from assets/managers silently drops the manager from
    his cover, so the renderer and the photo script must agree."""
    import re
    from pathlib import Path
    from halfmen import config
    src = Path(cover.__file__).read_text()
    looks = set(re.findall(r'_cut\(img, [^,]+, "(\w+)"', src))
    faces = set(re.findall(r'_face\(img, [^,]+, "(\w+)"', src))
    assert looks and faces
    d = Path(cover.__file__).parent.parent / "assets" / "managers"
    for oid in config.managers():
        for k in looks:
            assert (d / f"{oid}_body-{k}.webp").exists(), (oid, k)
        for k in faces:
            assert (d / f"{oid}_face-{k}.webp").exists(), (oid, k)


ONE_PERSON = [x for x in STORIES + MORE if x["kind"] in cover.ROTATING] + [
    dict(BASE, kind="streak", owner="1", first="Clayton", n=5, rec="10–2", pf="925"),
    dict(BASE, kind="blowout", owner="1", first="Isiah", loser="Thad", margin="61", pts_w="162.4", pts_l="101.0"),
]


@pytest.mark.parametrize("skin", cover.SKINS)
@pytest.mark.parametrize("story", ONE_PERSON, ids=lambda s: s["kind"])
def test_every_one_person_story_runs_in_every_skin(story, skin):
    out = cover.render(story, _img(), skin=skin)
    assert out.startswith('<div class="kx wc"') and 'class="cut"' in out
    assert "&lt;br&gt;" not in out and "{" not in out.replace("{body}", "")


def test_an_unknown_skin_falls_back_to_the_story_s_own():
    assert cover.render(STORIES[0], _img(), skin="nope") == cover.render(STORIES[0], _img())


def test_the_deal_never_repeats_a_skin_within_two_weeks():
    kinds = {w: ("biggest" if w % 3 else "bench") for w in range(1, 18)}
    skins = cover.deal(kinds, "2026")
    seq = [skins[w] for w in sorted(skins)]
    assert all(seq[i] not in seq[max(0, i - 2):i] for i in range(len(seq)))
    assert len(set(seq)) >= 6


def test_the_deal_is_the_same_every_time_and_keeps_pinned_weeks():
    kinds = {w: "biggest" for w in range(1, 8)}
    assert cover.deal(kinds, "2026") == cover.deal(kinds, "2026")
    assert cover.deal(kinds, "2026", {3: "slate"})[3] == "slate"


def test_fixed_layouts_keep_their_own_look_and_block_their_lookalike():
    skins = cover.deal({1: "issue", 2: "biggest", 3: "biggest"}, "x")
    assert skins[1] == "issue" and "cyan" not in (skins[2], skins[3])


NEW_ONE_PERSON = [
    dict(BASE, kind="close", owner="1", first="Josh", loser="Corey", margin="0.4", pts_w="118.2", pts_l="117.8"),
    dict(BASE, kind="surge", owner="1", first="Josh", rec="7–7", before=31, after=62, delta="+31", up=True),
    dict(BASE, kind="surge", owner="1", first="Isiah", rec="6–8", before=58, after=36, delta="-22", up=False),
    dict(BASE, kind="trade", owner="1", first="Thad", other="Lucas", gets_a="KAMARA", gets_b="WADDLE, PICKS"),
]


@pytest.mark.parametrize("skin", cover.SKINS)
@pytest.mark.parametrize("story", NEW_ONE_PERSON, ids=lambda s: s["kind"] + str(s.get("up", "")))
def test_the_new_highlights_run_in_every_skin(story, skin):
    out = cover.render(story, _img(), skin=skin)
    assert out.startswith('<div class="kx wc"') and 'class="cut"' in out


def test_a_drop_in_playoff_odds_reads_as_a_freefall():
    assert "FREEFALL" in cover.render(NEW_ONE_PERSON[2], _img(), skin="splat")


def test_the_star_s_other_feats_lead_the_cover_lines_in_every_skin():
    s = dict(STORIES[0], feats=["BEAT BRANDON BY 2.3", "PLAYOFF ODDS 23% → 38%"])
    for skin in cover.SKINS:
        assert "BEAT BRANDON BY 2.3" in cover.render(s, _img(), skin=skin), skin
