"""Turning what somebody said into a player.

Speech mangles these names badly and predictably, so the cases here are real
mis-transcriptions rather than tidy inputs. Two of them are bugs the first
version of this shipped with, kept as tests so they cannot come back.
"""
from __future__ import annotations

import pytest

from halfmen import voice

ROSTER = [
    {"id": "1", "name": "Ja'Marr Chase", "position": "WR"},
    {"id": "2", "name": "Bijan Robinson", "position": "RB"},
    {"id": "3", "name": "Puka Nacua", "position": "WR"},
    {"id": "4", "name": "Jaren Kanak", "position": "LB"},
    {"id": "5", "name": "De'Von Achane", "position": "RB"},
    {"id": "6", "name": "Nick Nash", "position": "WR"},
    {"id": "7", "name": "Amon-Ra St. Brown", "position": "WR"},
    {"id": "8", "name": "A.J. Brown", "position": "WR"},
    {"id": "9", "name": "Lamar Jackson", "position": "QB"},
    {"id": "10", "name": "Malik Nabers", "position": "WR"},
    {"id": "11", "name": "Jahmyr Gibbs", "position": "RB"},
]


def said(text, exclude=()):
    got = voice.match(text, ROSTER, exclude=exclude)
    return got["player"]["name"] if got else None


@pytest.mark.parametrize("heard,want", [
    ("jamar chase", "Ja'Marr Chase"),
    ("malik nabors", "Malik Nabers"),
    ("lamar jackson", "Lamar Jackson"),
    ("gibbs", "Jahmyr Gibbs"),
    ("brock", None),
])
def test_it_hears_the_ordinary_cases(heard, want):
    assert said(heard) == want


def test_a_surname_is_not_matched_inside_a_flattened_blob():
    """"puka nakua" concatenates to "pukanakua", which contains "kanak". The
    first version drafted Jaren Kanak off exactly that."""
    assert said("puka nakua") == "Puka Nacua"


def test_the_first_name_breaks_a_surname_tie():
    """Both are Brown. Only one of them is who anyone meant."""
    assert said("amon ra saint brown") == "Amon-Ra St. Brown"


def test_a_name_speech_split_in_two_still_lands():
    """"Achane" comes back as "a shane" about as often as not."""
    assert said("deevon a shane") == "De'Von Achane"
    assert said("devon achane") == "De'Von Achane"


def test_it_finds_the_name_inside_a_whole_sentence():
    """People announce picks, they do not read out bare names."""
    assert said("with the ninth pick isiah takes lamar jackson") == "Lamar Jackson"


def test_nonsense_matches_nothing():
    assert said("zzzzzz") is None
    assert said("") is None
    assert said("uh") is None


def test_an_already_drafted_player_is_not_offered():
    assert said("jamar chase", exclude=["1"]) is None


def test_it_only_calls_itself_sure_when_nothing_else_is_close():
    """A thin margin between two players is the one case where guessing is worse
    than asking."""
    clean = voice.match("lamar jackson", ROSTER)
    assert clean["sure"], clean

    tie = voice.match("brown", ROSTER)
    assert tie is not None
    assert not tie["sure"], "two Browns - it must not pick one on its own"


def test_similarity_is_symmetric_and_bounded():
    assert voice.similarity("nacua", "nacua") == 1.0
    assert voice.similarity("nacua", "nakua") == voice.similarity("nakua", "nacua")
    assert 0.0 <= voice.similarity("nacua", "kanak") < 0.6


def test_adjacent_words_are_joined_as_candidates():
    assert "ashane" in voice.tokens("a shane")
    assert "saintbrown" in voice.tokens("saint brown")
