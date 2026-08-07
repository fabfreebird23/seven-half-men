"""The theme has to stay readable.

Rather than eyeball it, every foreground/background pair the app actually puts
text on is declared in theme.TEXT_PAIRS and checked against WCAG here. Add a new
coloured surface and you add its pair to that list, or this catches it.

There is one palette today. Everything here loops over PALETTES, so adding a
light ground later gets the same audit for free.
"""
from __future__ import annotations

import pytest

from halfmen import theme

AA_NORMAL = 4.5      # body text
AA_LARGE = 3.0       # 18.66px+ bold, or 24px+ regular
PALETTES = list(theme.PALETTES)

# Pairs that only ever carry large display type - headings, the big round
# numbers on contract cards, the ring centres.
LARGE_ONLY = {("--acc", "--card"), ("--acc2", "--card")}


def pairs():
    for pal in PALETTES:
        for fg, bg in theme.TEXT_PAIRS:
            yield pal, fg, bg


@pytest.mark.parametrize("pal,fg,bg", list(pairs()))
def test_every_text_pair_meets_contrast(pal, fg, bg):
    v = theme.palette_vars(pal)
    assert fg in v and bg in v, "%s is missing %s/%s" % (pal, fg, bg)
    ratio = theme.contrast(v[fg], v[bg])
    floor = AA_LARGE if (fg, bg) in LARGE_ONLY else AA_NORMAL
    assert ratio >= floor, "%s: %s on %s is %.2f:1, needs %.1f" % (pal, fg, bg, ratio, floor)


def test_the_muted_tier_is_still_legible_in_both():
    """--dim carries every eyebrow, caption and table header in the app. It is
    the one that quietly falls under the bar when a palette gets tweaked."""
    for pal in PALETTES:
        v = theme.palette_vars(pal)
        assert theme.contrast(v["--dim"], v["--card"]) >= AA_NORMAL


def test_all_palettes_define_the_same_tokens():
    """Trivially true with one palette; the point is that a second ground added
    later cannot ship missing a token the stylesheet references."""
    sets = [set(theme.palette_vars(p)) for p in PALETTES]
    for other in sets[1:]:
        assert other == sets[0], "palettes drifted: %s" % (other ^ sets[0])


def test_the_stylesheet_only_references_tokens_the_palette_defines():
    import re
    defined = set(theme.palette_vars(theme.DEFAULT)) | {
        "--f-display", "--f-body", "--f-data", "--f-script", "--r", "--r-sm"}
    used = set(re.findall(r"var\((--[a-z0-9-]+)\)", theme.css()))
    missing = used - defined
    assert not missing, "stylesheet uses undefined tokens: %s" % sorted(missing)


def test_contrast_maths():
    assert theme.contrast("#ffffff", "#000000") == pytest.approx(21.0, abs=0.01)
    assert theme.contrast("#ffffff", "#ffffff") == pytest.approx(1.0, abs=0.01)


def test_css_substitutes_cleanly_for_every_palette():
    """The stylesheet is built by replace() rather than %-formatting; make sure
    no placeholder survives and no literal percent got mangled."""
    for pal in PALETTES:
        out = theme.css(pal)
        assert "__FONTURL__" not in out and "__VARS__" not in out and "__FONTS__" not in out
        assert "%%" not in out
        assert theme.palette_vars(pal)["--acc"] in out


def test_the_display_face_is_a_real_condensed_cut():
    """Impact was only ever in the mockup because the artifact CSP blocks font
    CDNs. A real page loads the face it actually wanted."""
    css = theme.css()
    assert "Impact" not in css
    assert "fonts.googleapis.com" in css
    assert "Big Shoulders Display" in css and "Archivo" in css


def test_there_is_one_ground_and_it_is_dark():
    assert list(theme.PALETTES) == ["bloodysunday"]
    v = theme.palette_vars("bloodysunday")
    assert theme.contrast(v["--ink"], v["--bg"]) > 15, "near-black ground, bright ink"


def test_crimson_has_exactly_two_jobs():
    """The whole palette turns on this. A red brand that also means "warning"
    means nothing, so every other signal moved off red - positions included."""
    v = theme.palette_vars("bloodysunday")
    reds = {v["--acc"], v["--bad"]}
    for token in ("--good", "--warn", "--qb", "--rb", "--wr", "--te", "--acc2"):
        assert v[token] not in reds, "%s is wearing the brand colour" % token


