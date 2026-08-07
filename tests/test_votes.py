"""Eight people voting from a bar at the same time.

The failure that matters is not a crash, it is a vote that silently does not
count - which nobody notices until the tally is read out and somebody says "I
definitely picked week 12".
"""
from __future__ import annotations

import pytest

from halfmen import config, remote, storage


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    remote.invalidate()
    yield
    remote.invalidate()


def test_a_vote_is_recorded_and_can_be_changed():
    storage.record_vote("deadline", "alice", 1, 2026)
    assert storage.votes(2026)["deadline"] == {"alice": 1}
    storage.record_vote("deadline", "alice", 3, 2026)
    assert storage.votes(2026)["deadline"] == {"alice": 3}, "replaced, not appended"


def test_questions_do_not_collide_and_the_draw_is_untouched():
    storage.save_draw(11, ["a"], ["b"], 2026)
    storage.record_vote("deadline", "alice", 0, 2026)
    storage.record_vote("vetoes", "bob", 2, 2026)
    v = storage.votes(2026)
    assert v["deadline"] == {"alice": 0} and v["vetoes"] == {"bob": 2}
    assert storage.load_draw(2026)["seed"] == 11, "a vote must not eat the rest of the blob"


def test_concurrent_voters_do_not_overwrite_each_other(monkeypatch):
    """The real scenario: eight managers each holding a copy of the file from
    before the others voted. A plain write is last-one-wins and eats the rest;
    the mutation re-reads inside its retry loop, so every vote lands."""
    server = {"blob": {"season": 2026}}
    monkeypatch.setattr(remote, "config", lambda: ("t", "r", "b"))
    monkeypatch.setattr(remote, "mutate",
                        lambda p, fn, m: server.__setitem__("blob", fn(server["blob"]))
                        or server["blob"])
    monkeypatch.setattr(remote, "read", lambda p: server["blob"])
    for i, name in enumerate("abcdefgh"):
        storage.record_vote("deadline", name, i % 4, 2026)
    assert len(server["blob"]["votes"]["deadline"]) == 8


def test_a_failed_push_still_records_locally(monkeypatch):
    """GitHub being down mid-meeting must not silently drop somebody's answer."""
    monkeypatch.setattr(remote, "config", lambda: ("t", "r", "b"))
    monkeypatch.setattr(remote, "mutate", lambda *a: None)
    monkeypatch.setattr(remote, "read", lambda p: None)
    storage.record_vote("deadline", "alice", 2, 2026)
    assert storage.votes(2026)["deadline"] == {"alice": 2}
