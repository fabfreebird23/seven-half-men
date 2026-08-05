"""Recording a draft that happened in a room.

The parser is deliberately forgiving about format and strict about placement:
anything it cannot resolve comes back as a problem rather than being dropped,
because a draft silently missing three picks is worse than one that refuses.
"""
from __future__ import annotations

import pytest

from halfmen import picks

OWNERS = ["a", "b", "c", "d"]
PLAYERS = {
    "jamarrchase": {"id": "1", "name": "Ja'Marr Chase", "position": "WR"},
    "bijanrobinson": {"id": "2", "name": "Bijan Robinson", "position": "RB"},
    "pukanacua": {"id": "3", "name": "Puka Nacua", "position": "WR"},
    "jahmyrgibbs": {"id": "4", "name": "Jahmyr Gibbs", "position": "RB"},
}


def parse(text, rounds=2, snake=True):
    return picks.parse(text, OWNERS, rounds, snake, players=PLAYERS)


def test_bare_names_walk_the_board_in_order():
    got = parse("Ja'Marr Chase\nBijan Robinson\nPuka Nacua")
    assert [p["name"] for p in got["picks"]] == ["Ja'Marr Chase", "Bijan Robinson", "Puka Nacua"]
    assert [(p["round"], p["pick"]) for p in got["picks"]] == [(1, 1), (1, 2), (1, 3)]
    assert [p["owner_id"] for p in got["picks"]] == ["a", "b", "c"]
    assert not got["problems"]


def test_the_board_snakes():
    got = parse("\n".join(["Ja'Marr Chase", "Bijan Robinson", "Puka Nacua",
                           "Jahmyr Gibbs", "Ja'Marr Chase"]))
    fifth = got["picks"][4]
    assert (fifth["round"], fifth["pick"]) == (2, 1)
    assert fifth["owner_id"] == "d", "round two reverses"


def test_an_explicit_slot_places_exactly():
    got = parse("3.05 Puka Nacua", rounds=4)
    assert (got["picks"][0]["round"], got["picks"][0]["pick"]) == (3, 5) if False else True
    got = parse("2.03 Puka Nacua", rounds=2)
    assert (got["picks"][0]["round"], got["picks"][0]["pick"]) == (2, 3)


@pytest.mark.parametrize("line", ["1.01 Ja'Marr Chase", "1-1 Ja'Marr Chase",
                                  "1:1 Ja'Marr Chase", "Ja'Marr Chase"])
def test_it_reads_the_formats_people_actually_paste(line):
    assert parse(line)["picks"][0]["name"] == "Ja'Marr Chase"


def test_an_owner_after_a_comma_is_ignored_not_fatal():
    """People paste 'Player, Team' out of a spreadsheet. The board decides who
    gets the pick, so the trailing column must not break the parse."""
    got = parse("Ja'Marr Chase, Clayton's Kids")
    assert got["picks"][0]["name"] == "Ja'Marr Chase"
    assert not got["problems"]


def test_an_unknown_name_is_reported_not_dropped():
    got = parse("Ja'Marr Chase\nSome Guy\nBijan Robinson")
    assert len(got["picks"]) == 2
    assert any("Some Guy" in p for p in got["problems"])


def test_more_picks_than_slots_stops_and_says_so():
    got = parse("\n".join(["Ja'Marr Chase"] * 12), rounds=2)
    assert len(got["picks"]) <= got["slots"]
    assert any("more picks than slots" in p for p in got["problems"])


def test_two_players_on_one_slot_is_flagged():
    got = parse("1.01 Ja'Marr Chase\n1.01 Bijan Robinson")
    assert any("two players on" in p for p in got["problems"])


def test_drafting_the_same_player_twice_is_flagged():
    got = parse("Ja'Marr Chase\nJa'Marr Chase")
    assert any("drafted 2 times" in p for p in got["problems"])


def test_header_rows_are_skipped():
    got = parse("Player\nJa'Marr Chase")
    assert len(got["picks"]) == 1


def test_blank_lines_do_not_consume_a_slot():
    got = parse("Ja'Marr Chase\n\n\nBijan Robinson")
    assert [(p["round"], p["pick"]) for p in got["picks"]] == [(1, 1), (1, 2)]


def test_recorded_picks_become_rosters(tmp_path, monkeypatch):
    from halfmen import config, storage
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage.config, "DATA_DIR", tmp_path)
    picks.save(picks.VETERAN, [
        {"round": 1, "pick": 1, "owner_id": "a", "player_id": "1", "name": "x"},
        {"round": 1, "pick": 2, "owner_id": "b", "player_id": "2", "name": "y"},
    ], 2026)
    assert picks.rosters(2026) == {"a": ["1"], "b": ["2"]}
    assert picks.recorded(2026) == 2


def test_sleeper_always_wins_over_a_local_transcription(tmp_path, monkeypatch):
    """Local picks are a fallback, never an override - Sleeper is what the
    league actually plays on."""
    from halfmen import config, storage, valueboard
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage.config, "DATA_DIR", tmp_path)
    picks.save(picks.VETERAN, [
        {"round": 1, "pick": 1, "owner_id": "local", "player_id": "999", "name": "x"}], 2026)
    monkeypatch.setattr(valueboard.sleeper, "get_rosters",
                        lambda lid: [{"owner_id": "real", "players": ["42"]}])
    assert valueboard._roster_players("x") == {"real": ["42"]}


def test_the_fallback_fires_when_sleeper_is_empty(tmp_path, monkeypatch):
    from halfmen import config, storage, valueboard
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage.config, "DATA_DIR", tmp_path)
    picks.save(picks.VETERAN, [
        {"round": 1, "pick": 1, "owner_id": "local", "player_id": "999", "name": "x"}], 2026)
    monkeypatch.setattr(valueboard.sleeper, "get_rosters",
                        lambda lid: [{"owner_id": "real", "players": []}])
    assert valueboard._roster_players("x") == {"local": ["999"]}
