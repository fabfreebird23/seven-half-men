"""The minutes are transcribed, not edited.

Tidying somebody else's jokes is how you kill them, so the only thing worth
testing is that the record survives the trip to the page intact and at the right
depth - an outline that loses its levels stops being funny.
"""
from __future__ import annotations

import re
from pathlib import Path

from halfmen import minutes

SRC = (Path(__file__).resolve().parent.parent / "app.py").read_text()


def test_there_is_a_meeting_on_the_record():
    m = minutes.latest()
    assert m["date"] and m["title"] and m["minuted_by"]
    assert m["items"], "a meeting with no minutes is not minutes"


def test_the_outline_keeps_its_depth():
    """Three levels in the founding minutes, and the third one is the payoff."""
    def deepest(items, d=1):
        return max([d] + [deepest(k, d + 1) for _, k in items if k])
    assert deepest(minutes.latest()["items"]) == 3


def test_it_is_verbatim():
    """No editorialising - if these lines ever get 'improved', this fails."""
    flat = str(minutes.latest()["items"])
    for line in ("Very embarrassing.", "Lucas stopped him immediately",
                 "Thad got screwed", "Very rude"):
        assert line in flat


def test_the_minutes_render_nested_rather_than_flattened():
    assert "def outline(" in SRC
    assert "outline(kids) if kids else" in SRC, "sub-items have to recurse"


def test_they_live_under_the_rulebook_not_in_the_nav():
    """Ten leaves was the point of the last change. The minutes ride along on
    the Rules page rather than buying another tap."""
    groups = re.search(r"GROUPS = \{.*?\n\}\n", SRC, re.S).group(0)
    assert "minutes" not in groups
    assert "render_minutes()" in SRC
