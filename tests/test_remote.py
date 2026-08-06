"""The season blob has to outlive the container.

Streamlit Cloud throws away data/ on every reboot and redeploy. These tests
cover the two behaviours that make that survivable: the branch copy wins when it
exists, and a GitHub failure degrades to the local file rather than showing the
league an empty draw.
"""
from __future__ import annotations

import json

import pytest

from halfmen import config, remote, storage


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    remote.invalidate()
    yield
    remote.invalidate()


def test_no_token_means_plain_local_files(monkeypatch):
    monkeypatch.setattr(remote, "config", lambda: None)
    storage.save({"season": 2026, "teams": {"a": {"entries": []}}}, 2026)
    assert storage.load(2026)["teams"] == {"a": {"entries": []}}


def test_the_branch_copy_wins_over_a_stale_container(monkeypatch):
    """The container's local file is whatever this replica last wrote. The
    branch is what the league did."""
    monkeypatch.setattr(remote, "config", lambda: ("t", "r", "b"))
    monkeypatch.setattr(remote, "read", lambda p: {"season": 2026, "draw": {"seed": 7}})
    monkeypatch.setattr(remote, "write", lambda p, d, m: True)
    storage.save({"season": 2026, "draw": {"seed": 99}}, 2026)
    assert storage.load(2026)["draw"]["seed"] == 7


def test_github_being_down_falls_back_to_local_not_to_empty(monkeypatch):
    monkeypatch.setattr(remote, "config", lambda: ("t", "r", "b"))
    monkeypatch.setattr(remote, "write", lambda p, d, m: False)
    monkeypatch.setattr(remote, "read", lambda p: None)
    storage.save_draw(4242, ["a"], ["b"], 2026)
    assert storage.load_draw(2026)["seed"] == 4242, "the draw survives a failed push"


def test_a_save_always_lands_locally_even_when_the_push_works(monkeypatch):
    monkeypatch.setattr(remote, "config", lambda: ("t", "r", "b"))
    pushed = {}
    monkeypatch.setattr(remote, "write",
                        lambda p, d, m: pushed.update({"path": p, "data": d}) or True)
    monkeypatch.setattr(remote, "read", lambda p: None)
    storage.save({"season": 2026, "locked": True}, 2026)
    assert pushed["path"] == "data/keepers_2026.json"
    assert json.loads(storage._path(2026).read_text())["locked"] is True


def test_a_read_error_serves_the_last_good_value(monkeypatch):
    """Mid-draw, an API blip must not blank the board eight people are watching."""
    monkeypatch.setattr(remote, "config", lambda: ("t", "r", "b"))
    calls = {"n": 0}

    def flaky(path):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"ok": 1}, "sha"
        raise RuntimeError("502")

    monkeypatch.setattr(remote, "_fetch", flaky)
    monkeypatch.setattr(remote, "_TTL", -1)   # force a re-fetch every call
    assert remote.read("p") == {"ok": 1}
    assert remote.read("p") == {"ok": 1}, "served from the last good read"


def test_the_token_never_comes_from_the_public_yaml():
    """config.yaml is in a public repo. If a token could be read from it we
    would have shipped one."""
    assert "github_token" not in (config.CONFIG_PATH.read_text())


def test_our_own_write_beats_a_stale_api_read(monkeypatch):
    """GitHub's contents API is CDN-cached for up to a minute. Writing the draw
    and reading it straight back returned the OLD value against the real repo -
    which on the night means the commissioner opens an envelope and the board
    rolls backwards. What we just wrote wins."""
    monkeypatch.setattr(remote, "config", lambda: ("t", "r", "b"))
    monkeypatch.setattr(remote, "_ensure_branch", lambda *a: None)
    monkeypatch.setattr(remote, "_fetch", lambda p: ({"n": 1}, "sha"))

    class OK:
        status_code = 200
    monkeypatch.setattr("requests.put", lambda *a, **k: OK())

    assert remote.write("p", {"n": 2}, "m") is True
    monkeypatch.setattr(remote, "_TTL", -1)   # even with the read cache expired
    assert remote.read("p") == {"n": 2}, "not the stale {'n': 1} the API would serve"


def test_the_read_carries_a_cache_buster(monkeypatch):
    """Without it the CDN keeps handing back the same body to every replica."""
    monkeypatch.setattr(remote, "config", lambda: ("t", "r", "b"))
    seen = []

    class R:
        status_code = 200
        @staticmethod
        def raise_for_status(): pass
        @staticmethod
        def json():
            import base64, json as j
            return {"content": base64.b64encode(j.dumps({"ok": 1}).encode()).decode(),
                    "sha": "s"}

    def get(url, **kw):
        seen.append(kw.get("params", {}))
        return R()

    monkeypatch.setattr("requests.get", get)
    remote._fetch("p"); remote._fetch("p")
    assert all("_" in p for p in seen)
    assert seen[0]["_"] != seen[1]["_"], "the buster has to actually change"


def test_the_probe_names_the_actual_failure(monkeypatch):
    """"Is my token set up right" has four different wrong answers and they need
    four different fixes. Reading config can only distinguish one of them."""
    monkeypatch.setattr(remote, "config", lambda: None)
    assert "TOML" in remote.probe()["detail"], "unparsed secrets is the common one"

    monkeypatch.setattr(remote, "config", lambda: ("t", "r/x", "b"))

    class Resp:
        def __init__(self, code): self.status_code = code

    monkeypatch.setattr("requests.get", lambda url, **k: Resp(401))
    assert "revoked" in remote.probe()["detail"]

    monkeypatch.setattr("requests.get",
                        lambda url, **k: Resp(200 if url.endswith("/user") else 404))
    assert "Repository access" in remote.probe()["detail"]

    monkeypatch.setattr("requests.get", lambda url, **k: Resp(200))
    monkeypatch.setattr(remote, "write", lambda *a: False)
    assert "read and write" in remote.probe()["detail"]


def test_the_probe_confirms_a_real_round_trip(monkeypatch):
    monkeypatch.setattr(remote, "config", lambda: ("t", "fab/repo", "league-data"))

    class Resp:
        status_code = 200

    monkeypatch.setattr("requests.get", lambda url, **k: Resp())
    store = {}
    monkeypatch.setattr(remote, "write",
                        lambda p, d, m: bool(store.__setitem__(p, d)) or True)
    monkeypatch.setattr(remote, "read", lambda p: store.get(p))
    got = remote.probe()
    assert got["ok"]
    assert "league-data" in got["detail"]


def test_a_write_that_cannot_be_read_back_at_all_fails(monkeypatch):
    monkeypatch.setattr(remote, "config", lambda: ("t", "fab/repo", "b"))

    class Resp:
        status_code = 200

    monkeypatch.setattr("requests.get", lambda url, **k: Resp())
    monkeypatch.setattr(remote, "write", lambda *a: True)
    monkeypatch.setattr(remote, "read", lambda p: None)
    assert not remote.probe()["ok"]


def test_a_stale_read_back_is_still_a_pass(monkeypatch):
    """GitHub's CDN can serve the previous body for another minute and the
    cache-buster does not reliably beat it - measured against the real repo. A
    probe that failed on that would cry wolf every time; freshness is the
    own-write hold's job, not this check's."""
    monkeypatch.setattr(remote, "config", lambda: ("t", "fab/repo", "b"))

    class Resp:
        status_code = 200

    monkeypatch.setattr("requests.get", lambda url, **k: Resp())
    monkeypatch.setattr(remote, "write", lambda *a: True)
    monkeypatch.setattr(remote, "read", lambda p: {"checked_at": "an older stamp"})
    assert remote.probe()["ok"]
