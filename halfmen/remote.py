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
import json
import time
from typing import Any, Dict, Optional, Tuple

_API = "https://api.github.com"
_TTL = 5.0          # seconds; the draw reveal has to feel live to a room
_cache: Dict[str, Tuple[float, Any]] = {}


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
                     headers=_headers(tok), params={"ref": branch}, timeout=15)
    if r.status_code == 404:
        return None, None
    r.raise_for_status()
    j = r.json()
    body = base64.b64decode(j["content"]).decode()
    return (json.loads(body) if body.strip() else None), j["sha"]


def read(path: str) -> Optional[dict]:
    """Cached read. None means "nothing there" AND "could not tell" - both of
    which the caller handles the same way: use the local copy."""
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
                _cache[path] = (time.time(), data)
                return True
            if r.status_code != 409:   # not a sha conflict, so retrying won't help
                return False
    except Exception:
        return False
    return False


def invalidate(path: str = None) -> None:
    if path is None:
        _cache.clear()
    else:
        _cache.pop(path, None)
