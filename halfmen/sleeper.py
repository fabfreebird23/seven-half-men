"""Thin client for Sleeper's public read-only API.

Every read is cached to disk with a stale fallback. That is not just a speed
optimisation: urllib3 on this machine's LibreSSL intermittently hangs on the
league endpoints, and a stale cache is much better than a dashboard that spins.
Pre-warm with `scripts/warm_cache.sh` if a fresh clone stalls.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

import requests

from . import config

BASE = "https://api.sleeper.app/v1"
HEADERS = {"User-Agent": "seven-half-men/1.0 (personal fantasy tool)"}
_PLAYERS_CACHE = config.DATA_DIR / "players_nfl.json"
_PLAYERS_MAX_AGE = 60 * 60 * 24


def _get(path: str) -> Any:
    last = None
    for attempt in range(3):
        try:
            r = requests.get("%s/%s" % (BASE, path), headers=HEADERS, timeout=8)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            last = exc
            if attempt < 2:
                time.sleep(1.0 * (attempt + 1))
    raise last


def _disk(key: str, ttl: int, fetch):
    p = config.DATA_DIR / ("cache_%s.json" % key)
    if p.exists() and (time.time() - p.stat().st_mtime) < ttl:
        try:
            return json.loads(p.read_text())
        except ValueError:
            pass
    try:
        data = fetch()
    except Exception:
        if p.exists():
            return json.loads(p.read_text())
        raise
    config.DATA_DIR.mkdir(exist_ok=True)
    p.write_text(json.dumps(data))
    return data


def get_league(league_id: str) -> Dict[str, Any]:
    return _disk("league_%s" % league_id, 3600, lambda: _get("league/%s" % league_id))


def get_users(league_id: str) -> List[Dict[str, Any]]:
    return _disk("users_%s" % league_id, 3600, lambda: _get("league/%s/users" % league_id))


def get_rosters(league_id: str) -> List[Dict[str, Any]]:
    return _disk("rosters_%s" % league_id, 1800, lambda: _get("league/%s/rosters" % league_id))


def get_traded_picks(league_id: str) -> List[Dict[str, Any]]:
    return _disk("traded_%s" % league_id, 1800,
                 lambda: _get("league/%s/traded_picks" % league_id) or [])


def get_drafts(league_id: str) -> List[Dict[str, Any]]:
    # 5 minutes, not an hour: a draft going live flips `status`, and an hour of
    # the board insisting nothing has started is an hour of people refreshing.
    return _disk("drafts_%s" % league_id, 300,
                 lambda: _get("league/%s/drafts" % league_id) or [])


def get_draft(draft_id: str) -> Dict[str, Any]:
    return _disk("draft_%s" % draft_id, 3600, lambda: _get("draft/%s" % draft_id))


def get_draft_picks(draft_id: str, ttl: int = 900) -> List[Dict[str, Any]]:
    """`ttl` drops to about a minute while a draft is live - fifteen minutes is
    fine for a finished board and useless when somebody is on the clock."""
    return _disk("picks_%s" % draft_id, ttl, lambda: _get("draft/%s/picks" % draft_id) or [])


def get_matchups(league_id: str, week: int) -> List[Dict[str, Any]]:
    return _disk("matchups_%s_%s" % (league_id, week), 1800,
                 lambda: _get("league/%s/matchups/%s" % (league_id, week)) or [])


def get_transactions(league_id: str, week: int) -> List[Dict[str, Any]]:
    return _disk("txns_%s_%s" % (league_id, week), 900,
                 lambda: _get("league/%s/transactions/%s" % (league_id, week)) or [])


def get_winners_bracket(league_id: str) -> List[Dict[str, Any]]:
    return _disk("bracket_%s" % league_id, 86400,
                 lambda: _get("league/%s/winners_bracket" % league_id) or [])


def get_losers_bracket(league_id: str) -> List[Dict[str, Any]]:
    """The Chase for the Pick - same shape as the winners bracket."""
    return _disk("losers_%s" % league_id, 86400,
                 lambda: _get("league/%s/losers_bracket" % league_id) or [])


def get_players() -> Dict[str, Any]:
    """The full NFL player map (~5MB). Refreshed daily at most."""
    config.DATA_DIR.mkdir(exist_ok=True)
    if _PLAYERS_CACHE.exists():
        if (time.time() - _PLAYERS_CACHE.stat().st_mtime) < _PLAYERS_MAX_AGE:
            return json.loads(_PLAYERS_CACHE.read_text())
    try:
        data = _get("players/nfl")
    except Exception:
        if _PLAYERS_CACHE.exists():
            return json.loads(_PLAYERS_CACHE.read_text())
        raise
    _PLAYERS_CACHE.write_text(json.dumps(data))
    return data


def nfl_state() -> Dict[str, Any]:
    """Sleeper's own view of the NFL calendar: current week, and the date of
    the first game. Cached for six hours - it changes once a week at most."""
    return _disk("nfl_state", 21600, lambda: _get("state/nfl"))


def league_chain(league_id: str) -> List[Dict[str, Any]]:
    """Walk previous_league_id back to the first season. Newest first."""
    chain: List[Dict[str, Any]] = []
    lid: Optional[str] = league_id
    seen = set()
    while lid and lid not in ("0", None) and lid not in seen:
        seen.add(lid)
        lg = get_league(lid)
        if not lg:
            break
        chain.append({"season": int(lg["season"]), "league_id": lg["league_id"],
                      "draft_id": lg.get("draft_id"),
                      "previous": lg.get("previous_league_id")})
        lid = lg.get("previous_league_id")
    return chain


def invalidate(league_id: str) -> None:
    """Drop the caches a trade invalidates so the next read is fresh."""
    for key in ("rosters_%s" % league_id, "traded_%s" % league_id):
        p = config.DATA_DIR / ("cache_%s.json" % key)
        if p.exists():
            p.unlink()
