"""The draft while it is actually happening.

A 24-hour pick clock means the draft is a fortnight-long background event, not
an evening. Nobody is going to sit on Sleeper watching it, so the board here has
to answer the two questions people will open their phone for: whose pick is it,
and how long have they got.

It also checks Sleeper against the rulebook. The two can disagree - the rookie
draft went live configured for 16 ROUNDS rather than 16 picks, which at a day a
pick is 128 days instead of 16 - and a board that quietly rendered the league's
intention while Sleeper ran something else would hide exactly the mistake worth
catching.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from . import config, sleeper

ROOKIE = 1          # Sleeper's player_type for a rookie-only draft
VETERAN = 0


def _draft_for(kind: int, league_id: str = None) -> Optional[dict]:
    try:
        drafts = sleeper.get_drafts(league_id or config.league_id()) or []
    except Exception:
        return []
    for d in drafts:
        if int((d.get("settings") or {}).get("player_type", VETERAN)) == kind:
            return d
    return None


def state(kind: int = ROOKIE, league_id: str = None) -> Dict[str, Any]:
    """Everything the page needs about one draft. {} if there is no such draft.

    `on_clock` is None when the draft has not started or has finished, so a
    caller can tell "nobody is on the clock" from "we could not work it out".
    """
    d = _draft_for(kind, league_id)
    if not d:
        return {}
    st = d.get("settings") or {}
    teams = int(st.get("teams") or len(config.managers()))
    rounds = int(st.get("rounds") or 0)
    timer = int(st.get("pick_timer") or 0)
    snake = (d.get("type") == "snake")

    try:
        picks = sleeper.get_draft_picks(d["draft_id"], ttl=60 if d.get("status") == "drafting"
                                        else 900) or []
    except Exception:
        picks = []

    # draft_order maps owner -> slot; we want the slot order.
    order_by_slot = {int(v): str(k) for k, v in (d.get("draft_order") or {}).items()}
    order = [order_by_slot.get(i + 1) for i in range(teams)]

    made = len(picks)
    total = rounds * teams
    on_clock = None
    rnd = pick_in_round = None
    if d.get("status") == "drafting" and made < total and all(order):
        rnd = made // teams + 1
        i = made % teams
        # A snake reverses the even rounds, so slot and pick number diverge.
        slot_i = (teams - 1 - i) if (snake and rnd % 2 == 0) else i
        on_clock = order[slot_i]
        pick_in_round = i + 1

    deadline = None
    if on_clock and timer:
        last = d.get("last_picked") or d.get("start_time")
        if last:
            deadline = last / 1000.0 + timer

    return {
        "draft": d, "picks": picks, "status": d.get("status"),
        "rounds": rounds, "teams": teams, "timer": timer, "snake": snake,
        "order": order, "made": made, "total": total,
        "on_clock": on_clock, "round": rnd, "pick": pick_in_round,
        "deadline": deadline,
    }


def disagreements(s: Dict[str, Any], kind: int = ROOKIE) -> List[str]:
    """Where Sleeper and the rulebook do not match.

    Sleeper is what the league actually drafts on, so it wins - but silently
    following it would hide a setting nobody meant to choose. Named, not
    corrected.
    """
    if not s:
        return []
    out = []
    want = config.rookie_rounds() if kind == ROOKIE else config.veteran_rounds()
    if s["rounds"] and s["rounds"] != want:
        out.append(
            "Sleeper is set to <b>%d rounds</b> (%d picks); the rulebook says <b>%d</b> "
            "(%d picks)." % (s["rounds"], s["rounds"] * s["teams"], want, want * s["teams"]))
    drawn = _drawn_order(kind)
    if drawn and all(s["order"]) and [str(o) for o in drawn] != [str(o) for o in s["order"]]:
        out.append("Sleeper's draft order is <b>not the order the drum drew</b>. "
                   "Sleeper is what you are actually drafting on.")
    return out


def _drawn_order(kind: int) -> List[str]:
    from . import storage
    try:
        draw = storage.load_draw() or {}
    except Exception:
        return []
    return list(draw.get("rookie" if kind == ROOKIE else "veteran") or [])


def countdown(deadline: float, now: float = None) -> str:
    """'6h 12m left', or 'expired' once it is past. Rendered server-side on each
    rerun rather than ticking - it is a 24-hour clock, not a shot clock."""
    if not deadline:
        return ""
    left = int(deadline - (now if now is not None else time.time()))
    if left <= 0:
        return "on the clock past the deadline"
    d, rem = divmod(left, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return "%dd %dh left" % (d, h)
    if h:
        return "%dh %02dm left" % (h, m)
    return "%dm left" % m


def rows(s: Dict[str, Any], pmap: Dict[str, Any] = None) -> List[dict]:
    """Picks made so far, newest first - which is the order you want when the
    draft has been running for a week."""
    pmap = pmap if pmap is not None else {}
    out = []
    for p in reversed(s.get("picks") or []):
        md = p.get("metadata") or {}
        name = (" ".join(x for x in (md.get("first_name"), md.get("last_name")) if x)).strip()
        if not name:
            meta = pmap.get(str(p.get("player_id"))) or {}
            name = meta.get("full_name") or str(p.get("player_id"))
        out.append({
            "round": p.get("round"), "pick": p.get("draft_slot"),
            "overall": p.get("pick_no"), "name": name,
            "position": md.get("position") or "", "team": md.get("team") or "",
            "owner_id": str(p.get("picked_by") or ""),
        })
    return out
