"""What the app does when GitHub throttles it.

All of this was found on the Babies and Boomer draft night (2026-09-07), ported
here from docs/LIVE_DRAFT_FIXES.md. The REST quota is 5,000/hour per GitHub
USER - shared by every token that user owns - and a room full of people
watching a live board eats it in minutes. A 403 then fell through to the empty
local file, which renders as a blank board: "0 picks in", no keepers, for the
rest of the hour.

None of this is reachable by clicking around. It only happens when the quota is
gone, which is exactly when nobody can debug it.
"""
from __future__ import annotations

import json

import pytest

from halfmen import remote


class FakeResp:
    def __init__(self, status, payload=None, content=b""):
        self.status_code = status
        self._payload = payload
        self.content = content

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP %d" % self.status_code)


@pytest.fixture(autouse=True)
def _wired(monkeypatch):
    monkeypatch.setattr(remote, "config", lambda: ("tok", "owner/repo", "league-data"))
    remote._cache.clear()
    remote._own.clear()
    remote._branch_seen.clear()


def test_the_blob_sha_is_the_one_github_wants_back():
    """A raw-CDN read has to produce a usable sha or the next write 409s. This
    is git's own blob hash, so `git hash-object` agrees with it."""
    assert remote._blob_sha(b"{}") == "9e26dfeeb6e641a33dae4961196235bdb965b21b"
    assert remote._blob_sha(b"") == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"


def test_a_throttled_read_falls_back_to_the_cdn_not_to_nothing(monkeypatch):
    """The whole bug in one test: over quota, the board must still have data."""
    body = b'{"picks": {"veteran": [1, 2, 3]}}'
    monkeypatch.setattr(remote, "_raw_get", lambda repo, br, path, tok: body)

    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp(403))
    data, sha = remote._fetch("data/keepers_2026.json")
    assert data == json.loads(body), "a 403 must not read as an empty league"
    assert sha == remote._blob_sha(body), "and a save afterwards must still work"


def test_a_missing_file_is_still_missing_when_throttled(monkeypatch):
    monkeypatch.setattr(remote, "_raw_get", lambda repo, br, path, tok: None)
    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp(403))
    assert remote._fetch("data/nope.json") == (None, None)


def test_a_failed_read_serves_the_last_good_answer(monkeypatch):
    """Stale-on-error. An empty board is worse than a slightly old one."""
    remote._cache["p"] = (9e9, {"picks": "good"})
    monkeypatch.setattr(remote, "_fetch", lambda path: (_ for _ in ()).throw(RuntimeError()))
    remote._cache["p"] = (0, {"picks": "good"})       # expired, forces a fetch
    assert remote.read("p") == {"picks": "good"}


def test_our_own_write_beats_the_api_for_a_while():
    """The contents API is CDN-fronted and can hand back the value we just
    overwrote. On draft night that reads as the board rolling backwards."""
    remote._own["p"] = (9e9, {"picks": "mine"})
    assert remote.read("p") == {"picks": "mine"}


# ------------------------------------------------------- the branch check

def test_the_branch_is_only_checked_once_per_process(monkeypatch):
    calls = []
    import requests
    monkeypatch.setattr(requests, "get",
                        lambda url, **k: (calls.append(url), FakeResp(200))[1])
    for _ in range(5):
        remote._ensure_branch("owner/repo", "league-data", "tok")
    assert len(calls) == 1, "one check, not one per write"


def test_a_throttled_branch_check_does_not_try_to_create_the_branch(monkeypatch):
    """It already exists. Treating 403 as 'missing' fired three more API calls
    trying to create it - on every save, while already over quota."""
    calls = []
    import requests
    monkeypatch.setattr(requests, "get",
                        lambda url, **k: (calls.append(("GET", url)), FakeResp(403))[1])
    monkeypatch.setattr(requests, "post",
                        lambda url, **k: (calls.append(("POST", url)), FakeResp(201))[1])
    remote._ensure_branch("owner/repo", "league-data", "tok")
    assert not [c for c in calls if c[0] == "POST"], "must not try to create it"
    remote._ensure_branch("owner/repo", "league-data", "tok")
    assert len(calls) == 1, "and it is remembered"
