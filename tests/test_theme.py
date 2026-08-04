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
    assert list(theme.PALETTES) == ["acid"]
    v = theme.palette_vars("acid")
    assert theme.contrast(v["--ink"], v["--bg"]) > 15, "near-black ground, bright ink"


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
