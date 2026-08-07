"""Where submitted keeper slips, the draw and any recorded picks live.

One JSON blob per season. Deliberately boring: the slip is eight managers times
five players once a year, so there is nothing to be gained from a database. The
one thing that matters is that a slip, once locked, is a record - so writes are
atomic and the previous file is kept as `.bak`.

The blob is written to BOTH a local file and, when a GitHub token is configured,
a data branch of this app's own repo. On Streamlit Cloud the local file is
scratch that the next reboot deletes; the branch is the copy that survives. See
remote.py. With no token nothing changes and this is just a file.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List

from . import config, remote


def _path(season: int):
    return config.DATA_DIR / ("keepers_%d.json" % int(season))


def _remote_path(season: int) -> str:
    return "data/keepers_%d.json" % int(season)


def _blank(season: int) -> Dict[str, Any]:
    return {"season": season, "teams": {}, "kept": [], "rookie_kept": [], "locked": False}


def load(season: int = None) -> Dict[str, Any]:
    season = int(season or config.season())
    if remote.enabled():
        got = remote.read(_remote_path(season))
        if got:
            return got
        # Nothing on the branch yet, or GitHub is unreachable. Either way the
        # local copy is the best answer we have; a write will push it up.
    p = _path(season)
    if not p.exists():
        return _blank(season)
    try:
        return json.loads(p.read_text())
    except ValueError:
        return _blank(season)


def save(data: Dict[str, Any], season: int = None) -> None:
    season = int(season or data.get("season") or config.season())
    # Local first and always: it is the fallback if the push fails, and on a
    # laptop it is the only copy.
    config.DATA_DIR.mkdir(exist_ok=True)
    p = _path(season)
    if p.exists():
        p.with_suffix(".json.bak").write_text(p.read_text())
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    os.replace(str(tmp), str(p))
    if remote.enabled():
        remote.write(_remote_path(season), data, "league data: %d" % season)


def submit(owner_id: str, entries: List[Dict[str, Any]], season: int = None) -> Dict[str, Any]:
    """`entries` is a list of {player_id, kind, round}. Rewrites the flat
    `kept` / `rookie_kept` indexes that history.build reads."""
    data = load(season)
    if data.get("locked"):
        raise RuntimeError("keepers for %s are locked" % data.get("season"))
    data.setdefault("teams", {})[str(owner_id)] = {
        "entries": entries,
        "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _reindex(data)
    save(data, season)
    return data


def _reindex(data: Dict[str, Any]) -> None:
    kept, rookie = [], []
    for team in (data.get("teams") or {}).values():
        for e in team.get("entries") or []:
            pid = str(e.get("player_id"))
            if not pid:
                continue
            kept.append(pid)
            if e.get("kind") == "rookie":
                rookie.append(pid)
    data["kept"] = sorted(set(kept))
    data["rookie_kept"] = sorted(set(rookie))


def entries_for(owner_id: str, season: int = None) -> List[Dict[str, Any]]:
    return ((load(season).get("teams") or {}).get(str(owner_id)) or {}).get("entries") or []


def lock(season: int = None) -> None:
    data = load(season)
    data["locked"] = True
    save(data, season)


# --------------------------------------------------------------------------
# league votes
# --------------------------------------------------------------------------

def votes(season: int = None) -> Dict[str, Dict[str, int]]:
    """item id -> {owner_id: option index}."""
    return dict((load(season) or {}).get("votes") or {})


def record_vote(item: str, owner_id: str, choice: int, season: int = None) -> Dict[str, int]:
    """One manager's answer to one question.

    Goes through remote.mutate rather than load-then-save, because eight people
    voting from a bar at the same moment each hold a copy of the file from before
    the others voted - and a plain write would drop whichever ones landed in
    between. The mutation re-reads inside the retry loop, so a vote is only ever
    added on top of the current file.
    """
    season = int(season or config.season())

    def apply(data):
        data = dict(data or {})
        data.setdefault("season", season)
        v = dict(data.get("votes") or {})
        row = dict(v.get(item) or {})
        row[str(owner_id)] = int(choice)
        v[item] = row
        data["votes"] = v
        return data

    if remote.enabled():
        got = remote.mutate(_remote_path(season), apply, "vote: %s" % item)
        if got is not None:
            # keep the container copy in step so a Cloud restart has something
            config.DATA_DIR.mkdir(exist_ok=True)
            _path(season).write_text(json.dumps(got, indent=2, sort_keys=True))
            return dict(got.get("votes", {}).get(item) or {})

    data = apply(load(season))
    save(data, season)
    return dict(data.get("votes", {}).get(item) or {})


def clear_votes(item: str = None, season: int = None) -> None:
    def apply(data):
        data = dict(data or {})
        if item is None:
            data["votes"] = {}
        else:
            v = dict(data.get("votes") or {})
            v.pop(item, None)
            data["votes"] = v
        return data

    if remote.enabled():
        got = remote.mutate(_remote_path(int(season or config.season())), apply,
                            "clear vote: %s" % (item or "all"))
        if got is not None:
            return
    save(apply(load(season)), season)


# --------------------------------------------------------------------------
# the year-one draw
# --------------------------------------------------------------------------

def save_draw(seed: int, rookie: List[str], veteran: List[str],
              season: int = None) -> Dict[str, Any]:
    """Record the season-one draw so it outlives the browser tab that ran it.

    It was in st.session_state, which is per-browser-session: the commissioner
    would have seen the order and every other manager would have seen "nothing
    drawn yet", and a refresh would have wiped it. The seed is stored alongside
    so anyone can reproduce the same order from scratch and check it.
    """
    data = load(season)
    data["draw"] = {"seed": int(seed), "rookie": list(rookie), "veteran": list(veteran),
                    "drawn_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "reveal": 0}
    save(data, season)
    return data["draw"]


def load_draw(season: int = None) -> Dict[str, Any]:
    return (load(season) or {}).get("draw") or {}


def set_reveal(n: int, season: int = None) -> int:
    """How many selections have been read out so far.

    Kept in the file rather than the session so a manager watching from their
    phone sees the same envelope open at the same moment as the room, which is
    the entire point of doing it live.
    """
    data = load(season)
    if not data.get("draw"):
        return 0
    data["draw"]["reveal"] = max(0, int(n))
    save(data, season)
    return data["draw"]["reveal"]
