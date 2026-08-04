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
        "--f-display", "--f-body", "--f-data", "--r", "--r-sm"}
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