def test_the_position_scale_is_the_brand_badge_set_lifted():
    """The brand's own values are mixed for an off-white ground - plum reads
    1.9:1 on a dark card. Each one has to clear the CARD, not just the ground."""
    v = theme.palette_vars("bloodysunday")
    for token in ("--qb", "--rb", "--wr", "--te"):
        assert theme.contrast(v[token], v["--card2"]) >= 4.5, token
        assert theme.contrast(v[token], v["--card"]) >= 4.5, token


# ---------------------------------------------------------------- liquid

def test_every_bowl_gets_its_own_gradient_ids():
    """Streamlit renders all tab panels into one document, so ids that only
    count within a single glance row collide across rows and the second row
    inherits the first row's colours."""
    import re
    ids = [re.search(r'id="c(lq\d+)"', theme.liquid(0.5, "#fff", "1", "x")).group(1)
           for _ in range(6)]
    assert len(set(ids)) == 6


def test_the_fill_level_never_reaches_the_brim():
    """A bowl filled to the top has no surface, so it reads as a solid disc -
    and several of these metrics are 1.0 by construction."""
    import re
    sy = lambda v: float(re.search(r"--sy:([-\d.]+)px", theme.liquid(v, "#fff", "1", "x")).group(1))
    assert sy(1.0) > 0, "a full bowl still shows a meniscus"
    assert sy(1.0) == sy(5.0), "out-of-range values clamp rather than overflow"
    assert sy(0.0) == 200.0, "an empty bowl is genuinely empty"
    assert sy(0.5) == 100.0, "mid-range is linear"


def test_the_level_rides_a_custom_property_not_a_transform():
    """CSS animations beat inline styles. If the level were set as an inline
    transform the bob keyframes would clobber it and every bowl would animate
    to the same height."""
    svg = theme.liquid(0.5, "#fff", "1", "x")
    assert "--sy:" in svg and "transform:translateY" not in svg


def test_the_wave_loops_without_a_seam():
    """Both sine components divide the 200-unit scroll distance, so translating
    the path by -200 lands it back on itself."""
    import re
    d = theme._WAVE_FRONT
    pts = dict((float(a), float(b)) for a, b in re.findall(r"(-?[\d.]+),(-?[\d.]+)", d))
    for x in (0.0, 40.0, 96.0):
        assert abs(pts[x] - pts[x + 200.0]) < 1e-6, "seam at x=%s" % x


def test_the_build_fingerprint_moves_when_the_stylesheet_does():
    """Streamlit Cloud can re-run app.py while keeping an already-imported
    module in memory, so a deploy lands with the old css still injected and
    nothing on the page says so. This is how you tell at a glance."""
    before = theme.fingerprint()
    assert before == theme.fingerprint(), "must be stable for the same stylesheet"
    assert len(before) == 6

    original = theme._TEMPLATE
    try:
        theme._TEMPLATE = original + "\n/* nudge */"
        assert theme.fingerprint() != before
    finally:
        theme._TEMPLATE = original
    assert theme.fingerprint() == before


# ------------------------------------------------- burn-down, strip, pods

def _series(**kw):
    base = {"name": "Someone", "values": [0, 10, 30, 55], "colour": "var(--acc)", "key": False}
    base.update(kw)
    return base


def test_burndown_draws_a_line_per_team():
    svg = theme.burndown([_series(name="A"), _series(name="B")], 100, 4)
    assert svg.count("<polyline") == 2


def test_only_highlighted_lines_get_a_debt_bracket():
    """The bracket is the argument - the gap from the endpoint up to the ceiling
    IS the bill - so it is spent on the lines worth reading, not all eight."""
    plain = theme.burndown([_series(), _series()], 100, 4)
    keyed = theme.burndown([_series(key=True), _series()], 100, 4)
    assert plain.count("<circle") == 0
    assert keyed.count("<circle") == 1


