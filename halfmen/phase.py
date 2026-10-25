"""What time of year it is, inferred rather than configured.

The home page should lead with whatever is actually useful right now. The
phase is worked out from data the app already pulls - no extra config to
maintain, nothing anyone has to remember to flip in August:

  keepers_open  - a keeper deadline is set and has not passed yet
  pre_draft     - keepers are locked but a configured Sleeper draft is unfinished
  pre_season    - the drafts are done, NFL games have not started
  in_season     - the NFL is in its regular season or postseason
  offseason     - the Sleeper league itself is marked complete

Ported from the Kreeper League, with two changes this league needs: the
keeper deadline is optional here (there isn't one in config yet), and
"pre_draft" looks at every draft in `drafts.sleeper_drafts` rather than the
single `draft_id` Sleeper hands back, because 2026 ran two of them.

Pure logic - no Streamlit in this module.
"""
from __future__ import annotations

import datetime as dt
from typing import List, Optional

from . import config, sleeper

PHASES = ["keepers_open", "pre_draft", "pre_season", "in_season", "offseason"]


def keeper_deadline() -> Optional[dt.datetime]:
    """`league.keeper_deadline` as a tz-aware datetime, or None when unset.

    A naive value is read as wall-clock time in `league.keeper_timezone`
    (default America/Indiana/Indianapolis), so DST is handled for us.
    """
    raw = config.league().get("keeper_deadline")
    if not raw:
        return None
    try:
        d = dt.datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None
    if d.tzinfo is not None:
        return d
    zone = config.league().get("keeper_timezone") or "America/Indiana/Indianapolis"
    try:
        from zoneinfo import ZoneInfo  # py3.9+
        return d.replace(tzinfo=ZoneInfo(zone))
    except Exception:  # noqa: BLE001 - a bad zone name shouldn't lose the deadline
        return d.astimezone()


def draft_ids() -> List[str]:
    """Every configured Sleeper draft for this season, in config order."""
    out: List[str] = []
    for ids in (config.drafts().get("sleeper_drafts") or {}).values():
        out.extend(str(i) for i in (ids or []))
    return out


def current_phase(league_id: Optional[str] = None) -> str:
    league_id = league_id or config.league_id()

    deadline = keeper_deadline()
    if deadline is not None and dt.datetime.now(deadline.tzinfo) < deadline:
        return "keepers_open"

    try:
        lg = sleeper.get_league(league_id) or {}
    except Exception:  # noqa: BLE001 - a flaky Sleeper call must not crash the home page
        lg = {}
    if lg.get("status") == "complete":
        return "offseason"

    ids = draft_ids() or ([str(lg["draft_id"])] if lg.get("draft_id") else [])
    for did in ids:
        try:
            if (sleeper.get_draft(did) or {}).get("status") != "complete":
                return "pre_draft"
        except Exception:  # noqa: BLE001
            return "pre_draft"

    try:
        season_type = (sleeper.nfl_state() or {}).get("season_type")
    except Exception:  # noqa: BLE001
        season_type = None
    if season_type in ("regular", "post"):
        return "in_season"
    return "pre_season"
