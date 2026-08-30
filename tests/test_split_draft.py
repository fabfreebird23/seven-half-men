"""A draft that ran on two Sleeper boards is still one draft.

Sleeper fixes the round count when a board is created, so the 2026 veteran
draft - 14 rounds - had to finish on a second board after the first was built
for 10. That second board numbers its own rounds from 1, and its round 1 is the
league's round 11.

Nothing errors when this is wrong. The picks are all there, attributed to the
right managers, in the right order. Only the ROUND is off, and the round is the
keeper price: every player taken in rounds 11-14 was recorded as a 1st- to
4th-rounder, which prices him to keep at up to ten rounds more expensive than
the rules say. Jalen Coker went 11.07 and the board had him as a 1st-rounder.
"""
from __future__ import annotations

import pytest

from halfmen import config, history


PARTS = [
    {"draft_id": "aaa", "settings": {"player_type": 0, "rounds": 10, "teams": 8},
     "status": "complete", "type": "snake"},
    {"draft_id": "bbb", "settings": {"player_type": 0, "rounds": 4, "teams": 8},
     "status": "complete", "type": "snake"},
]


@pytest.fixture
def split(monkeypatch):
    monkeypatch.setattr(history.config, "drafts",
                        lambda: {"sleeper_drafts": {"veteran": ["aaa", "bbb"]},
                                 "veteran_rounds": 14, "rookie_rounds": 2})
    monkeypatch.setattr(history.sleeper, "get_drafts", lambda lid: list(PARTS))
    return PARTS


def test_the_second_board_continues_the_rounds_it_does_not_restart_them(split):
    got = dict((d["draft_id"], off) for d, off in history._real_drafts("x"))
    assert got == {"aaa": 0, "bbb": 10}, "board two starts at round 11"


def test_a_pick_on_the_second_board_lands_on_the_right_round(monkeypatch, split):
    """11.07 is an 11th-rounder. Recorded as a 1st-rounder it would cost a
    first-round pick to keep."""
    monkeypatch.setattr(history.sleeper, "league_chain",
                        lambda lid: [{"season": 2026, "league_id": "x"}])
    monkeypatch.setattr(history.sleeper, "get_players",
                        lambda: {"9": {"full_name": "Late Pick", "years_exp": 3}})
    monkeypatch.setattr(history.storage, "load", lambda season: {})
    monkeypatch.setattr(history.local_picks, "draft_rows", lambda: [])

    def picks(draft_id, ttl=900):
        if draft_id == "bbb":       # its own round 1 == the league's round 11
            return [{"player_id": "9", "picked_by": "o", "round": 1, "pick_no": 7}]
        return []
    monkeypatch.setattr(history.sleeper, "get_draft_picks", picks)

    h = history.build("x")
    assert h.draft_round("9") == 11


def test_an_unconfigured_league_still_reads_every_draft_at_offset_zero(monkeypatch):
    """A past season keyed in before the setting existed, or a league that
    never split a draft, must not silently lose its drafts."""
    monkeypatch.setattr(history.config, "drafts", lambda: {"veteran_rounds": 14,
                                                           "rookie_rounds": 2})
    monkeypatch.setattr(history.sleeper, "get_drafts", lambda lid: list(PARTS))
    assert [off for _d, off in history._real_drafts("x")] == [0, 0]


def test_junk_drafts_are_not_read_at_all(monkeypatch):
    """The abandoned 16-round rookie draft holds the same picks as the real
    one, so reading both recorded every rookie twice."""
    junk = dict(PARTS[0], draft_id="junk")
    monkeypatch.setattr(history.config, "drafts",
                        lambda: {"sleeper_drafts": {"veteran": ["aaa"]},
                                 "veteran_rounds": 14, "rookie_rounds": 2})
    monkeypatch.setattr(history.sleeper, "get_drafts", lambda lid: [PARTS[0], junk])
    assert [d["draft_id"] for d, _o in history._real_drafts("x")] == ["aaa"]
