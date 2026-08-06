"""Durable storage for the one file this app actually writes.

Streamlit Cloud gives every app a container it will throw away - on a reboot,
on a redeploy, on its own schedule. Anything under data/ is scratch space. That
is fine for the Sleeper cache, which rebuilds itself, and fatal for the two
things that cannot: the keeper slips eight managers submit once a year, and the
season-one draw. Losing the draw mid-read-out, with the room watching, is the
failure this exists to prevent.

So the season blob lives on a branch of this app's own repo, written through
the GitHub contents API. A separate branch, not main, because a commit to main
redeploys the app - which would restart the container in the middle of the very
thing we are protecting.

No token configured means local files, unchanged. That is the whole dev story,
and it is also the fallback if GitHub is down: a read failure falls back to the
local copy rather than showing eight people an empty draw.
"""
from __future__ import annotations

import base64
import itertools
import json
import time
from typing import Any, Dict, Optional, Tuple

_API = "https://api.github.com"
_TTL = 5.0          # seconds; the draw reveal has to feel live to a room
_cache: Dict[str, Tuple[float, Any]] = {}

# GitHub's contents API is served through a CDN that holds a copy for up to a
# minute. Writing the draw and immediately reading it back returned the OLD
# value in testing - which on the night would mean the commissioner opens an
# envelope and the board rolls back. Two defences: bust the cache on the way
# out, and trust what we just wrote for longer than we trust the API.
_OWN_HOLD = 90.0
_own: Dict[str, Tuple[float, Any]] = {}
_bust = itertools.count()


def config() -> Optional[Tuple[str, str, str]]:
    """(token, repo, branch), or None when we should stay local.

    The token only ever comes from Streamlit secrets - never from the YAML,
    which is public.
    """
    try:
        import streamlit as st
        tok = st.secrets.get("github_token")
    except Exception:
        return None
    if not tok:
        return None
    try:
        repo = str(st.secrets.get("github_repo", "fabfreebird23/seven-half-men"))
        branch = str(st.secrets.get("github_branch", "league-data"))
    except Exception:
        repo, branch = "fabfreebird23/seven-half-men", "league-data"
    return str(tok), repo, branch


def enabled() -> bool:
    return config() is not None


def _headers(tok: str) -> dict:
    return {"Authorization": "Bearer %s" % tok, "Accept": "application/vnd.github+json"}


def _ensure_branch(repo: str, branch: str, tok: str) -> None:
    import requests
    h = _headers(tok)
    r = requests.get("%s/repos/%s/branches/%s" % (_API, repo, branch), headers=h, timeout=15)
    if r.status_code == 200:
        return
    info = requests.get("%s/repos/%s" % (_API, repo), headers=h, timeout=15).json()
    default = info.get("default_branch", "main")
    ref = requests.get("%s/repos/%s/git/ref/heads/%s" % (_API, repo, default),
                       headers=h, timeout=15).json()
    requests.post("%s/repos/%s/git/refs" % (_API, repo), headers=h, timeout=15,
                  json={"ref": "refs/heads/%s" % branch, "sha": ref["object"]["sha"]})


def _fetch(path: str) -> Tuple[Optional[dict], Optional[str]]:
    """(parsed json, blob sha). (None, None) when the file does not exist yet."""
    import requests
    tok, repo, branch = config()
    r = requests.get("%s/repos/%s/contents/%s" % (_API, repo, path),
                     headers={"Cache-Control": "no-cache", **_headers(tok)},
                     params={"ref": branch, "_": next(_bust)}, timeout=15)
    if r.status_code == 404:
        return None, None
    r.raise_for_status()
    j = r.json()
    body = base64.b64decode(j["content"]).decode()
    return (json.loads(body) if body.strip() else None), j["sha"]


def read(path: str) -> Optional[dict]:
    """Cached read. None means "nothing there" AND "could not tell" - both of
    which the caller handles the same way: use the local copy."""
    mine = _own.get(path)
    if mine and time.time() - mine[0] < _OWN_HOLD:
        # We wrote this. Our copy is definitionally at least as fresh as
        # anything the API will hand back, and possibly fresher.
        return mine[1]
    hit = _cache.get(path)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    try:
        data, _ = _fetch(path)
    except Exception:
        return hit[1] if hit else None
    _cache[path] = (time.time(), data)
    return data