def test_burndown_pads_a_short_season():
    """Week 3 of the season should not stretch three points across seventeen."""
    svg = theme.burndown([_series(values=[0, 12])], 100, 17)
    pts = svg.split('points="')[1].split('"')[0].split()
    assert len(pts) == 17
    assert pts[-1].split(",")[1] == pts[1].split(",")[1], "flat after the last real week"


def test_burndown_labels_never_stack():
    """Eight teams converge near the ceiling; without pushing them apart the
    right-hand labels land on top of each other."""
    import re
    flat = [_series(name="T%d" % i, values=[0, 90, 95, 96]) for i in range(8)]
    svg = theme.burndown(flat, 100, 4)
    ys = [float(m) for m in re.findall(r'<text x="691" y="([\d.]+)"', svg)]
    assert len(ys) == 8
    assert all(b - a >= 14.9 for a, b in zip(sorted(ys), sorted(ys)[1:]))


def test_burndown_survives_an_empty_league():
    assert theme.burndown([], 100, 17) == ""


def test_capital_strip_is_one_block_per_round():
    html = theme.capital_strip(["live"] * 13)
    assert html.count("<i ") == 13


def test_capital_strip_distinguishes_the_four_states():
    html = theme.capital_strip(["live", "eaten", "traded", "extra"])
    for state in ("live", "eaten", "traded", "extra"):
        assert 'class="%s"' % state in html
    assert 'title="R3' in html, "each block says which round it is"


def test_a_pod_on_its_last_year_is_flagged():
    last = theme.taxi_pod("Jadyn Davis", "QB", "slot 1", year=2, years=2)
    first = theme.taxi_pod("Justice Haynes", "RB", "slot 2", year=1, years=2)
    assert "expiring" in last and "expiring" not in first
    assert 'chip bad">Year 2 of 2' in last
    assert 'chip warn">Year 1 of 2' in first


def test_a_pod_clock_has_one_segment_per_year():
    html = theme.taxi_pod("x", "QB", "slot 1", year=1, years=2)
    assert html.count("<i ") == 2 and html.count('class="on"') == 1


# ------------------------------------------------------------------ mobile

def test_the_section_heading_wraps_its_eyebrow_on_a_phone():
    """The eyebrow is nowrap and sits in a flex row with the title, so without
    this it pushed the whole heading past the viewport."""
    css = theme.css()
    phone = css[css.index("@media (max-width:640px)"):]
    assert ".bar{ flex-wrap:wrap" in phone
    assert "flex-basis:100%" in phone and "white-space:normal" in phone


def test_the_phone_breakpoints_target_the_element_that_exists():
    """A previous mobile rule targeted h2.bar long after the heading became a
    div, so it silently did nothing for weeks."""
    css = theme.css()
    assert "h2.bar" not in css, "stale selector - the heading is div.bar"


def test_the_bottom_bar_is_the_only_navigation():
    """Nav moved off a tab row into a floating pill bar with a drill-down
    sheet, matching what Kreeper and Babies & Boomer converged on."""
    css = theme.css()
    assert ".bb-wrap" in css and ".bb-pop" in css and ".bb-scrim" in css
    assert "position:fixed" in css.split(".bb-wrap")[1][:120]


def test_the_page_scrolls_clear_of_the_floating_bar():
    """The bar floats over the content, so the last card must not sit under
    it."""
    import re
    m = re.search(r"\.block-container\{[^}]*padding-bottom:calc\((\d+)px", theme.css())
    assert m and int(m.group(1)) >= 100


def test_the_bottom_bar_clears_the_home_indicator():
    """At a flat 18px the pill sits in the iPhone swipe zone, and this league
    will be on phones during the draft."""
    css = theme.css()
    assert "env(safe-area-inset-bottom)" in css
    assert css.count("env(safe-area-inset-bottom)") >= 3, "bar, sheet and page padding"


def test_the_fingerprint_is_still_reachable_after_leaving_the_masthead():
    """It came off the face of the masthead as clutter, not as a capability.
    Diagnosing a stale Streamlit Cloud module still needs it, so it moved to the
    title attribute rather than being deleted."""
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "halfmen" / "theme.py").read_text()
    mast = src[src.index("def masthead"):src.index("def bar(")]
    assert 'title="build %s"' in mast
    assert "&middot; build" not in mast, "not on the face of it any more"
