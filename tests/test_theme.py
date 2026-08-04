"""Both palettes have to stay readable when you flip between them.

Rather than eyeball it, every foreground/background pair the app actually puts
text on is declared in theme.TEXT_PAIRS and checked against WCAG here. Add a new
coloured surface and you add its pair to that list, or this catches it.
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


def test_both_palettes_define_the_same_tokens():
    a, b = (set(theme.palette_vars(p)) for p in PALETTES)
    assert a == b, "palettes drifted: %s" % (a ^ b)


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


def test_the_display_face_is_not_a_condensed_fallback():
    """Impact was only ever there because the mockup ran under a CSP that blocks
    font CDNs. A real page loads a real face."""
    css = theme.css("lights_off")
    assert "Impact" not in css
    assert "fonts.googleapis.com" in css
    assert "Archivo" in css