def write(path: str, data: dict, message: str) -> bool:
    """Replace the file. Retries a concurrent-write conflict, because two
    managers submitting slips within the same second is exactly the case this
    has to survive. Returns False rather than raising - the caller always keeps
    a local copy too, so a failed push is a degraded save, not a lost one."""
    conf = config()
    if not conf:
        return False
    tok, repo, branch = conf
    try:
        import requests
        _ensure_branch(repo, branch, tok)
        for _ in range(3):
            _, sha = _fetch(path)
            body = {
                "message": message,
                "content": base64.b64encode(
                    json.dumps(data, indent=2, sort_keys=True).encode()).decode(),
                "branch": branch,
            }
            if sha:
                body["sha"] = sha
            r = requests.put("%s/repos/%s/contents/%s" % (_API, repo, path),
                             headers=_headers(tok), json=body, timeout=20)
            if r.status_code in (200, 201):
                now = time.time()
                _cache[path] = (now, data)
                _own[path] = (now, data)
                return True
            if r.status_code != 409:   # not a sha conflict, so retrying won't help
                return False
    except Exception:
        return False
    return False


PROBE_PATH = "data/_connection.json"


def probe() -> Dict[str, Any]:
    """Actually try it, and say what happened.

    "Is my token set up right" is not answerable by reading config - a token can
    be present and expired, present and scoped to the wrong repo, or the secrets
    file can have failed to parse and left nothing behind at all. So this does
    the real thing: writes a small file to the data branch and reads it back.

    Returns {ok, detail}. `detail` is written to be read by whoever is standing
    in front of the app, not by a log.
    """
    conf = config()
    if not conf:
        return {"ok": False, "detail":
                "No token is reaching the app. Either github_token is missing from the "
                "secrets, or the secrets failed to parse \u2014 the value has to be "
                "wrapped in double quotes, because that box is TOML."}
    tok, repo, branch = conf

    try:
        import requests
        who = requests.get("%s/user" % _API, headers=_headers(tok), timeout=15)
        if who.status_code == 401:
            return {"ok": False, "detail":
                    "GitHub rejected the token (401). It has been revoked, or it expired, "
                    "or part of it was lost in the paste."}
        r = requests.get("%s/repos/%s" % (_API, repo), headers=_headers(tok), timeout=15)
        if r.status_code == 404:
            return {"ok": False, "detail":
                    "The token cannot see %s. A fine-grained token has to name this "
                    "repository under Repository access." % repo}
    except Exception as exc:
        return {"ok": False, "detail": "Could not reach GitHub: %s" % exc}

    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if not write(PROBE_PATH, {"checked_at": stamp, "branch": branch},
                 "connection check: %s" % stamp):
        return {"ok": False, "detail":
                "The token reaches %s but cannot write to it. It needs Contents: read and "
                "write, not just read." % repo}

    # Read it back over the wire, ignoring what we just cached. Deliberately NOT
    # comparing the timestamp: GitHub's CDN can still be serving the previous
    # body for another minute, and the cache-buster does not reliably defeat it
    # (measured, not assumed). A stale-but-present body proves the read path
    # works, which is the only thing a token check can honestly claim. Freshness
    # is the job of the own-write hold in read(), not of this probe.
    invalidate(PROBE_PATH)
    back = read(PROBE_PATH)
    if not back or "checked_at" not in back:
        return {"ok": False, "detail":
                "The write landed but reading it back returned nothing. The token can "
                "write to %s and not read it, which should not be possible \u2014 check "
                "the permissions." % repo}
    return {"ok": True, "detail":
            "Wrote to %s on the %s branch and read it back. Keeper slips, the draw and any "
            "entered picks will survive a reboot." % (repo, branch)}


def invalidate(path: str = None) -> None:
    """Forget everything cached, including our own writes. Used by tests."""
    if path is None:
        _cache.clear()
        _own.clear()
    else:
        _cache.pop(path, None)
        _own.pop(path, None)
