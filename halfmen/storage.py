"""Where submitted keeper slips live.

A JSON file per season under data/. Deliberately boring: the slip is eight
managers times five players once a year, so there is nothing to be gained from
a database. The one thing that matters is that a slip, once locked, is a record
- so writes are atomic and the previous file is kept as `.bak`.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List

from . import config


def _path(season: int):
    return config.DATA_DIR / ("keepers_%d.json" % int(season))


def load(season: int = None) -> Dict[str, Any]:
    season = int(season or config.season())
    p = _path(season)
    if not p.exists():
        return {"season": season, "teams": {}, "kept": [], "rookie_kept": [], "locked": False}
    try:
        return json.loads(p.read_text())
    except ValueError:
        return {"season": season, "teams": {}, "kept": [], "rookie_kept": [], "locked": False}


def save(data: Dict[str, Any], season: int = None) -> None:
    season = int(season or data.get("season") or config.season())
    config.DATA_DIR.mkdir(exist_ok=True)
    p = _path(season)
    if p.exists():
        p.with_suffix(".json.bak").write_text(p.read_text())
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    os.replace(str(tmp), str(p))


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
