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


def _configured_ids(kind: int) -> List[str]:
    """The draft ids the rulebook says are real, in board order. [] if unset."""
    key = "rookie" if kind == ROOKIE else "veteran"
    got = (config.drafts().get("sleeper_drafts") or {}).get(key) or []
    return [str(x) for x in got]


def _parts_for(kind: int, league_id: str = None) -> List[dict]:
    """Every Sleeper draft that makes up this one draft, in board order.

    A draft can be more than one Sleeper draft. Sleeper fixes the round count
    when a board is created, so a 14-round veteran draft that started life as
    a 10-round board has to finish on a second one - two Sleeper drafts, one
    actual draft, and the rounds continue rather than restart.

    Which ids count is CONFIGURED, not detected. Detecting by player_type
    picked whichever was created last out of five, two of which were never
    used, so the site cheerfully reported a four-round veteran draft.
    """
    try:
        drafts = sleeper.get_drafts(league_id or config.league_id()) or []
    except Exception:
        return []
    want = _configured_ids(kind)
    if want:
        by_id = {str(d.get("draft_id")): d for d in drafts}
        got = [by_id[i] for i in want if i in by_id]
        if got:
            return got
        # Configured, but the league we are looking at has none of them - a
        # different league id, or a test harness. Fall through and detect
        # rather than reporting that the draft does not exist.
    # Nothing configured: fall back to the old behaviour, oldest first so a
    # draft in progress does not jump ahead of the one before it.
    got = [d for d in drafts
           if int((d.get("settings") or {}).get("player_type", VETERAN)) == kind]
    got.sort(key=lambda d: d.get("created") or 0)
    return got[:1]


def _draft_for(kind: int, league_id: str = None) -> Optional[dict]:
    """The FIRST part, for callers that only want the draft's identity."""
    parts = _parts_for(kind, league_id)
    return parts[0] if parts else None


def state(kind: int = ROOKIE, league_id: str = None) -> Dict[str, Any]:
    """Everything the page needs about one draft. {} if there is no such draft.

    `on_clock` is None when the draft has not started or has finished, so a
    caller can tell "nobody is on the clock" from "we could not work it out".
    """
    parts = _parts_for(kind, league_id)
    if not parts:
        return {}
    d = parts[0]
    st = d.get("settings") or {}
    teams = int(st.get("teams") or len(config.managers()))
    # Rounds ADD UP across the parts: two Sleeper boards of 10 and 4 are one
    # 14-round draft, not a 4-round one.
    rounds = sum(int((p.get("settings") or {}).get("rounds") or 0) for p in parts)
    timer = int(st.get("pick_timer") or 0)
    snake = (d.get("type") == "snake")
    # The live one is the last part with anything still to do; otherwise the
    # last part, so `status` reports the end of the draft and not the start.
    tail = parts[-1]

    picks = []
    offset = 0
    for p in parts:
        pr = int((p.get("settings") or {}).get("rounds") or 0)
        try:
            got = sleeper.get_draft_picks(
                p["draft_id"], ttl=60 if p.get("status") == "drafting" else 900) or []
        except Exception:
            got = []
        got = sorted(got, key=lambda x: int(x.get("pick_no") or 0))
        for q in got:
            q = dict(q)
            # Renumber onto the combined board. Without this, round 11 comes
            # back as round 1 and the board draws four picks on top of the
            # first four of round one.
            q["round"] = int(q.get("round") or 0) + offset
            q["pick_no"] = int(q.get("pick_no") or 0) + offset * teams
            picks.append(q)
        offset += pr

    # draft_order maps owner -> slot; we want the slot order.
    order_by_slot = {int(v): str(k) for k, v in (d.get("draft_order") or {}).items()}
    order = [order_by_slot.get(i + 1) for i in range(teams)]

    made = len(picks)
    total = rounds * teams
    # What the LEAGUE is running, which is not always what Sleeper is set to.
    # Sleeper would not accept a two-round rookie draft, so it runs long and
    # gets stopped by hand - the board counts against the rulebook and says when
    # to pause it, because 24 hours a pick makes it very easy to sail past.
    want_rounds = config.rookie_rounds() if kind == ROOKIE else config.veteran_rounds()
    league_total = want_rounds * teams
    over_run = rounds > want_rounds
    on_clock = None
    rnd = pick_in_round = None
    if tail.get("status") == "drafting" and made < total and all(order):
        rnd = made // teams + 1
        i = made % teams
        # A snake reverses the even rounds, so slot and pick number diverge.
        slot_i = (teams - 1 - i) if (snake and rnd % 2 == 0) else i
        on_clock = order[slot_i]
        pick_in_round = i + 1

    deadline = None
    if on_clock and timer:
        last = tail.get("last_picked") or tail.get("start_time")
        if last:
            deadline = last / 1000.0 + timer

    return {
        "draft": d, "parts": parts, "picks": picks, "status": tail.get("status"),
        "rounds": rounds, "teams": teams, "timer": timer, "snake": snake,
        "order": order, "made": made, "total": total,
        "league_total": league_total, "over_run": over_run,
        "voided": max(0, made - league_total) if over_run else 0,
        "stop_now": bool(over_run and made >= league_total),
        "last_before_stop": bool(over_run and made == league_total - 1),
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
    if s["rounds"] and s["rounds"] > want:
        out.append(
            "Sleeper is set to <b>%d rounds</b> (%d picks) and will not stop at %d. This "
            "draft has to be <b>paused by hand</b> after pick %d. Everything past that is "
            "not a pick in this league &mdash; the boards here ignore it." % (
                s["rounds"], s["rounds"] * s["teams"], want, s["league_total"]))
    elif s["rounds"] and s["rounds"] < want:
        out.append(
            "Sleeper is set to <b>%d rounds</b>; the rulebook says <b>%d</b>." % (
                s["rounds"], want))
    return out


def _drawn_order(kind: int) -> List[str]:
    """The order the drum drew. This is a SELECTION order - who chooses a slot
    first - and is deliberately NOT compared against Sleeper's board order.
    First choice takes any spot they want, so the two are expected to differ;
    flagging that as a disagreement would cry wolf on the rules working."""
    from . import storage
    try:
        draw = storage.load_draw() or {}
    except Exception:
        return []
    return list(draw.get("rookie" if kind == ROOKIE else "veteran") or [])


def slots_chosen(s: Dict[str, Any], kind: int = ROOKIE) -> List[tuple]:
    """(slot, owner, where they came in the drum) once Sleeper has a board.

    The interesting column is the third one: it shows what each manager did with
    their pick of the board, which is the only record of it anywhere.
    """
    order = s.get("order") or []
    if not order or not all(order):
        return []
    drawn = [str(o) for o in _drawn_order(kind)]
    out = []
    for i, owner in enumerate(order):
        pos = drawn.index(str(owner)) + 1 if str(owner) in drawn else None
        out.append((i + 1, str(owner), pos))
    return out


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


def rows(s: Dict[str, Any], pmap: Dict[str, Any] = None, counted_only: bool = True) -> List[dict]:
    """Picks made so far, newest first - which is the order you want when the
    draft has been running for a week.

    `counted_only` drops anything past the rulebook's round count. Sleeper will
    keep taking picks after the league's draft is over, and showing those as
    real would put players on rosters nobody agreed to.
    """
    pmap = pmap if pmap is not None else {}
    cap = s.get("league_total") if counted_only else None
    out = []
    for p in reversed(s.get("picks") or []):
        if cap and int(p.get("pick_no") or 0) > cap:
            continue
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
