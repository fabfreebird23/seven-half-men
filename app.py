"""7 1/2 Men - keeper dashboard.

Six sections: Home, Keepers, Taxi Bay, The Pot, Draft, Lottery.

The league starts in 2026 with empty rosters and no keepers, so most screens
have two modes: a "season one" state that shows the rule and what it will do,
and the live state once there is data behind it. The engine underneath is the
full ruleset either way - nothing here is stubbed for year one.
"""
from __future__ import annotations

import hashlib
import html
from pathlib import Path
import json
import time
from collections import Counter
from typing import Dict, List

import re
import streamlit as st
import streamlit.components.v1 as components

def _fresh_halfmen() -> None:
    """Drop stale halfmen.* modules after a deploy, so a push never needs a
    Reboot. Streamlit re-executes THIS file every run, but imported modules
    stay in sys.modules for the life of the process — and Streamlit Cloud
    keeps the process across a push, so new app code ran against last
    deploy's modules (theme.fingerprint exists to diagnose exactly that).
    Fingerprint the package (size + mtime per file); if the loaded copy was
    built from different files, or predates this guard, forget every halfmen
    module so the imports below load fresh. Plain reruns keep them. Same fix
    as the Kreeper, B&B and Draft Room apps."""
    import hashlib
    import sys
    # The test suite runs this file with halfmen modules it has patched;
    # dropping them would throw the patches away.
    if "pytest" in sys.modules:
        return
    root = Path(__file__).resolve().parent / "halfmen"
    h = hashlib.sha1()
    for f in sorted(root.rglob("*.py")):
        try:
            st_ = f.stat()
        except OSError:
            continue
        h.update(f"{f.relative_to(root)}:{st_.st_size}:{st_.st_mtime_ns}".encode())
    fp = h.hexdigest()
    loaded = sys.modules.get("halfmen")
    if loaded is not None and getattr(loaded, "_fingerprint", None) != fp:
        for name in [m for m in sys.modules if m == "halfmen" or m.startswith("halfmen.")]:
            del sys.modules[name]
    import halfmen
    halfmen._fingerprint = fp


_fresh_halfmen()

from halfmen import (adp_board, agenda, config, draftboard, engine, history, lottery,
                     live, minutes, voice, phase, playoffs, playoffs_view, recap,
                     gameday, picks, pot, remote, rulebook, season, sleeper, stakes, storage,
                     taxi, theme, valueboard)

st.set_page_config(page_title="7½ Men", page_icon="🏈", layout="wide")

LG = config.league_id()
SEASON = config.season()
DEFAULT_VIEW = config.me()


def _viewer() -> str:
    """Whose team the 'your' views show.

    Lives in the query string rather than session state so a manager can
    bookmark their own team and land on it, and so a link shared in the group
    chat opens on whatever the sender was looking at.
    """
    want = st.query_params.get("team")
    want = str(want[0] if isinstance(want, list) else want or "")
    return want if want in config.managers() else DEFAULT_VIEW
FIRST = config.is_first_season()
# The full season a manager can spend FAAB across: regular season plus the
# Chase bracket, since the bracket teams are still making claims.
WEEKS = int(config.league()["regular_season_weeks"]) + len(config.league()["chase_weeks"])


def draw_unlocked() -> bool:
    """Whether this browser may operate the draw.

    Only the controls are gated. Everyone else still sees the board, the hat and
    each envelope as it opens - which is the point of running it live - they
    just cannot re-draw it or rewind the reveal from their phone.

    Session-only on purpose: re-drawing the lottery is destructive, so that one
    should not survive a link being pasted into the group chat. The draft room
    uses `room_unlocked` instead, which does.
    """
    if not config.draw_password():
        return True
    return bool(st.session_state.get("draw_unlocked"))


def room_token() -> str:
    """A short stand-in for the password, safe to carry in a URL."""
    pw = config.draw_password()
    return hashlib.sha1(("room:" + pw).encode()).hexdigest()[:10] if pw else ""


def room_unlocked() -> bool:
    """Whether this browser may enter picks.

    The draft room is the one place the unlock has to survive a full page load:
    voice navigates the page to hand its transcript back, and a new page is a
    new Streamlit session with an empty session_state - so a session-only flag
    asked for the password after every single spoken pick.

    So the room carries a token in the URL instead. It is a hash rather than the
    password, but be clear about what that buys: anyone with the link can run
    the board. That is the same speed bump as before, except it now travels, and
    it deliberately does NOT unlock the lottery draw.
    """
    if not config.draw_password():
        return True
    if st.session_state.get("room_unlocked"):
        return True
    return _qp("k") == room_token()


def room_lock_ui() -> bool:
    if room_unlocked():
        return True
    c1, c2 = st.columns([2, 3])
    with c1:
        pw = st.text_input("Commissioner", type="password",
                           placeholder="password to run the board",
                           label_visibility="collapsed", key="room_pw")
        if pw:
            if pw == config.draw_password():
                st.session_state["room_unlocked"] = True
                st.query_params["k"] = room_token()
                st.rerun()
            else:
                st.markdown('<div class="tiny" style="color:var(--bad)">Not that one.</div>',
                            unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="tiny">Watching only. The board fills in here for everybody as '
                    'picks go in &mdash; you just cannot enter them.</div>',
                    unsafe_allow_html=True)
    return False


def draw_lock_ui(placeholder: str = "password to run the draw",
                 note: str = ("Watching only. The board and every envelope update here as the "
                              "commissioner opens them &mdash; you just cannot re-draw or "
                              "rewind it.")) -> bool:
    """Renders the unlock control and returns whether we are unlocked."""
    if draw_unlocked():
        return True
    c1, c2 = st.columns([2, 3])
    with c1:
        pw = st.text_input("Commissioner", type="password",
                           placeholder=placeholder,
                           label_visibility="collapsed", key="draw_pw")
        if pw:
            if pw == config.draw_password():
                st.session_state["draw_unlocked"] = True
                st.rerun()
            else:
                st.markdown('<div class="tiny" style="color:var(--bad)">Not that one.</div>',
                            unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="tiny">%s</div>' % note, unsafe_allow_html=True)
    return False


def storage_note(check: bool = False) -> None:
    """Whether what you are about to type in will still be here tomorrow.

    Streamlit Cloud deletes the container's disk on every reboot, so this is not
    a detail worth hiding. `check` adds a button that actually tries it, because
    a token can be present and expired, present and scoped to the wrong
    repository, or the whole secrets file can have failed to parse - and none of
    those are visible from config alone.
    """
    if remote.enabled():
        st.markdown('<div class="tiny" style="margin-top:8px">Saved to the league data '
                    'branch &mdash; this survives a reboot or a redeploy.</div>',
                    unsafe_allow_html=True)
    else:
        st.markdown('<div class="tiny" style="margin-top:8px;color:var(--warn)">Saved to '
                    'this container only. Set <code>github_token</code> in the app secrets '
                    'to make it durable &mdash; otherwise a Streamlit reboot wipes it.</div>',
                    unsafe_allow_html=True)
    if not check:
        return
    if st.button("Test the connection", key="probe_%s" % st.session_state.get("_probe_n", 0)):
        # Streamlit Cloud can re-run app.py while keeping an already-imported
        # module in memory, so new code calls into an old module. This button is
        # the one people press when something is ALREADY wrong; it must not add
        # a red traceback to the pile. Name the condition instead.
        run = getattr(remote, "probe", None)
        if run is None:
            st.markdown(
                '<div class="banner" style="margin-top:8px;border-color:var(--warn);'
                'color:var(--warn)"><b>The app is running old code.</b> Streamlit Cloud '
                're-ran this page against a stale copy of the storage module. Reboot app '
                'from the Cloud menu &mdash; the storage itself is fine, this check just '
                'is not there yet.</div>', unsafe_allow_html=True)
            return
        with st.spinner("Writing to the data branch and reading it back\u2026"):
            got = run()
        st.markdown(
            '<div class="banner" style="margin-top:8px;border-color:%s;color:%s">'
            '<b>%s</b> %s</div>' % (
                "var(--acc)" if got["ok"] else "var(--bad)",
                "var(--ink)" if got["ok"] else "var(--bad)",
                "Durable." if got["ok"] else "Not durable.", esc(got["detail"])),
            unsafe_allow_html=True)


def first_draw() -> dict:
    """The season-one draw, from disk. Falls back to this session only if the
    file is unreadable, so every manager sees the same order rather than only
    whoever pressed the button."""
    try:
        saved = storage.load_draw(SEASON)
    except Exception:
        saved = {}
    return saved or st.session_state.get("first_draw") or {}


def submitted_keepers() -> dict:
    """owner_id -> [{"round", "name", "kind"}]. Empty until the first slip is
    submitted, which is a year away - the draft board and the capital strip both
    have to render sensibly against nothing."""
    try:
        teams = (storage.load(SEASON) or {}).get("teams") or {}
    except Exception:
        return {}
    out = {}
    for owner, blob in teams.items():
        rows = []
        for e in (blob or {}).get("entries") or []:
            if e.get("round"):
                rows.append({"round": int(e["round"]), "name": e.get("name") or "",
                             "kind": e.get("kind") or "keeper"})
        if rows:
            out[str(owner)] = rows
    return out


# ---------------------------------------------------------------------------
# data loading (cached; every Sleeper read is disk-cached underneath too)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=900, show_spinner=False)
def league_state() -> dict:
    lg = sleeper.get_league(LG)
    rosters = sleeper.get_rosters(LG)
    users = sleeper.get_users(LG)
    drafts = sleeper.get_drafts(LG)
    return {"league": lg, "rosters": rosters, "users": users, "drafts": drafts}


@st.cache_data(ttl=3600, show_spinner=False)
def players_map() -> dict:
    try:
        return sleeper.get_players()
    except Exception:
        return {}


def player_data_warning() -> None:
    """Say so when the player map is missing, rather than degrading quietly.

    It is a 15MB file, gitignored because it has no business in the repo, so a
    fresh container has to fetch the whole thing from Sleeper before anything
    that needs a position, a team or an age can work. Nearly every board here
    depends on it, and every one of them swallows the failure and carries on
    with an empty dict - which is how three managers came to be accused of
    stashing illegal players when the only thing wrong was a slow download.
    """
    if players_map():
        return
    st.markdown(
        '<div class="banner" style="border-color:var(--warn)"><b>Player data is still '
        'loading.</b> The full NFL player file is ~15MB and this container has not finished '
        'fetching it from Sleeper. Positions, ages and anything derived from them will be '
        'blank or missing until it lands &mdash; give it a moment and refresh. Nothing is '
        'broken and nothing you see is a rule.</div>', unsafe_allow_html=True)


@st.cache_data(ttl=1800, show_spinner=False)
def owned_map() -> Dict[str, Counter]:
    try:
        return draftboard.owned_rounds(LG, SEASON)
    except Exception:
        rounds = config.veteran_rounds()
        return {o: Counter({r: 1 for r in range(1, rounds + 1)}) for o in config.managers()}


@st.cache_data(ttl=900, show_spinner=False)
def _value_data():
    try:
        rows = valueboard.rows(LG, SEASON)
    except Exception:
        rows = []
    return rows, engine.value_curve()


def value_rows() -> List[dict]:
    """Every rostered player, priced. Cheap to call before the draft - the
    module bails on an empty league before touching the 5MB player map.

    Also (re)installs the keeper-value curve rows() built. The rows come out of
    Streamlit's cache, which skips rows() entirely - so without this, a fresh
    process (or reloaded engine) would price every other screen in rounds."""
    rows, curve = _value_data()
    engine.set_value_curve(curve)
    return rows


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def ordinal(n: int) -> str:
    n = int(n)
    if 11 <= (n % 100) <= 13:
        return "%dth" % n
    return "%d%s" % (n, {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))


def owner_ids() -> List[str]:
    return list(config.managers().keys())


def who(owner_id: str) -> str:
    return config.manager_name(owner_id)


def team_of(owner_id: str) -> str:
    return config.team_name(owner_id)


# ---------------------------------------------------------------------------
# chrome
# ---------------------------------------------------------------------------

state = league_state()
lg = state["league"] or {}

# No sidebar and one theme: the masthead sits alone at the top, the way the
# Floodlight mock has it.
theme.inject()

# The masthead is a full-bleed band now, so it cannot live inside a column -
# a column would clip it to three fifths of the page and leave the band
# stopping in mid-air.
VIEW = _viewer()


def _initials(owner_id: str) -> str:
    parts = who(owner_id).split()
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else parts[0][1:2])).upper() if parts else "?"


@st.cache_data(show_spinner=False)
def _mgr_photo(owner, tone: str = ""):
    """A manager's photo as a data URI, or None when there isn't one.

    assets/managers/<sleeper id>.jpg is the natural-colour shot the circles
    use. `_g` and `_r` are background-free cutouts (transparent WebP) that
    sit straight on a coloured band: _g for the side being looked at, _r for
    the opponent. Ported from the Kreeper League - the photos are the one
    thing in this port that can't be written, only taken.
    """
    import base64
    ext, mime = ("webp", "image/webp") if tone else ("jpg", "image/jpeg")
    f = Path(__file__).parent / "assets" / "managers" / f"{owner}{'_' + tone if tone else ''}.{ext}"
    return f"data:{mime};base64," + base64.b64encode(f.read_bytes()).decode() if f.exists() else None


def _mgr_face(owner, cls: str = "") -> str:
    """The manager's circle: their photo, or their initials until there is one."""
    src = _mgr_photo(str(owner)) if owner else None
    inner = f'<img src="{src}" alt="">' if src else _initials(owner) if owner else "?"
    return f'<i class="mf{" " + cls if cls else ""}{"" if src else " ini"}">{inner}</i>'


def _first(owner) -> str:
    return (who(owner).split() or ["?"])[0]


# Whose phone it is: a chip on the masthead opens a team dropdown (built into
# the bottom bar's sheets, see _me_popover). The choice rides in ?team= on
# every link, and the browser remembers it so a bookmark or a fresh tab comes
# back to the same team (render_bottom_bar). Replaces the "Viewing as" select
# that sat under the masthead.
theme.masthead("%d \u00b7 %s" % (SEASON, "season one" if FIRST else "offseason"),
               '<span class="mechip" role="button" data-toggle="bb-pop-me">'
               '<span class="av">%s</span>%s <i>&#9662;</i></span>' % (
                   _initials(VIEW), esc(team_of(VIEW))))

# ---------------------------------------------------------------------------
# navigation
#
# Grouped by season PHASE rather than by content type, and routed entirely
# through ?p=&g=&t= so the bottom bar can deep-link to a leaf instead of
# dropping you at the top of a page and making you scroll past three other
# sections. Same shape the Kreeper and Babies & Boomer apps converged on.
# ---------------------------------------------------------------------------

GROUPS = {
    # No group headings in season: three destinations do not need sorting into
    # categories, and "The Wire" under a heading reading "The Wire" is noise.
    "inseason": [
        # "2027 Keepers" lived here and was the slip again - same question, a
        # second engine answering it. One page now: Offseason > Set my keepers.
        ("week", "This Week", [("live", "Live"), ("matchup", "Matchup")]),
        ("wire", "The League", [("wire", "The Wire")]),
        ("taxi", "", [("taxi", "Taxi")]),
        ("pot", "", [("pot", "The Pot")]),
        ("playoffs", "", [("playoffs", "Playoffs"), ("chase", "The Chase")]),
        # The record book has nothing behind it in season one - it would be
        # this season's standings again - so until a season has finished it
        # is folded into Managers and the leaf stays out of the bar.
        ("league", "People &amp; history", [("managers", "Managers")]
         + ([] if FIRST else [("record", "Record book")])
         + [("trades", "Trades"), ("analyzer", "Trade analyzer"), ("superlatives", "Superlatives")]),
    ],
    # Everything here is dormant between February and August. It sat FIRST and
    # held eight of eleven leaves while the season it belongs to was already
    # over, which put the four months of the year anyone actually opens this
    # app behind the eight pages nobody needs until next spring.
    "offseason": [
        ("keepers", "Keepers", [("matrix", "What a keeper costs"),
                                ("slip", "Set my keepers")]),
        # The rookie draft retires with the one-board draft in 2027; its page
        # goes with it once the 2026 season does.
        ("draft", "Draft", [("room", "Draft room")]
         + ([("rookie", "Rookie draft")] if FIRST else [])
         + [("capital", "Draft capital")]),
        ("lottery", "Lottery", [("drums", "The drum"),
                                ("sim", "Simulate")]),
    ],
}

# Leaves that used to exist, and where their content lives now. Links get pasted
# into the group chat and bookmarked, so a route that quietly rendered nothing
# would be a broken link with no error - the worst kind.
MOVED = {
    ("wire", "value"): ("inseason", "wire", "wire"),
    ("wire", "cheap"): ("inseason", "wire", "wire"),
    ("pot", "burn"): ("inseason", "pot", "pot"),
    ("pot", "settle"): ("inseason", "pot", "pot"),
    ("keepers", "franchise"): ("offseason", "keepers", "slip"),
    ("draft", "locks"): ("offseason", "keepers", "matrix"),
    ("draft", "enter"): ("offseason", "draft", "rookie"),
    # The room IS the veteran draft now - it is the live board and the record.
    # A second, read-only grid of the same thing was two boards showing one
    # draft, only one of which was real.
    ("draft", "board"): ("offseason", "draft", "room"),
    # The taxi bay and the in-season taxi page were two views of one squad -
    # the bay had "Every bay" and "Taxi compliance" before the in-season page
    # was built with the same two tables on it. One page now, in the section
    # where a taxi decision actually gets made.
    ("young", "bay"): ("inseason", "taxi", "taxi"),
    ("young", "compliance"): ("inseason", "taxi", "taxi"),
    # These two were duplicates of the rulebook, word for word.
    ("young", "counts"): ("rules", None, None),
    ("lottery", "guards"): ("rules", None, None),
    # 2027 Keepers was the slip, priced by a second engine. It is the slip now.
    ("week", "keepers"): ("offseason", "keepers", "slip"),
}
if FIRST:
    MOVED[("league", "record")] = ("inseason", "league", "managers")
SECTIONS = [("home", "Home"), ("inseason", "In-Season"),
            ("offseason", "Offseason"), ("rules", "Rules")]


def _qp(key: str, default: str = "") -> str:
    v = st.query_params.get(key)
    return str(v[0] if isinstance(v, list) else (v or default))


PAGE = _qp("p", "home")
# The section was called "preseason" until the season started and every page
# in it went dormant. Old links carry it, so it redirects rather than falling
# back to Home and losing whichever leaf someone actually wanted.
if PAGE == "preseason":
    PAGE = "offseason"
    st.query_params["p"] = PAGE
if PAGE not in dict(SECTIONS):
    PAGE = "home"

# A retired route silently falling back to the first leaf of its group would
# send someone who clicked "the guardrails" to the drums with no explanation.
# Send them where the content actually went instead.
_moved = MOVED.get((_qp("g"), _qp("t")))
if _moved and PAGE in GROUPS:
    _team, _key = _qp("team"), _qp("k")
    PAGE, _g, _t = _moved
    st.query_params.clear()
    st.query_params["p"] = PAGE
    if _g:
        st.query_params["g"] = _g
        st.query_params["t"] = _t
    if _team:                     # a redirect must not change who you are
        st.query_params["team"] = _team
    if _key:                      # nor lock you out of the board mid-draft
        st.query_params["k"] = _key

GROUP = LEAF = None
if PAGE in GROUPS:
    groups = GROUPS[PAGE]
    GROUP = _qp("g", groups[0][0])
    if GROUP not in dict((g[0], g) for g in groups):
        GROUP = groups[0][0]
    leaves = dict((g[0], g[2]) for g in groups)[GROUP]
    LEAF = _qp("t", leaves[0][0])
    if LEAF not in dict(leaves):
        LEAF = leaves[0][0]


# ---------------------------------------------------------------------------
# shared pieces
# ---------------------------------------------------------------------------

def glance(cards: List[dict]) -> None:
    """A row of liquid bowls. Label and value live inside the bowl, the sentence
    that explains them sits underneath."""
    cells = "".join(
        '<div class="gl">%s<div class="s">%s</div></div>' % (
            theme.liquid(c["pct"], c["color"], c["big"], c.get("label", "")),
            c.get("note", ""))
        for c in cards)
    st.markdown('<div class="glance">%s</div>' % cells, unsafe_allow_html=True)


def contract_card(p) -> str:
    """One player's clock and price.

    The left rail encodes state rather than decorating: red for a player at the
    wall, gold for a franchise tag, lime for a keeper carrying real surplus.
    """
    sur = p.surplus
    rail = ("wall" if not p.eligible else
            "fr" if p.kind == "franchise" else
            "pick" if (sur or 0) >= 3 else "")

    chips = []
    if p.kind == "rookie":
        chips.append('<span class="chip mag">Rookie keeper</span>')
    elif p.kind == "franchise":
        chips.append('<span class="chip solid">Franchise</span>')
    elif not p.eligible:
        chips.append('<span class="chip bad">Year %d &mdash; wall</span>' % p.year)
    else:
        chips.append('<span class="chip">Year %d of %d</span>' % (
            p.year, int(config.keeper_rules()["max_years"])))
    if p.from_rookie_draft:
        chips.append('<span class="chip acc">Rookie-draft R%d</span>' % engine.rookie_draft_premium())
    if p.adp_round:
        chips.append('<span class="chip">%d ADP R%d</span>' % (config.season() + 1, p.adp_round))
    if p.bumped:
        chips.append('<span class="chip warn">Bumped from R%d</span>' % p.base_round)
    if sur is not None:
        chips.append('<span class="chip %s">%s keeper value</span>' % (
            "good" if sur > 0 else "bad" if sur < 0 else "", theme.signed(sur)))

    price = ('<div class="rd">R%d</div><div class="sub">cost</div>' % p.final_round
             if p.final_round else '<div class="rd">&mdash;</div><div class="sub">no price</div>')

    face = ('<img class="cface" src="https://sleepercdn.com/content/nfl/players/thumb/%s.jpg" alt="" '
            'onerror="this.style.visibility=\'hidden\'">' % esc(p.player_id)) if getattr(p, "player_id", None) else ""
    return ('<div class="contract %s">' + face + '<div class="who">'
            '<div class="nm">%s</div><div class="meta">%s</div>'
            '<div style="margin-top:9px">%s</div>'
            '<div class="tags2">%s</div>%s</div>'
            '<div class="price">%s</div></div>') % (
        rail, esc(p.name), esc(p.position),
        theme.pips(p.year, franchise=(p.kind == "franchise"), rookie=(p.kind == "rookie")),
        "".join(chips),
        ('<div class="tiny" style="margin-top:8px">%s</div>' % esc(p.reason)) if p.reason else "",
        price)


def ledger_table(headers: List[str], rows: List[List[str]], me_row: int = None) -> None:
    head = "".join("<th>%s</th>" % h for h in headers)
    body = ""
    for i, r in enumerate(rows):
        cls = ' class="me"' if me_row is not None and i == me_row else ""
        body += "<tr%s>%s</tr>" % (cls, "".join("<td>%s</td>" % c for c in r))
    st.markdown('<div class="scroller"><table class="ledger"><thead><tr>%s</tr></thead>'
                '<tbody>%s</tbody></table></div>' % (head, body), unsafe_allow_html=True)


RULES_LEDGER = [
    ("Keepers", "Five: three regular, two rookie. No position caps."),
    ("The price climbs", "Year 1 the round you drafted him in. Year 2 that minus three, or ADP "
                         "if it is kinder \u2014 but never later than his draft round. Year 3 "
                         "ADP, no choice. Year 4 is the wall."),
    ("Franchise tag", "One player, years four and five, frozen at the most expensive round you "
                      "have ever paid for him. Gone after year five. It still uses a keeper slot."),
    ("Rookie keepers", "Any NFL rookie you <b>drafted</b> — rookie draft or veteran draft, not a "
                       "waiver pickup. Costs your last picks, no clock, yours for his career. "
                       "Trade him and he becomes a regular keeper at his original draft round "
                       "with the clock back at year one."),
    ("Owning the pick", "A keeper lands on a round you actually hold. If it is gone he bumps to "
                        "the next-earliest round you own. The price travels with the player on a "
                        "trade — an R7 keeper is an R7 again for an owner who has their R7."),
    ("Taxi", "Two slots, two-year clocks, any rookie you drafted. Declared before the first "
             "kickoff and locked after it. Never startable. Promotion is permanent."),
    ("The pot", "FAAB you SPEND comes due. The first $%d goes to the Chase-bracket winner and "
                "everything above it rejoins the payout." % pot.cap_amount()[0]),
    ("The lottery", "One drum from %d, on final standing: playoff teams by finish, Chase teams "
                    "by Chase finish, so winning the Chase costs you balls. Champion always at the "
                    "floor. It picks a selection order, not a slot. No first choice two years "
                    "running." % int(config.lottery_rules().get("single_drum_from", 2027))),
]


# ---------------------------------------------------------------------------
# HOME
# ---------------------------------------------------------------------------

def my_situation(view: str) -> dict:
    """Everything the Home card needs about one team, in whatever state the
    season is actually in.

    Written to degrade rather than lie. Before the draft there is no record, no
    spend and no keeper worth anything, so the card reports the things that ARE
    settled - your two selection slots, an untouched budget, an empty bay -
    instead of printing four zeros and pretending they mean something.
    """
    out = {"record": None, "place": None, "played": 0, "faab_left": None, "owed": None,
           "best": None, "worst": None, "taxi": None, "slots": {}, "kept": 0,
           "rostered": 0}

    rosters = state["rosters"] or []
    r = next((x for x in rosters if str(x.get("owner_id")) == str(view)), None)
    if r:
        out["rostered"] = len(r.get("players") or [])
        st_ = r.get("settings") or {}
        w, l, t = (int(st_.get("wins", 0)), int(st_.get("losses", 0)),
                   int(st_.get("ties", 0)))
        if w or l or t:
            out["record"] = "%d\u2013%d%s" % (w, l, ("\u2013%d" % t) if t else "")
            out["played"] = w + l + t
            # Wins first, points for as the tiebreak - the same order Sleeper
            # shows, so the card never disagrees with the app they play on.
            def rank_key(x):
                sx = x.get("settings") or {}
                return (-int(sx.get("wins", 0)),
                        -(float(sx.get("fpts", 0)) + float(sx.get("fpts_decimal", 0)) / 100))
            ranked = sorted(rosters, key=rank_key)
            for i, x in enumerate(ranked):
                if str(x.get("owner_id")) == str(view):
                    out["place"] = i + 1
        budget = int(config.faab_rules()["budget"])
        left = st_.get("waiver_budget_used")
        if left is not None:
            out["faab_left"] = max(0, budget - int(left))
            out["owed"] = out["faab_left"]

    d = first_draw()
    for kind in ("rookie", "veteran"):
        order = d.get(kind) or []
        if str(view) in [str(o) for o in order]:
            out["slots"][kind] = [str(o) for o in order].index(str(view)) + 1

    mine = [x for x in value_rows() if str(x["owner_id"]) == str(view)]
    # Measured on SURPLUS - price against market - which is the same basis the
    # league-wide block on this page uses. Two definitions of "best contract"
    # on one screen is worse than either of them.
    #
    # That comparison only became meaningful once a keeper price stopped being
    # derived FROM adp. It used to be the cheaper of draft round and market, so
    # the two numbers were the same by construction and the gap was
    # structurally zero. The price is the draft round now, so they are
    # independent and the gap is real.
    priced = [x for x in mine if x.get("eligible") and x.get("cost")
              and x.get("surplus") is not None]
    if priced:
        out["best"] = max(priced, key=lambda x: x["surplus"])
        out["worst"] = min(priced, key=lambda x: x["surplus"])
    out["kept"] = len(submitted_keepers().get(str(view)) or [])

    try:
        bay = taxi.build(LG, SEASON).get(str(view))
    except Exception:
        bay = None
    if bay:
        out["taxi"] = bay
    return out


def meter(label: str, value: str, note: str, *, pct: float = None, pips=None,
          color: str = "var(--acc)", off: bool = False) -> str:
    """One fraction, drawn. Everything on this card is n-of-something, so the
    denominator is shown rather than left to be worked out."""
    if pips is not None:
        gauge = '<div class="pips">%s</div>' % "".join(
            '<span class="pip"%s></span>' % (
                ' style="background:%s;border-color:%s"' % (c, c) if c else "")
            for c in pips)
    else:
        gauge = ('<div class="track"><div class="fill" style="width:%.0f%%;background:%s">'
                 '</div></div>' % (max(0.0, min(1.0, pct or 0)) * 100, color))
    return ('<div class="m"><div class="t"><div class="k">%s</div>'
            '<div class="val%s"%s>%s</div></div><div class="n">%s</div>%s</div>' % (
                esc(label), " off" if off else "",
                "" if off else ' style="color:%s"' % color, value, note, gauge))


def band_numbers(sit: dict) -> tuple:
    """The two numbers at the top, and the caption under them.

    Two rather than one on purpose: a single figure leaves dead air beside it,
    and before the season starts a lone em-dash in an empty band reads as broken
    rather than as "not yet". There is always an honest pair.
    """
    weeks = int(config.league()["regular_season_weeks"])
    n = len(owner_ids())

    if sit["record"]:
        # Not "9 of 14 played" - the caption under the band already says that.
        # Whether you are in the bracket is the thing the record is actually for.
        cut = int(config.league()["playoff_teams"])
        where = ("in the playoff bracket" if sit["place"] and sit["place"] <= cut
                 else "outside the top %d" % cut if sit["place"] else "")
        left = ("Record", sit["record"], where, False)
        right = ("Standing", ordinal(sit["place"]) if sit["place"] else "\u2014",
                 "of %d &mdash; <b>final standing sets your veteran balls</b>" % n, True)
        played = sit["played"]
        cap = ("Week %d" % played, "%d to play" % max(0, weeks - played))
        return left, right, cap, (played / float(weeks) if weeks else 0)

    # Nothing played yet. The draft is done, so the two numbers are the two
    # things that ARE settled going into week 1 - what you can spend, and what
    # you are holding. This used to show your rookie-draft and veteran-draft
    # selection slots, which stopped meaning anything the moment the boards
    # were full.
    budget = int(config.faab_rules()["budget"])
    left = ("FAAB", "$%d" % (budget if sit["faab_left"] is None else sit["faab_left"]),
            "to spend all season &mdash; <b>every dollar you bid, you owe</b>", False)
    held = sit.get("rostered") or 0
    tx = len(sit["taxi"].pods) if sit["taxi"] else 0
    right = ("Rostered", str(held) if held else "\u2014",
             "%d active + %d on taxi" % (max(0, held - tx), tx) if held
             else "nobody rostered yet", True)
    return left, right, ("Week 1", "%d to play" % weeks), 0


def my_card(view: str) -> None:
    """Your team, on the way in.

    The one screen a manager opens from a phone in week 6 should answer "where
    do I stand and what is it costing me" without a tap. One object rather than
    a strip of tiles plus a loose table: header, the two numbers that matter,
    three meters, contracts in the footer.
    """
    sit = my_situation(view)
    budget = int(config.faab_rules()["budget"])
    total_keepers = int(config.keeper_rules()["total"])
    slots = int(config.taxi_rules()["slots"])
    taxi_used = len(sit["taxi"].pods) if sit["taxi"] else 0
    expiring = len(sit["taxi"].expiring) if sit["taxi"] else 0
    left_faab = budget if sit["faab_left"] is None else sit["faab_left"]

    theme.bar("Your team", "")

    (lk, lv, ln, _), (rk, rv, rn, _), (cap_l, cap_r), progress = band_numbers(sit)
    # The accent is reserved for a place that is worth something. Eighth of
    # eight lit up in the brand colour reads as congratulation.
    in_bracket = bool(sit["place"] and sit["place"] <= int(config.league()["playoff_teams"]))
    status = (("%s of %d" % (ordinal(sit["place"]), len(owner_ids())), not in_bracket)
              if sit["place"] else
              ("nothing played yet", True))

    parts = ['<div class="tcard">']
    parts.append(
        '<div class="head%s"><div class="nm"><small>Your team</small>%s</div>'
        '<div class="st%s">%s</div></div>' % (
            "" if in_bracket else " quiet", esc(team_of(view)),
            " off" if status[1] else "", esc(status[0])))

    parts.append(
        '<div class="band"><div class="row">'
        '<div class="half"><div class="k">%s</div><div class="v">%s</div>'
        '<div class="n">%s</div></div>'
        '<div class="div"></div>'
        '<div class="half mut"><div class="k">%s</div><div class="v">%s</div>'
        '<div class="n">%s</div></div></div>'
        '<div class="season">%s</div>'
        '<div class="cap"><span>%s</span><span>%s</span></div></div>' % (
            esc(lk), lv, ln, esc(rk), rv, rn,
            '<i style="width:%.0f%%"></i>' % (progress * 100) if progress else "",
            esc(cap_l), esc(cap_r)))

    parts.append('<div class="meters">')
    parts.append(meter(
        "FAAB left", "$%d" % left_faab,
        ("nothing bid, nothing owed" if left_faab == budget else
         "$%d spent &mdash; that is what you owe" % (budget - left_faab) if left_faab else
         "spent out &mdash; you owe the full $%d" % budget),
        pct=left_faab / float(budget),
        color="var(--good)" if left_faab == budget else "var(--warn)",
        off=left_faab == budget))
    parts.append(meter(
        "Keepers in", "%d<small>/%d</small>" % (sit["kept"], total_keepers),
        "on your slip",
        pips=["var(--acc2)" if i < sit["kept"] else None for i in range(total_keepers)],
        color="var(--acc2)", off=not sit["kept"]))
    # An expiring pod is coloured apart: "2 of 2" and "2 of 2 with a decision to
    # make" must not look identical.
    # Before kickoff the only thing that matters about this meter is how long
    # is left to fill it: after the lock an empty slot stays empty all season.
    dl = season.taxi_deadline()
    if dl and not dl["locked"]:
        taxi_note = ("locks %s &mdash; <b>%d day%s</b>" % (
            dl["label"], dl["days_left"], "" if dl["days_left"] == 1 else "s")
            if taxi_used < slots else "locks %s" % dl["label"])
    elif expiring:
        taxi_note = "%d pod%s expiring" % (expiring, "" if expiring == 1 else "s")
    else:
        taxi_note = "locked for the season" if dl else (
            "bay is empty" if not taxi_used else "no decisions due")
    parts.append(meter(
        "On taxi", "%d<small>/%d</small>" % (taxi_used, slots), taxi_note,
        pips=[("var(--warn)" if i >= taxi_used - expiring else "var(--good)")
              if i < taxi_used else None for i in range(slots)],
        color="var(--warn)" if (dl and not dl["locked"] and taxi_used < slots)
        else "var(--good)", off=not taxi_used))
    parts.append('</div>')

    shown = 0
    for tag, p in (("good", sit["best"]), ("bad", sit["worst"])):
        if not p or (tag == "bad" and p is sit["best"]):
            continue
        shown += 1
        parts.append(
            '<div class="foot"><span class="chip %s">%s contract</span>'
            '<span><b>%s</b> keeps at <span class="mono">R%s</span> against an '
            '<span class="mono">R%s</span> market &mdash; <b>%s</b></span></div>' % (
                tag, "best" if tag == "good" else "worst", esc(p["name"]),
                p["cost"], p["adp"] if p["adp"] else "&mdash;",
                ("%s value" % theme.signed(p["surplus"])) if p["surplus"]
                else "line ball"))
    if not shown:
        parts.append('<div class="foot"><span class="tiny">Contracts appear here once the '
                     'draft has been held.</span></div>')

    if sit["taxi"] and sit["taxi"].squeeze:
        sq = sit["taxi"].squeeze
        parts.append(
            '<div class="foot warn"><span><b>%d incoming rookie%s with nowhere to go.</b> '
            'Your bay is full and %d pod%s expiring &mdash; something has to be promoted, '
            'cut or kept before the rookie draft.</span></div>' % (
                sq, "" if sq == 1 else "s", expiring, "" if expiring == 1 else "s"))

    parts.append('</div>')
    st.markdown("".join(parts), unsafe_allow_html=True)


def _waiting_on(cast: dict, everyone: list) -> str:
    missing = [o for o in everyone if str(o) not in cast]
    if not missing:
        return "All %d in." % len(everyone)
    if len(missing) > 3:
        return "%d of %d voted." % (len(everyone) - len(missing), len(everyone))
    return "Waiting on %s." % esc(", ".join(who(o) for o in missing))


def render_matchups() -> None:
    """This week's fixtures.

    There is no projections feed anywhere in this app - Sleeper returns points
    already scored and the ADP file is season-long. So the edge shown is
    preseason consensus weight and is labelled as that, and anything inside a
    few points is called a coin flip rather than dressed up as 50.2%. Once
    games start the real score replaces it.
    """
    wk = season.current_week()
    games = season.matchups(wk)
    if not games:
        return
    live = any(g["started"] for g in games)
    theme.bar("Week %d" % wk, "live scores" if live
              else "preseason consensus &middot; no games played yet")
    rows = []
    for g in games:
        a, b = g["sides"]
        mine = VIEW in (a["owner_id"], b["owner_id"])
        if live:
            verdict = '<span class="mono">%.1f &ndash; %.1f</span>' % (a["points"], b["points"])
        elif g["too_close"]:
            verdict = '<span class="chip">too close to call</span>'
        else:
            verdict = '<span class="chip good">%s by %.0f%%</span>' % (
                esc(who(g["favourite"]).split()[0]), g["edge"])
        rows.append([
            '<div style="font-weight:%d">%s</div><div class="tiny">%s</div>' % (
                700 if mine else 550, esc(team_of(a["owner_id"])), esc(who(a["owner_id"]))),
            '<div style="font-weight:%d">%s</div><div class="tiny">%s</div>' % (
                700 if mine else 550, esc(team_of(b["owner_id"])), esc(who(b["owner_id"]))),
            verdict,
        ])
    ledger_table(["", "", ""], rows)
    if not live:
        st.markdown(
            '<div class="tiny" style="margin-top:8px">There is no weekly projection feed wired '
            'up, so this is the two rosters weighed against the <b>preseason consensus board</b> '
            '&mdash; not a score and not a win probability. Everyone drafted off the same board, '
            'so most weeks land inside the margin where it says nothing at all.</div>',
            unsafe_allow_html=True)


def render_pot_strip() -> None:
    """The money in one line: the four prizes and your bill, with the detail
    - every bill, the running total, the settlement - one tap away on The Pot.
    It used to carry a row per manager, which was The Pot's own table again."""
    rows = season.standings()
    if not rows:
        return
    spent = sum(r["spent"] for r in rows)
    cap = int(pot.cap_amount()[0])
    pool = int(config.buy_in() or 0) * len(rows)
    split = config.payout_split()
    prize = {k: int(round(pool * split[k] / 100.0)) for k in ("first", "second", "third")}
    to_chase = min(spent, cap)
    me = next((r for r in rows if r["owner_id"] == VIEW), None)
    cells = [("Winner", "$%d" % prize["first"], ""),
             ("Runner-up", "$%d" % prize["second"], ""),
             ("Third", "$%d" % prize["third"], ""),
             ("The Chase", "$%d" % to_chase,
              ("full &middot; +$%d over" % (spent - cap)) if spent > cap else "of $%d" % cap),
             ("Your bill", "$%d" % (me["spent"] if me else 0),
              ("of $%d" % me["entitlement"]) if me else "")]
    theme.bar("The money", "$%d pool &middot; $%d in the pot" % (pool, spent))
    st.markdown(
        '<div class="mstrip">' + "".join(
            f'<div{" class=me" if k == "Your bill" else ""}><span>{k}</span><b>{v}</b><i>{n}</i></div>'
            for k, v, n in cells)
        + f'<a href="?p=inseason&g=pot&t=pot{_keep()}" target="_self">The Pot &rarr;</a></div>',
        unsafe_allow_html=True)


def render_transactions() -> None:
    """What the league has actually done lately."""
    tx = season.transactions(limit=10)
    theme.bar("Recent moves", "adds, claims and trades")
    if not tx:
        st.markdown(
            '<div class="banner">No moves yet. Claims start landing once waivers run '
            'on Wednesday.</div>', unsafe_allow_html=True)
        return
    rows = []
    for t in tx:
        who_did = ", ".join(esc(who(o)) for o in t["owners"] if o) or "&mdash;"
        moved = []
        for p in t["adds"]:
            moved.append('<span class="chip good">+ %s</span>' % esc(p["name"]))
        for p in t["drops"]:
            moved.append('<span class="chip warn">&minus; %s</span>' % esc(p["name"]))
        rows.append([
            '<div style="font-weight:600">%s</div><div class="tiny">week %d</div>' % (
                esc(t["kind"]), t["week"]),
            who_did,
            " ".join(moved) or "&mdash;",
            ('<span class="mono">$%d</span>' % t["bid"]) if t["bid"] else "",
        ])
    ledger_table(["Move", "Who", "Players", "Bid"], rows)



def render_taxi_league(leaf=None) -> None:
    """Every taxi squad in the league, then yours.

    Same shape as the wire because it answers the same kind of question: what
    is out there, and what am I holding. Sleeper will show you one roster at a
    time and there is no league-wide taxi view in it at all, so an empty slot
    is invisible unless somebody opens eight rosters and counts.

    Eligibility is any rookie you DRAFTED, off either board - the 12th-round
    veteran-draft rookie qualifies exactly as much as the 1.01. So an open slot
    is only worth flagging when the manager is holding a rookie who could fill
    it, which is what the block leads with. From 2027 there is one draft and
    the distinction stops existing.
    """
    rows = season.taxi()
    if not rows:
        st.markdown('<div class="banner">Could not read rosters from Sleeper just now.</div>',
                    unsafe_allow_html=True)
        return
    slots = int(config.taxi_rules()["slots"])
    wasting = [r for r in rows if r["wasting"]]
    filled = sum(r["used"] for r in rows)

    _w = wasting[0] if wasting else None
    st.markdown(_bh("ink", "Taxi · league-wide", f'{filled}<small style="font-size:.5em">/{slots * len(rows)}</small>',
                    "slots used" + (f' — <b>{esc(who(_w["owner_id"]))}</b> has a rookie on the bench who could park for free'
                                    if _w else " — every squad that can be full is full")), unsafe_allow_html=True)
    st.markdown(
        '<div class="banner"><b>Any rookie you drafted is eligible</b> &mdash; off the rookie '
        'draft or the veteran draft, it makes no difference. Taxi sits <em>outside</em> your %d '
        'active spots, so a rookie parked here costs you no bench place and no keeper slot for '
        'two years. Squads are <b>declared before the first game of week one</b> and shut at '
        'kickoff &mdash; no swapping one rookie for another after that, and no shuttling '
        'anybody in and out for a bye. The only way off taxi is to <b>promote</b> him, which '
        'is permanent and costs you a roster spot.</div>' % config.active_roster_size(),
        unsafe_allow_html=True)
    if wasting:
        n = sum(len(r["parkable"]) for r in wasting)
        st.markdown(
            '<div class="banner" style="border-color:var(--bad)">'
            '<b>Declare before the first game kicks off.</b> A slot still empty at kickoff '
            'stays empty for the season &mdash; it is not returned and it cannot be filled '
            'later. <b>%d %s</b> on a bench right now that could be on taxi for free, held by '
            '<b>%s</b>. Every one is an active roster spot being spent on a player the rules '
            'say costs nothing. It has to be done in Sleeper; this page only counts it.</div>'
            % (n, "rookie" if n == 1 else "rookies",
               esc(", ".join(who(r["owner_id"]) for r in wasting))),
            unsafe_allow_html=True)

    body = []
    for r in rows:
        men = "".join(f'<span class="txc">{esc(p["name"])}</span>' for p in r["players"])
        if r["wasting"]:
            men += "".join(f'<span class="txc dash">{esc(p["name"])} on the bench</span>' for p in r["parkable"])
            flag, cls = f'{len(r["parkable"])} could park', " warn"
        elif r["open"]:
            flag, cls = f'{r["open"]} open', ""
        else:
            flag, cls = "full", ""
        body.append(
            f'<div class="tx{" me" if r["owner_id"] == VIEW else ""}{cls}"><div class="tx-n"><b>{esc(who(r["owner_id"]))}</b>'
            f'<span>{esc(team_of(r["owner_id"]))}</span></div><div class="tx-s">{men or "<span class=txc>nobody stashed</span>"}</div>'
            f'<em>{r["used"]}/{r["slots"]}</em><span class="tx-f">{flag}</span></div>')
    st.markdown('<div class="kx">' + "".join(body) + "</div>", unsafe_allow_html=True)

    # Legality. Sleeper gates taxi on NFL experience and nothing else, so it
    # will let someone stash a player they picked up off waivers.
    theme.bar("Legal squads", "Sleeper cannot enforce this rule for us")
    try:
        bays = taxi.build(LG, SEASON)
        flagged = taxi.compliance(bays, history.build(LG))
    except Exception:
        bays, flagged = {}, {}
    if flagged:
        st.markdown("".join(
            '<div class="banner" style="border-color:var(--bad);margin-bottom:8px">'
            '<b>%s</b> is stashing %s, who is not an eligible rookie. Taxi is for rookies '
            '<b>you drafted</b> this year, off either board &mdash; not waiver pickups and '
            'not veterans. He has to come off.</div>' % (
                esc(who(o)), ", ".join(esc(p.name) for p in pods))
            for o, pods in flagged.items()), unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="banner"><b>Every taxi squad is legal.</b> Sleeper polices taxi by a '
            'player&rsquo;s NFL experience &mdash; <code>taxi_allow_vets</code> blocks veterans '
            'and nothing else &mdash; so it would happily let someone stash a player they '
            'picked up off the wire. This is the check that catches it.</div>',
            unsafe_allow_html=True)

    # Your own squad, as slots with clocks on them rather than a table row.
    # The clock is the thing you act on: year two is promote-or-release.
    years = int(config.taxi_rules()["years"])
    mine = bays.get(VIEW) or taxi.Bay(owner_id=VIEW, pods=[])
    slots = int(config.taxi_rules()["slots"])
    theme.bar("Your taxi", "%d of %d filled &middot; %d-year clocks" % (
        len(mine.pods), slots, years))
    pods = []
    for i in range(slots):
        if i < len(mine.pods):
            pod = mine.pods[i]
            last = pod.year >= years
            pods.append(
                f'<div class="kt{" last" if last else ""}">{_ph_img(pod.player_id, "kh-img")}'
                f'<i>slot {i + 1} &middot; year {pod.year} of {years}</i><b>{esc(pod.name)}</b>'
                f'<span>{esc(pod.position)} &middot; '
                + ("clock is up — promote or release" if last else "can't start · free of bench · no keeper slot")
                + '</span></div>')
        else:
            pods.append(f'<div class="kt empty"><i>slot {i + 1}</i><b>open</b>'
                        '<span>and it stays empty — squads lock at kickoff</span></div>')
    if slots == 2:
        # Two slots on a turntable - tap to turn it. The clock is what you act
        # on, so each face carries its pips; year two lights amber.
        faces = []
        for i in range(slots):
            if i < len(mine.pods):
                pod = mine.pods[i]
                last = pod.year >= years
                pips = "".join('<u class="%s"></u>' % ("now" if k + 1 == pod.year and last else
                                                      "on" if k + 1 <= pod.year else "")
                               for k in range(years))
                faces.append(
                    f'<div class="txc-p{" last" if last else ""}">{_ph_img(pod.player_id, "txc-h")}'
                    f'<i>slot {i + 1} &middot; year {pod.year} of {years}</i><b>{esc(pod.name)}</b>'
                    f'<div class="pips">{pips}</div>'
                    f'<span>{esc(pod.position)} &middot; '
                    + ("clock is up &mdash; promote or release" if last else "one more year of runway")
                    + '</span></div>')
            else:
                faces.append(f'<div class="txc-p empty"><i>slot {i + 1}</i><b>Open</b>'
                             '<span>and it stays empty &mdash; squads lock at kickoff</span></div>')
        st.markdown('<div class="kx txc"><div class="txc-stage" tabindex="0" role="button" '
                    'aria-label="Turn to the other taxi slot"><div class="txc-in">'
                    + "".join(faces) + '</div></div><div class="txc-n">Tap the slot to turn the '
                    'table to the other one.</div></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="ktray txtray">%s</div>' % "".join(pods), unsafe_allow_html=True)
    st.markdown(
        '<div class="tiny" style="margin-top:8px">Promoting does <b>not</b> cost the '
        'rookie-keeper designation &mdash; he moves from costing nothing to costing a rookie '
        'slot at your last round, with no three-year clock. Promote onto a full roster and '
        'you cut somebody.</div>', unsafe_allow_html=True)


def _drafted_round(r: dict):
    """Which round he actually cost his owner, from this league's own draft.

    The one valuation worth trusting in-season. The ADP board is the preseason
    consensus everyone drafted off, so measuring a player against it in week 6
    just replays August. What he went for in the room is a fact.
    """
    return r.get("drafted_round")


def _dtxt(r: dict) -> str:
    """'drafted R3' / 'undrafted' / 'rookie draft' as plain text for a list row."""
    t = re.sub("<[^>]+>", "", _drafted_cell(r)).strip()
    return t if t in ("undrafted", "rookie draft") else f"drafted {t}"


def _drafted_cell(r: dict) -> str:
    rd = _drafted_round(r)
    if not rd:
        return ('<span class="tiny">rookie draft</span>' if r.get("from_rookie_draft")
                else '<span class="tiny">undrafted</span>')
    cost = r.get("cost")
    gain = (cost - rd) if cost else 0
    return ('<span class="mono">R%d</span>%s' % (
        rd, (' <span class="surplus %s">%s</span>' % (
            theme.surplus_class(gain), theme.signed(gain))) if gain else ""))


def _contract_flips_html(best: list) -> str:
    """Keeper contracts as flip cards: the price and the gap to market on the
    front, the year-by-year ladder on the back."""
    cards = []
    for r in best:
        if r["kind"] == "rookie":
            tag = "rookie slot"
        elif r.get("from_rookie_draft"):
            tag = "R%d premium" % engine.rookie_draft_premium()
        else:
            tag = "drafted R%d" % r["drafted_round"] if r.get("drafted_round") else "undrafted"
        mkt = "market R%d" % r["adp"] if r["adp"] else "no market price"
        steps = "".join(
            f'<div class="kf-st{" wall" if "wall" in v or "gone" in v else ""}"><span>{k or "after"}</span><b>{v}</b></div>'
            for k, v in _ladder_steps(r))
        cards.append(
            f'<div class="kflip{" me" if r["owner_id"] == VIEW else ""}" tabindex="0" role="button" '
            f'aria-label="Flip {esc(r["name"])}"><div class="kf-in">'
            f'<div class="kf-f"><div class="kf-top">{_ph_img(r["player_id"], "kf-h")}<div><b>{esc(r["name"])}</b>'
            f'<span>{esc(r["position"])} &middot; {tag}</span></div></div>'
            f'<div class="kf-px"><b>R{r["cost"]}</b><em class="{theme.surplus_class(r["surplus"])}">'
            f'{theme.signed(r["surplus"])} &middot; {mkt}</em></div>'
            f'<div class="kf-own">{_mgr_face(r["owner_id"])}{esc(team_of(r["owner_id"]))}</div></div>'
            f'<div class="kf-b"><span>The ladder &middot; {esc(_surname(r["name"]))}</span>{steps}</div>'
            f'</div></div>')
    return '<div class="kx kflips">' + "".join(cards) + '</div>'


def render_power() -> None:
    """Power rankings: what you have done, blended with what you are holding.

    The blend is labelled on the page rather than left implicit. In week 1 it
    is roster strength and says so - a ranking that quietly weighed an unplayed
    record would be roster strength wearing a disguise. Past the crossover
    week it is results only, because by then the season has opinions of its
    own.

    Movement is measured against the PRESEASON strength order, not last week's
    table. That needs no stored history and answers the better question: who is
    doing more than their draft said they would.

    NB: do not %-format this docstring. Streamlit's magic turns a bare
    expression into st.write, and a triple-quoted string followed by a percent
    operator is a BinOp rather than a docstring - it printed this whole
    paragraph onto the Home page above the block.
    """
    rows = season.power()
    if not rows:
        return
    cut = int(config.league()["playoff_teams"])
    # This absorbed the separate standings table. They were two league tables
    # in a row answering nearly the same question, and the record, points and
    # bracket cut are all here - the only thing the old block added was a
    # second ordering of the same eight teams.
    theme.bar("Power rankings", "%s &middot; top %d make the bracket" % (
        season.power_basis(rows), cut))
    top = rows[0]["power"] or 1.0

    body = []
    for r in rows:
        mv = r["moved"]
        if not r["weight"]:
            chip = '<span class="chip">seeded by the draft</span>'
        elif mv > 0:
            chip = '<span class="chip good">&#9650; %d on the draft</span>' % mv
        elif mv < 0:
            chip = '<span class="chip bad">&#9660; %d on the draft</span>' % abs(mv)
        else:
            chip = ""      # "holding its seed" on six rows of eight said nothing
        body.append([
            '<span class="mono" style="font-family:var(--f-display);font-weight:800;'
            'font-size:19px;color:%s">%d</span>' % (
                "var(--acc)" if r["rank"] == 1 else "var(--dim)", r["rank"]),
            '<div style="font-weight:%d">%s</div><div class="tiny">%s</div>' % (
                700 if r["owner_id"] == VIEW else 550,
                esc(team_of(r["owner_id"])), esc(who(r["owner_id"]))),
            '<span class="mono">%s</span>' % r["record"],
            '<span class="mono">%s</span>' % (
                "%.1f" % r["points_for"] if r["results"] else "&mdash;"),
            '<div class="pwr"><span style="width:%d%%"></span></div>'
            '<div class="tiny">%.0f</div>' % (
                int(round(100.0 * r["power"] / top)), r["power"]),
            chip,
        ])
    ledger_table(["", "Team", "W&ndash;L", "PF", "Power", ""], body,
                 me_row=next((i for i, r in enumerate(rows)
                              if r["owner_id"] == VIEW), None))
    st.markdown(
        '<div class="tiny" style="margin-top:6px">The bracket is decided on <b>record</b>, not '
        'on this. Power ranks the eight by form and roster; the top %d by W&ndash;L at the end '
        'of week %d are the ones who actually play for it.</div>' % (
            cut, config.regular_season_weeks()), unsafe_allow_html=True)
    if not rows[0]["weight"]:
        st.markdown(
            '<div class="tiny" style="margin-top:8px">Nothing has been played, so this is '
            '<b>roster strength only</b> &mdash; each team\'s best nine actives against the '
            'consensus board, taxi excluded. Everyone drafted off that same board, so this is '
            'close to ranking the room by draft slot. Records start pulling it apart from week '
            '1 and take over completely by week %d.</div>' % int(season.RESULTS_TAKE_OVER_BY),
            unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="tiny" style="margin-top:8px">Results are <b>60% win rate, 40% points '
            'for</b> &mdash; win rate alone rewards a soft schedule, points alone ignore that '
            'the league plays games. The arrow is movement against where your draft seeded you, '
            'not against last week.</div>', unsafe_allow_html=True)


def render_taxi_deadline() -> None:
    """The one dated thing on this page.

    Taxi squads lock when the first game kicks off, and the lock runs both
    ways: after it you cannot swap a rookie out, cannot shuttle anybody in to
    cover a bye, and a slot left open stays open for the season. That makes it
    the only decision on the front page with a clock on it, and the clock is
    the part worth printing - a date alone does not tell you it is close.

    Goes quiet once the deadline passes. A countdown to a date in the past is
    noise on every page load for the next four months.
    """
    dl = season.taxi_deadline()
    if not dl or dl["locked"]:
        return
    try:
        rows = season.taxi()
    except Exception:
        rows = []
    mine = next((r for r in rows if r["owner_id"] == VIEW), None)
    waiting = [r for r in rows if r["wasting"]]
    days = dl["days_left"]

    theme.bar("Taxi locks %s" % dl["label"],
              "%d day%s left &middot; declared before the first game" % (
                  days, "" if days == 1 else "s"))

    if mine and mine["wasting"]:
        st.markdown(
            '<div class="banner" style="border-color:var(--bad)">'
            '<b>You have %d rookie%s on your bench that could be on taxi.</b> %s. Taxi sits '
            'outside your %d active spots, so this is a roster place you are spending for '
            'nothing &mdash; and after kickoff the slot cannot be filled at all. It has to be '
            'done in Sleeper.</div>' % (
                len(mine["parkable"]), "" if len(mine["parkable"]) == 1 else "s",
                esc(", ".join(p["name"] for p in mine["parkable"])),
                config.active_roster_size()), unsafe_allow_html=True)
    elif mine and not mine["open"]:
        st.markdown(
            '<div class="banner" style="border-color:var(--good)"><b>Your squad is set.</b> '
            '%s. After %s they are locked in &mdash; the only way off taxi is to promote, '
            'which is permanent.</div>' % (
                esc(", ".join(p["name"] for p in mine["players"])), dl["label"]),
            unsafe_allow_html=True)

    if waiting:
        st.markdown(
            '<div class="tiny" style="margin-top:8px">Still to declare: <b>%s</b>. '
            '%d of %d slots filled across the league.</div>' % (
                esc(", ".join(who(r["owner_id"]) for r in waiting)),
                sum(r["used"] for r in rows), sum(r["slots"] for r in rows)),
            unsafe_allow_html=True)


# ------------------------------------------------------------------ this week
# The Kreeper hub's weekly screens (live matchup card, what to do, Live slot by
# slot, Matchup with start/sit and injury risk), ported. Shims map its names
# onto this app's: whose team = VIEW (always set here), team names via
# team_of, the league via LG.
MANAGERS = config.managers()
LEAGUE = {"sleeper_league_id": LG}


def _team_of(owner_id: str) -> str:
    return team_of(owner_id)


def _two_cell(owner: str, win: bool = False) -> str:
    return (f'<td class="two{" w" if win else ""}"><b>{esc(team_of(owner))}</b>'
            f'<span>{esc(who(owner))}</span></td>')


class _ThemeShim:
    """theme.section_head as this app's section bar."""
    @staticmethod
    def section_head(title_html: str, caption: str = "", page: bool = False) -> str:
        return '<div class="bar">%s<span class="n">%s</span></div>' % (title_html, caption)


# The Draft Room's weekly screens, rebuilt for Kreeper: a live matchup card,
# lineup advice, every matchup slot by slot. These are the only pages that
# know whose phone they're on — see _me(). Everything league-wide stays
# league-wide.
_START_CHIP = '<span class="wchip good">start</span>'
_POSC = {"QB": "#c98fbb", "RB": "#7fd8b4", "WR": "#6aa6f0", "TE": "#f0b357"}


def _me():
    """Whose team this page is about: the viewer chosen in the masthead."""
    return VIEW


def _href_with(**kv) -> str:
    """This page's URL with some params replaced — for links that should
    switch something (the team) without leaving the page."""
    from urllib.parse import urlencode
    q = {k: st.query_params.get(k) for k in st.query_params.keys()}
    q.update({k: v for k, v in kv.items() if v is not None})
    return "?" + urlencode(q)


@st.cache_data(ttl=86400, show_spinner=False)
def get_player_meta() -> dict:
    """{pid: (name, pos, nfl_team)} for every skill-position player."""
    out = {}
    for pid, p in sleeper.get_players().items():
        pos = p.get("position")
        if pos in gameday.SKILL:
            nm = p.get("full_name") or f'{p.get("first_name", "")} {p.get("last_name", "")}'.strip()
            out[str(pid)] = (nm or str(pid), pos, p.get("team") or "")
    return out


@st.cache_data(ttl=86400, show_spinner=False)
def _pos_team_maps():
    meta = get_player_meta()
    return {p: m[1] for p, m in meta.items()}, {p: m[2] for p, m in meta.items()}


def _pname(pid: str) -> str:
    return get_player_meta().get(str(pid), (str(pid), "", ""))[0]


@st.cache_data(ttl=3600, show_spinner=False)
def get_injury_map() -> dict:
    """{pid: (injury_status, practice_participation, body_part)} for every
    flagged lineup-position player, from Sleeper's player blob (refreshed
    daily — Sleeper asks for no more than that)."""
    out = {}
    for pid, p in sleeper.get_players().items():
        if p.get("position") in gameday.LINEUP_POS and (p.get("injury_status") or p.get("practice_participation")):
            out[str(pid)] = (p.get("injury_status"), p.get("practice_participation"), p.get("injury_body_part"))
    return out


def _risk(ctx: dict, pid: str) -> dict:
    """gameday.injury_risk for one player in this week's context, plus the
    evidence behind it for the hover text."""
    pos_of, team_of = _pos_team_maps()
    status, practice, part = get_injury_map().get(str(pid), (None, None, None))
    r = gameday.injury_risk(status, practice, pos_of.get(str(pid), ""),
                            gameday.status(ctx["games"], team_of.get(str(pid), "")))
    r["why"] = " · ".join(x for x in (status, part, f"practice: {practice}" if practice else None) if x)
    return r


def _risk_td(ctx: dict, pid: str) -> str:
    r = _risk(ctx, pid)
    if r["pct"] is None:
        return '<td class="risk"><span class="rkp ok">&mdash;</span></td>'
    lab = f'{r["label"]} ' if r["label"] else ""
    tip = r["why"] or "no injury tag — the usual in-game risk for his position"
    return f'<td class="risk" title="{tip}"><span class="rkp {r["level"]}">{lab}{r["pct"]}%</span></td>'


_RISK_NOTE = ("Risk % = the chance a player misses the game or gets hurt in it: his injury tag "
              "(moved by this week's practice report) plus a typical in-game rate for his "
              "position. Projections are discounted by the chance he misses, so an Out player "
              "projects 0. An estimate, not a medical model; tags refresh daily.")


@st.cache_data(ttl=30, show_spinner=False)
def get_week_ctx(week: int) -> dict:
    """Everything the weekly pages need for one week, cached 30s so a page
    refreshing every 30s for eight phones is still one call per source.

    sides: {owner: {mid, starters, players, actual}}; starters are aligned
    to `slots` the way Sleeper stores them."""
    lid = LEAGUE["sleeper_league_id"]
    games = gameday.load_week(SEASON, week)
    live = gameday.any_live(games)
    rows = sleeper.get_matchups(lid, week, ttl=30 if live else 600) or []
    rosters = sleeper.get_rosters(lid)
    rosters = [r for r in rosters if r.get("roster_id") is not None]
    r2o = {int(r["roster_id"]): str(r.get("owner_id")) for r in rosters}
    roster_players = {r2o[int(r["roster_id"])]: [str(p) for p in (r.get("players") or [])] for r in rosters}
    slots = [s for s in (sleeper.get_league(lid).get("roster_positions") or [])
             if s not in ("BN", "IR", "TAXI")]
    sides = {}
    for m in rows:
        o = r2o.get(int(m.get("roster_id") or 0))
        if not o or m.get("matchup_id") is None:
            continue
        sides[o] = {"owner": o, "mid": m["matchup_id"],
                    "starters": [str(p) for p in (m.get("starters") or [])],
                    "players": [str(p) for p in (m.get("players") or [])] or roster_players.get(o, []),
                    "actual": {str(k): float(v or 0) for k, v in (m.get("players_points") or {}).items()}}
    # Projections are Sleeper's, discounted by each player's chance of missing
    # the game. Sleeper is slow to zero an Out player, and undiscounted the
    # lineup advice told people to START him (Breece Hall, Out, quad).
    proj = dict(gameday.week_projections(SEASON, week))
    for pid, (status, practice, _part) in get_injury_map().items():
        if pid in proj:
            miss = gameday.injury_risk(status, practice, "")["miss"]
            if miss:
                proj[pid] = round(proj[pid] * (1 - miss), 2)
    return {"week": week, "games": games, "live": live, "slots": slots, "sides": sides,
            "proj": proj}


def _outlook(ctx: dict, side: dict, starters=None) -> dict:
    pos_of, team_of = _pos_team_maps()
    return gameday.side_outlook(starters if starters is not None else side["starters"],
                                side["actual"], ctx["proj"], pos_of, team_of, ctx["games"])


def _pairs(ctx: dict, me=None) -> list:
    """[(side_a, side_b)] for every matchup, `me` first and on the left."""
    by_mid = {}
    for s in ctx["sides"].values():
        by_mid.setdefault(s["mid"], []).append(s)
    out = []
    for mid in sorted(by_mid):
        pair = by_mid[mid]
        if len(pair) != 2:
            continue
        a, b = pair
        if b["owner"] == me:
            a, b = b, a
        out.append((a, b))
    out.sort(key=lambda ab: ab[0]["owner"] != me)
    return out


def _wp(a: dict, b: dict) -> float:
    return gameday.win_prob(a["final"], a["sd"], b["final"], b["sd"])


def _week_started(ctx: dict) -> bool:
    return any(g.get("state") != "pre" for g in ctx["games"].values())


def _slot_chip(pos: str, slot: str = "") -> str:
    c = _POSC.get(pos, "#8a8a95")
    return f'<span class="wslot" style="--c:{c}">{slot or pos or "&mdash;"}</span>'


def _two_div(owner: str, win: bool = False) -> str:
    return (f'<div class="two{" w" if win else ""}"><b>{_team_of(owner)}</b>'
            f'<span>{config.manager_name(owner)}</span></div>')


_THUMB = "https://sleepercdn.com/content/nfl/players/thumb/{}.jpg"


def _ph_img(pid, cls: str) -> str:
    return (f'<img class="{cls}" src="{_THUMB.format(pid)}" alt="" onerror="this.style.visibility=\'hidden\'">'
            if pid else "")


def _top_pid(ctx: dict, side: dict):
    """The side's best projected starter — the face its scoreboard half wears."""
    ps = [p for p in (side.get("starters") or []) if p and p != "0"]
    return max(ps, key=lambda p: ctx["proj"].get(p, 0.0)) if ps else None


def _rec_of(owner: str) -> str:
    try:
        return str(my_situation(owner).get("record") or "")
    except Exception:  # noqa: BLE001
        return ""


def _hero_html(a: str, b: str, *, pill: str, big_a: float, big_b: float, kicker: str,
               wp: float, sub_a: str, sub_b: str, cells: list, photo_a=None, photo_b=None) -> str:
    """The matchup as a fight poster, the Kreeper League's cover in Bloody
    Sunday: your side crimson, theirs black, the two managers facing off -
    you in the blue duotone, them in crimson, each a square the full height of
    its band at the outer edge, mirrored to face each other and fading out
    before the score, VS on the seam. The best player stands in for anyone
    with no photo. Then four tiles."""
    tiles = "".join(f'<div><span>{k}</span><b class="{c}">{v}</b><i>{s_}</i></div>' for k, v, s_, c in cells)
    ra, rb = _rec_of(a), _rec_of(b)
    ga, gb = _mgr_photo(str(a), "g"), _mgr_photo(str(b), "r")
    ph_a = f'<img class="xb-ph xb-mg" src="{ga}" alt="">' if ga else _ph_img(photo_a, "xb-ph")
    ph_b = f'<img class="xb-ph xb-mg" src="{gb}" alt="">' if gb else _ph_img(photo_b, "xb-ph")
    lab = f"{kicker} · {pill}".replace("&middot;", "·").upper()
    vs = '<span class="xb-vs">VS</span>' if ga and gb else ""
    return (
        f'<div class="kx xb{_intro("xb") if ga and gb else ""}"><div class="xb-s me{" fight" if ga else ""}">{ph_a}<div class="xb-t">'
        f'<span>{_team_of(a)}{" &middot; " + ra if ra else ""}</span><b>{big_a:.1f}</b><i>{sub_a}</i></div></div>'
        f'<div class="xb-m">{vs}<span class="xb-k">{lab}</span><b>{wp * 100:.0f}<sup>%</sup></b><em>win probability</em>'
        f'<div class="xb-bar"><i style="width:{wp * 100:.0f}%"></i></div></div>'
        f'<div class="xb-s op{" fight" if gb else ""}"><div class="xb-t"><span>{_team_of(b)}{" &middot; " + rb if rb else ""}</span>'
        f'<b>{big_b:.1f}</b><i>{sub_b}</i></div>{ph_b}</div></div>'
        f'<div class="kx xb-tiles">{tiles}</div>')


def _bh(tone: str, kick: str, num, line: str, *, photo=None, grid=None) -> str:
    """A page's cover: royal when it wants you to act, black with a gold edge
    when it's telling you where you stand."""
    g = ""
    if grid:
        g = '<div class="bh-grid">' + "".join(f'<div><span>{k}</span><b>{v}</b><i>{s_}</i></div>'
                                              for k, v, s_ in grid) + '</div>'
    ph = _ph_img(photo, "bh-duo") if (photo and not grid) else ""
    return (f'<div class="kx bh {tone}{" has-grid" if grid else ""}"><div class="bh-l"><span class="bh-k">{kick}</span>'
            f'<b class="bh-n">{num}</b><em>{line}</em></div>{g}{ph}</div>')


def _advice(me: str, week: int) -> dict | None:
    """Lineup advice for `me` in `week`, or None if they have no game."""
    ctx = get_week_ctx(week)
    side = ctx["sides"].get(me)
    if not side or not ctx["slots"]:
        return None
    pos_of, team_of = _pos_team_maps()
    locked = {p for p in side["players"]
              if gameday.status(ctx["games"], team_of.get(p, "")) in ("in", "post")}
    adv = gameday.lineup_advice(side["starters"], side["players"], ctx["slots"], ctx["proj"],
                                pos_of, locked=locked)
    adv["byes"] = [p for p in side["players"] if pos_of.get(p) in gameday.SKILL
                   and team_of.get(p) and team_of[p] not in ctx["games"] and ctx["games"]]
    adv["ctx"], adv["side"], adv["week"] = ctx, side, week
    return adv


def _todo_html(me: str, adv: dict) -> str:
    wk = adv["week"]
    cards = []
    for i, o, gain in adv["swaps"][:3]:
        cards.append(("&uarr;", f"Start {_pname(i)}, bench {_pname(o)}",
                      f"Week {wk} &middot; worth <b>+{gain:.1f}</b> to your total.",
                      f"+{gain:.1f}", "points", ""))
    for h in adv["holes"]:
        cards.append(("+", f"No {h} for Week {wk}",
                      "Nobody on your roster can fill it. Claim one before waivers run Wednesday.",
                      "0.0", "projected", "bad"))
    if adv["byes"]:
        cards.append(("&#9650;", f'Week {wk} takes {len(adv["byes"])} of yours',
                      ", ".join(_pname(p) for p in adv["byes"]) + ".",
                      str(len(adv["byes"])), "on bye", "bad"))
    ctx_ = adv["ctx"]
    hurt = [(p, _risk(ctx_, p)) for p in adv["side"]["starters"] if p and p != "0"]
    hurt = sorted(((p, r) for p, r in hurt if r["level"] in ("high", "out")), key=lambda x: -(x[1]["pct"] or 0))
    if hurt:
        cards.append(("+", f'{len(hurt)} starter{"s" if len(hurt) != 1 else ""} at real risk this week',
                      ", ".join(f'{_pname(p)} ({r["label"] or "—"}, {r["pct"]}%)' for p, r in hurt[:3])
                      + ". Line up a backup before he locks.",
                      f'{hurt[0][1]["pct"]}%', "risk", "bad"))
    if not cards:
        cards.append(("&#10003;", f"Your Week {wk} lineup is the best one you have",
                      "Nothing to change.", "", "", "good"))
    html = "".join(
        f'<div class="todo {c}{" hot" if (i == 0 and c != "good") else ""}"><span class="ic">{ic}</span><div><b>{t}</b><span>{s}</span></div>'
        f'<div class="tv"><b>{v}</b><i>{k}</i></div></div>' for i, (ic, t, s, v, k, c) in enumerate(cards))
    left = my_situation(me).get("faab_left")
    if left is not None:
        html += f'<div class="todo-foot">Waivers run Wednesday &middot; <b>${left}</b> FAAB left.</div>'
    return html


def _lineup_rows(ctx: dict, side: dict, *, flag=frozenset(), show_actual=True) -> str:
    """One lineup as one list: slot, face, name and game, a royal-to-gold bar,
    the risk chip and the points. A flagged row (one to bench) turns royal."""
    pos_of, team_of = _pos_team_maps()
    vals = []
    for pid in side["starters"]:
        played = gameday.status(ctx["games"], team_of.get(pid, "")) in ("in", "post")
        vals.append(side["actual"].get(pid, 0.0) if (show_actual and played) else ctx["proj"].get(pid, 0.0))
    mx = max(vals + [1.0])
    rows = []
    for slot, pid, v in zip(ctx["slots"], side["starters"], vals):
        if not pid or pid == "0":
            rows.append(f'<div class="xl swap"><span class="xl-s">{slot}</span><span></span>'
                        '<div class="xl-n"><b>Empty</b><i>nobody in this slot</i></div><div class="xl-b"></div>'
                        '<div class="xl-r"></div><b class="xl-p">0.0</b></div>')
            continue
        tm = team_of.get(pid, "")
        risk = _risk_td(ctx, pid).replace('<td class="risk"', '<div class="xl-r"').replace("</td>", "</div>")
        rows.append(
            f'<div class="xl{" swap" if pid in flag else ""}"><span class="xl-s">{slot}</span>{_ph_img(pid, "xl-f")}'
            f'<div class="xl-n"><b>{_pname(pid)}</b><i>{tm} &middot; {gameday.game_label(ctx["games"], tm)}</i></div>'
            f'<div class="xl-b"><i style="width:{100 * v / mx:.0f}%"></i></div>{risk}'
            f'<b class="xl-p">{v:.1f}</b></div>')
    return '<div class="kx xl-wrap">' + "".join(rows) + "</div>"


def _picker_html(compact: bool = False) -> str:
    me = _me()
    cards = "".join(
        f'<a class="tp{" on" if o == me else ""}" '
        f'href="{_href_with(team=o)}" target="_self">'
        f'<b>{m.get("team") or m["name"]}</b><em>{m["name"]}</em></a>'
        for o, m in MANAGERS.items())
    blurb = ("It decides whose matchup and lineup lead Home and the This Week pages. "
             "Asked once, remembered on this device; switch any time from the masthead. "
             "Everything league-wide stays league-wide.")
    return (f'<div class="card picker"><div class="weyebrow">{"Make it yours" if compact else "This device"}</div>'
            f'<h3>Which team is yours?</h3><p>{blurb}</p><div class="tpgrid">{cards}</div></div>')


def render_team_picker() -> None:
    st.markdown(_picker_html(), unsafe_allow_html=True)


def _need_me(what: str):
    """The current owner, or render the picker and return None."""
    me = _me()
    if me is None:
        st.caption(f"{what} is about your team — pick it once and this device remembers.")
        st.markdown(_picker_html(compact=True), unsafe_allow_html=True)
    return me


def _render_home_my_week(me: str, cur: int) -> None:
    """Home's top: your live matchup, what to do, and your lineup."""
    ctx = get_week_ctx(cur)
    pair = next((ab for ab in _pairs(ctx, me) if ab[0]["owner"] == me), None)
    if pair:
        a, b = (_outlook(ctx, s) for s in pair)
        started = _week_started(ctx)
        done = gameday.week_complete(ctx["games"])
        aw = gameday.advice_week(cur, ctx["games"])
        adv = _advice(me, aw)
        _sit = my_situation(me)
        rec = ({"wins": _sit["record"], "losses": None, "rank": _sit["place"]}
               if _sit.get("record") else None)
        lineup_cell = (("Week %d lineup" % aw,
                        (f'{len(adv["swaps"])} change{"s" if len(adv["swaps"]) != 1 else ""}'
                         + (f' + {len(adv["holes"])} hole' if adv["holes"] else "")),
                        f'worth +{adv["best_total"] - adv["set_total"]:.1f} pts',
                        "amber" if adv["swaps"] or adv["holes"] else "good") if adv else
                       ("Lineup", "&mdash;", "no game that week", ""))
        st.markdown(_hero_html(
            me, pair[1]["owner"], photo_a=_top_pid(ctx, pair[0]), photo_b=_top_pid(ctx, pair[1]),
            pill=f"Week {cur}",
            big_a=a["points"] if started else a["final"], big_b=b["points"] if started else b["final"],
            kicker="final" if done else "live" if started else "projected", wp=_wp(a, b),
            sub_a=f'you &middot; {a["left"]} still to play', sub_b=f'{b["left"]} still to play',
            cells=[("Projected final", f'{a["final"]:.0f}&ndash;{b["final"]:.0f}', "actual + what's left", "good"),
                   ("Still to play", str(a["left"]), f'theirs {b["left"]}', ""),
                   lineup_cell,
                   ("Record", rec["wins"] if rec else "&mdash;",
                    f'#{rec["rank"]} in the league' if rec else "", "")]),
            unsafe_allow_html=True)
        left = sorted((g for g in ctx["games"].values() if g.get("state") == "pre" and g.get("home")),
                      key=gameday.kickoff_ts)
        if left and not done:
            nxt = left[0]
            st.markdown(f'<div class="lockline">Week {cur} &middot; next kickoff <b>{nxt["opp"]} @ '
                        f'{[t for t, g in ctx["games"].items() if g is nxt][0]}</b> '
                        f'{gameday.kickoff_label(nxt)} &middot; {len(left)} game{"s" if len(left) != 1 else ""} to go</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown('<div class="lockline"></div>', unsafe_allow_html=True)
        todo = _todo_html(me, adv) if adv else ""
        st.markdown(
            f'<div class="weyebrow">What to do</div>{todo}'
            f'<a class="to-matchup" href="?p=inseason&g=week&t=matchup{_keep()}" target="_self">'
            f'Your full lineup and bench &rarr;</a>', unsafe_allow_html=True)


# ---------------------------------------------------------------- Game of the Week
# Every game this week is scored by how much it moves the LEAGUE'S playoff
# odds, not just the two teams in it: the rest of the season is simulated
# twice, once with each side taking the game, and the gap summed over all
# eight teams is what it's worth (halfmen/stakes.py). The biggest one is the
# Game of the Week. Every Around-the-League row gets the same meter plus a
# rooting tip, because in an eight-team league with four playoff spots the
# games you aren't playing in move you nearly as much as the one you are.
#
# Ported from the Kreeper League.

_NFL_CITY = {
    "ARI": "Arizona", "ATL": "Atlanta", "BAL": "Baltimore", "BUF": "Buffalo", "CAR": "Carolina",
    "CHI": "Chicago", "CIN": "Cincinnati", "CLE": "Cleveland", "DAL": "Dallas", "DEN": "Denver",
    "DET": "Detroit", "GB": "Green Bay", "HOU": "Houston", "IND": "Indianapolis", "JAX": "Jacksonville",
    "KC": "Kansas City", "LAC": "the Chargers", "LAR": "the Rams", "LV": "Las Vegas", "MIA": "Miami",
    "MIN": "Minnesota", "NE": "New England", "NO": "New Orleans", "NYG": "the Giants", "NYJ": "the Jets",
    "PHI": "Philadelphia", "PIT": "Pittsburgh", "SEA": "Seattle", "SF": "San Francisco",
    "TB": "Tampa Bay", "TEN": "Tennessee", "WAS": "Washington",
}


@st.cache_data(ttl=3600, show_spinner="Simulating the rest of the season…")
def get_stakes(week: int) -> dict:
    try:
        return stakes.week_stakes(LG, SEASON, week, n_sims=12000)
    except Exception:          # noqa: BLE001 - a slate with no fixtures must not kill the page
        return {"games": []}


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def get_h2h(a: str, b: str, week: int) -> dict:
    try:
        return stakes.h2h(LG, a, b, SEASON, week)
    except Exception:          # noqa: BLE001
        return {"a": 0, "b": 0, "games": []}


@st.cache_data(ttl=600, show_spinner=False)
def _draft_done(kind: str) -> bool:
    """Every configured Sleeper draft of this kind is complete."""
    ids = (config.drafts().get("sleeper_drafts") or {}).get(kind) or []
    if not ids:
        return False
    try:
        return all((sleeper.get_draft(str(i)) or {}).get("status") == "complete" for i in ids)
    except Exception:          # noqa: BLE001
        return False


@st.cache_data(ttl=600, show_spinner=False)
def _phase() -> str:
    try:
        return phase.current_phase(LG)
    except Exception:          # noqa: BLE001
        return "in_season"


def _intro(key: str) -> str:
    """" in" the first time `key` renders this session, so an entrance plays
    once per page load (every nav link is a full load) and never again on a
    rerun or on Live's 30-second refresh."""
    seen = st.session_state.setdefault("_intros", set())
    if key in seen:
        return ""
    seen.add(key)
    return " in"


def _flap(new: float, old) -> str:
    """A score as split-flap digits: the ones that changed since `old` (the
    last value this session showed) flip over like a stadium board."""
    ns = f"{new:.1f}"
    os_ = f"{old:.1f}" if isinstance(old, (int, float)) else ns
    os_ = os_.rjust(len(ns))[-len(ns):]
    out = []
    for c, o in zip(ns, os_):
        cls = "fd pt" if c == "." else "fd"
        if c == o:
            out.append(f'<span class="{cls} s">{c}</span>')
        else:
            o = o.strip() or "&nbsp;"
            out.append(f'<span class="{cls}"><span class="h t"><span>{c}</span></span><span class="h b"><span>{o}</span></span>'
                       f'<span class="ft"><span>{o}</span></span><span class="fb"><span>{c}</span></span></span>')
    return '<span class="fl">' + "".join(out) + '</span>'


def _sphere(n: int):
    """n points through a unit sphere on a golden-angle spiral: every ball in
    a drum gets its own depth, and the cluster never collapses into a ring."""
    import math
    out = []
    for i in range(n):
        yy = 1 - (i + 0.5) * 2 / n
        rr = math.sqrt(max(0.0, 1 - yy * yy))
        th = i * 2.39996
        out.append((math.cos(th) * rr, yy, math.sin(th) * rr))
    return out


def _drum3d(seats, colour: str, tint: str, label: str) -> str:
    """One lottery drum as a glass globe: each seat a ball with the manager's
    face on it, sized by his weight, so the weighting is the picture."""
    balls = []
    for (x, y, z), s_ in zip(_sphere(len(seats)), seats):
        d = 24 + s_.weight * 1.3
        reach = 84 - d / 2 + 6
        ph = _mgr_photo(str(s_.owner_id))
        inner = f'<img src="{ph}" alt="">' if ph else f'<em>{_initials(s_.owner_id)}</em>'
        balls.append(
            f'<div class="ball" style="transform:translate3d({x * reach:.1f}px,{y * reach * .82:.1f}px,{z * reach:.1f}px)">'
            f'<div class="fc3" style="--d:{d:.0f}px"><div class="bob" style="--bt:{1.4 + (len(balls) % 3) * .35:.2f}s;'
            f'--bd:-{len(balls) * .37:.2f}s"><div class="orb{" out" if s_.locked_out else ""}" style="--bc:{colour}" '
            f'title="{esc(who(s_.owner_id))} - {s_.weight} balls">{inner}</div></div></div></div>')
    return (f'<div><div class="drum" style="--tint:{tint}"><div class="floor"></div><div class="stand"></div>'
            f'<div class="glb"><div class="back"></div><div class="spin">{"".join(balls)}</div>'
            f'<div class="cage"><i></i><i></i><i></i><i></i></div><div class="glass"></div><div class="axle"></div></div></div>'
            f'<span class="drum-l">{label}</span></div>')


def _gotw(cur: int):
    """(the game, every game) for this week, or (None, []) with nothing to rank."""
    games = get_stakes(cur).get("games") or []
    return (games[0], games) if games and games[0]["stakes"] > 0 else (None, games)


def _gotw_cover(ctx: dict, g: dict, games: list, me, cur: int) -> str:
    a, b = g["a"], g["b"]
    sa, sb = ctx["sides"].get(a), ctx["sides"].get(b)
    oa, ob = (_outlook(ctx, sa), _outlook(ctx, sb)) if sa and sb else (None, None)
    started = _week_started(ctx)

    def side(o, cls):
        ph = _mgr_photo(str(o), "g")
        img = f'<img class="gw-ph" src="{ph}" alt="">' if ph else ""
        win, lose = (g["if_a"], g["if_b"]) if o == a else (g["if_b"], g["if_a"])
        rec = _rec_of(o)
        txt = (f'<div class="gw-t"><span>{esc(_team_of(o))}{" &middot; " + rec if rec else ""}</span>'
               f'<b>{esc(_first(o))}</b>'
               f'<i>playoff odds <em class="up">{win.get(o, 0)}%</em> win &middot; '
               f'<em class="dn">{lose.get(o, 0)}%</em> lose</i></div>')
        return f'<div class="gw-s {cls}">' + (img + txt if cls == "l" else txt + img) + '</div>'
    nxt = games[1]["stakes"] if len(games) > 1 else 0
    sub = f"the most of any game this week &middot; next biggest {nxt}" if nxt else "the week's only game"
    mid = (f'<div class="gw-m"><span class="gw-k">Game of the Week &middot; week {cur}</span>'
           f'<span class="gw-vs">VS</span><b>{g["stakes"]}</b>'
           f'<em>points of playoff odds on the line</em><span class="gw-sub">{sub}</span></div>')
    cover = f'<div class="kx gw{_intro("gw%d" % cur)}">{side(a, "l")}{mid}{side(b, "r")}</div>'

    # tiles: all-time, the score, the ripple, your rooting interest
    h = get_h2h(a, b, cur)
    if h["games"]:
        lead = a if h["a"] > h["b"] else b if h["b"] > h["a"] else None
        big = (f'{_first(lead)} {max(h["a"], h["b"])}&ndash;{min(h["a"], h["b"])}' if lead
               else f'Tied {h["a"]}&ndash;{h["b"]}')
        yr, wk, pa, pb = h["games"][0]
        t1 = ("All-time", big, f'last met {yr} wk {wk}: {_first(a if pa >= pb else b)} '
                               f'{max(pa, pb):.1f}&ndash;{min(pa, pb):.1f}', "")
    else:
        # 2026 is season one, so this is every pair until next year
        t1 = ("All-time", "First meeting", "no regular-season games on record", "")
    if oa:
        wp = _wp(oa, ob)
        fav, pr = (a, wp) if wp >= 0.5 else (b, 1 - wp)
        if started:
            t2 = ("Live", f'{oa["points"]:.1f}&ndash;{ob["points"]:.1f}',
                  f'{_first(fav)} {pr * 100:.0f}% to win &middot; {oa["left"] + ob["left"]} still to play', "")
        else:
            t2 = ("Projected", f'{oa["final"]:.0f}&ndash;{ob["final"]:.0f}',
                  f'{_first(fav)} by {abs(oa["final"] - ob["final"]):.0f} &middot; {pr * 100:.0f}% to win', "")
    else:
        t2 = ("Projected", "&mdash;", "", "")
    others = [o for o in g["if_a"] if o not in (a, b)]
    rip = max(others, key=lambda o: abs(g["if_a"][o] - g["if_b"][o]), default=None)
    if rip and abs(g["if_a"][rip] - g["if_b"][rip]) >= 1:
        hi_with = a if g["if_a"][rip] > g["if_b"][rip] else b
        lo_v, hi_v = sorted((g["if_a"][rip], g["if_b"][rip]))
        t3 = ("The ripple", f'{_first(rip)} +{hi_v - lo_v}',
              f'a {_first(hi_with)} win lifts {_first(rip)} {lo_v}% &rarr; {hi_v}%', "")
    else:
        t3 = ("The ripple", "None", "nobody else's odds move", "")
    # The fourth tile is your stake in this game. The Game of the Week's row
    # is left out of the ladder under it, so this is the only place it shows.
    if me in (a, b):
        t4 = ("Your game", f'&plusmn;{abs(g["if_a"][me] - g["if_b"][me])}',
              f'{max(g["if_a"][me], g["if_b"][me])}% with a win, '
              f'{min(g["if_a"][me], g["if_b"][me])}% with a loss', "amber")
    elif me and me in g["if_a"]:
        root = stakes.rooting([g], me).get((a, b))
        if root and root[1] >= 1:
            t4 = ("Your rooting", f'{_first(root[0])} +{root[1]}',
                  f"you're {max(g['if_a'][me], g['if_b'][me])}% if {_first(root[0])} wins, "
                  f"{min(g['if_a'][me], g['if_b'][me])}% if not", "amber")
        else:
            t4 = ("Your rooting", "Either way", "this one doesn't move your odds", "")
    else:
        t4 = ("Your rooting", "&mdash;", "pick your team to see who to root for", "")
    tiles = "".join(f'<div><span>{k}</span><b class="{c}">{v}</b><i>{s_}</i></div>'
                    for k, v, s_, c in (t1, t2, t3, t4))
    return cover + f'<div class="kx xb-tiles gw-tiles">{tiles}</div>'


def _tape_html(ctx: dict, g: dict) -> str:
    """The marquee position battles: each side's best QB, RB and top two WRs by
    projection (TE when a side starts fewer than two WRs). Live points once a
    player's game is on, projections before, same rule on both sides."""
    a, b = g["a"], g["b"]
    sa, sb = ctx["sides"].get(a), ctx["sides"].get(b)
    if not sa or not sb:
        return ""
    pos_of, team_of_ = _pos_team_maps()
    proj = ctx["proj"]

    def by_pos(side):
        out = {}
        for pl in side["starters"] or []:
            if pl and pl != "0":
                out.setdefault(pos_of.get(pl, ""), []).append(pl)
        return {k: sorted(v, key=lambda x: -proj.get(x, 0.0)) for k, v in out.items()}

    def val(side, pid):
        a_, pj = side["actual"].get(pid, 0.0), proj.get(pid, 0.0)
        stt = gameday.status(ctx["games"], team_of_.get(pid, ""))
        if stt in ("post", "bye"):
            return a_, True
        return (a_ + 0.5 * pj, False) if stt == "in" else (pj, False)
    pa, pb = by_pos(sa), by_pos(sb)
    want = [("QB", 0, "QB"), ("RB", 0, "RB1"), ("WR", 0, "WR1"), ("WR", 1, "WR2"), ("TE", 0, "TE")]
    rows = []
    for pos, i, lab in want:
        if len(rows) == 4:
            break
        if len(pa.get(pos, [])) > i and len(pb.get(pos, [])) > i:
            x, y = pa[pos][i], pb[pos][i]
            vx, lx = val(sa, x)
            vy, ly = val(sb, y)
            d = vx - vy
            w = min(100.0, abs(d) / 12 * 100)
            fill = f'<i style="width:{w:.0f}%"></i>'
            rows.append(
                f'<div class="gw-tp"><b class="gw-n">{esc(_pname(x))}<span>{team_of_.get(x, "")}</span></b>'
                f'<b class="gw-p{" w" if d > 0 else ""}{"" if lx else " pj"}">{vx:.1f}</b>'
                f'<div class="gw-e"><div class="gw-h l">{fill if d > 0 else ""}</div><span>{lab}</span>'
                f'<div class="gw-h r">{fill if d < 0 else ""}</div></div>'
                f'<b class="gw-p{" w" if d < 0 else ""}{"" if ly else " pj"}">{vy:.1f}</b>'
                f'<b class="gw-n r">{esc(_pname(y))}<span>{team_of_.get(y, "")}</span></b></div>')
    # the notes: a manager facing a player who shares his name, and NFL teams
    # both sides are leaning on
    notes = []
    for mgr, opp in ((a, sb), (b, sa)):
        mine = {w.lower(): w for w in who(mgr).split() if len(w) > 2}
        for pl in opp["starters"] or []:
            nm = _pname(pl) if pl and pl != "0" else ""
            hit = next((mine[w.lower()] for w in nm.replace("'", " ").split() if w.lower() in mine), None)
            if hit:
                notes.append(f'<b>{esc(hit)} vs {esc(hit)}.</b> {esc(who(mgr))} is facing {esc(nm)}.')
                break

    def last(pid):
        parts = [w for w in _pname(pid).split() if w not in ("Jr.", "Sr.", "II", "III", "IV")]
        return parts[-1] if parts else _pname(pid)
    ta = {}
    for o, side in ((a, sa), (b, sb)):
        for pl in side["starters"] or []:
            if pl and pl != "0" and team_of_.get(pl):
                ta.setdefault(team_of_[pl], {}).setdefault(o, []).append(last(pl))
    shared = [t for t, m in ta.items() if len(m) == 2]
    if shared:
        t = shared[0]

        def names(xs):
            return " and ".join(xs) if len(xs) <= 2 else ", ".join(xs[:-1]) + " and " + xs[-1]
        notes.append(f'Both sides lean on {_NFL_CITY.get(t, t)}: {_first(a)} starts {names(ta[t][a])}, '
                     f'{_first(b)} starts {names(ta[t][b])}.')
    note = f'<div class="gw-note">{" ".join(notes)}</div>' if notes else ""
    head = (f'<div class="gw-th">{_mgr_face(a, "gw-f")}<div><b>{esc(_team_of(a))}</b>'
            f'<span>{esc(_first(a))} &middot; {_rec_of(a)}</span></div>'
            f'<div class="r"><b>{esc(_team_of(b))}</b><span>{esc(_first(b))} &middot; {_rec_of(b)}</span></div>'
            f'{_mgr_face(b, "gw-f")}</div>')
    key = '<div class="gw-key">projected finals &middot; <i>italic</i> = still playing or yet to play</div>'
    return f'<div class="kx gw-tape">{head}{"".join(rows)}{key}{note}</div>' if rows else ""


def _riding_html(g: dict) -> str:
    """Everyone this one game moves: where their playoff odds land either way."""
    a, b = g["a"], g["b"]
    moved = sorted((o for o in g["if_a"] if abs(g["if_a"][o] - g["if_b"].get(o, 0)) >= 2),
                   key=lambda o: -abs(g["if_a"][o] - g["if_b"].get(o, 0)))
    if not moved:
        return ""
    rows = []
    for o in moved:
        x, y = g["if_a"][o], g["if_b"].get(o, 0)
        lo, hi = min(x, y), max(x, y)
        rows.append(f'<div class="gw-rd">{_mgr_face(o)}<b>{esc(_first(o))}</b><div class="gw-tr">'
                    f'<i class="gw-band" style="left:{lo}%;width:{hi - lo}%"></i>'
                    f'<i class="gw-dot a" style="left:{x}%"></i><i class="gw-dot b" style="left:{y}%"></i></div>'
                    f'<span class="gw-nums"><em class="a">{x}%</em> / <em class="b">{y}%</em></span></div>')
    big = moved[0]
    lose = min(g["if_a"][big], g["if_b"][big])
    win = max(g["if_a"][big], g["if_b"][big])
    return (f'<div class="kx gw-ride"><div class="gw-leg"><span><i class="gw-dot a"></i>if {_first(a)} wins</span>'
            f'<span><i class="gw-dot b"></i>if {_first(b)} wins</span><span class="dim">playoff odds</span></div>'
            + "".join(rows) +
            f'<div class="gw-note">{_first(big)} has the most riding on it: {win}% with a win, '
            f'{lose}% with a loss.</div></div>')


@st.cache_data(ttl=3600, show_spinner=False)
def _recap_png(week: int, me: str) -> bytes:
    r = get_week_review(week)
    if not r:
        return b""
    pts = r["pts"]
    b, c, lk = r["blowout"], r["close"], r["lucky"]
    tiles = [("Blowout", "%s by %.1f" % (_first(b["w"]), b["margin"]), "%.1f over %s" % (pts[b["w"]], _first(b["l"]))),
             ("Nail-biter", "%s by %.1f" % (_first(c["w"]), c["margin"]),
              "%.1f-%.1f over %s" % (pts[c["w"]], pts[c["l"]], _first(c["l"])))]
    if r["upset"]:
        u = r["upset"]
        tiles.append(("Upset", "%s over %s" % (_first(u["w"]), _first(u["l"])),
                      "projected %.1f worse before kickoff" % r["upset_gap"]))
    if r["star"]:
        pid, o, v = r["star"]
        tiles.append(("Player of the week", _pname(pid), "%.1f for %s" % (v, _first(o))))
    bo = r["benchiest"]
    tiles.append(("Most left on the bench", "%s %.1f" % (_first(bo), r["bench"][bo]),
                  "what his best lineup would have added"))
    tiles.append(("Luckiest win", "%s %.1f" % (_first(lk["w"]), pts[lk["w"]]),
                  "%d scored more and he still won" % r["lucky_beaten"] if r["lucky_beaten"]
                  else "the top score, no luck needed"))
    nxt_g, _games = _gotw(week + 1)
    footer = ("This week: %s v %s, %d points of playoff odds on the line" % (
        _first(nxt_g["a"]), _first(nxt_g["b"]), nxt_g["stakes"])) if nxt_g else ""
    return recap.render(week, config.league().get("name", "7 1/2 Men").replace("1/2", "½"),
                        [(o, _first(o), v) for o, v in pts.items()], tiles, me=me, footer=footer)


def _render_recap_download(week: int) -> None:
    """Week in Review as one image for the group chat."""
    try:
        png = _recap_png(week, VIEW)
    except Exception:          # noqa: BLE001 - a missing font or face must not cost the page
        png = b""
    if not png:
        return
    c1, c2 = st.columns([1, 2])
    with c1:
        st.image(png, width="stretch")
    with c2:
        st.markdown('<div class="tiny" style="margin-bottom:8px">The week in one picture, sized for a '
                    'group chat: the skyline, the five stories, and this week&rsquo;s Game of the Week. '
                    'Your tower is the red one.</div>', unsafe_allow_html=True)
        st.download_button("Download the week %d recap" % week, png,
                           file_name="7half-men-week-%d.png" % week, mime="image/png")


def _render_gotw(cur: int, me=None, full: bool = True) -> None:
    """Live's deep dive on the Game of the Week. The poster itself is Home's;
    here it's the tale of the tape and who it moves."""
    g, games = _gotw(cur)
    if not g:
        return
    ctx = get_week_ctx(cur)
    st.markdown(_ThemeShim.section_head('Game of the <span class="g">Week</span>',
                                        f"{_first(g['a'])} v {_first(g['b'])} &middot; "
                                        f"{g['stakes']} points of playoff odds on the line"),
                unsafe_allow_html=True)
    tape = _tape_html(ctx, g)
    ride = _riding_html(g) if full else ""
    if tape and ride:
        st.markdown(f'<div class="wk-cols gw-cols"><div><div class="weyebrow">Tale of the tape</div>{tape}</div>'
                    f'<div><div class="weyebrow">What&rsquo;s riding on it</div>{ride}</div></div>',
                    unsafe_allow_html=True)
    elif tape or ride:
        st.markdown(f'<div class="gw-cols"><div class="weyebrow">'
                    f'{"Tale of the tape" if tape else "What&rsquo;s riding on it"}</div>'
                    f'{tape or ride}</div>', unsafe_allow_html=True)


@st.cache_data(ttl=3600, show_spinner=False)
def get_week_review(week: int) -> dict:
    """Last week's story out of its final box scores: the blowout, the
    nail-biter, the upset (against Sleeper's own pre-game projections), points
    left on every bench, and the luckiest win. Ported from the Kreeper League.
    """
    if week < 1 or not season.week_is_final(LG, week):
        return {}
    ctx = get_week_ctx(week)
    pos_of, _tm = _pos_team_maps()
    pre = gameday.week_projections(SEASON, week) or {}
    pts, proj_tot, bench = {}, {}, {}
    for o, sd in ctx["sides"].items():
        st_ = [pl for pl in sd["starters"] if pl and pl != "0"]
        pts[o] = sum(sd["actual"].get(pl, 0.0) for pl in st_)
        proj_tot[o] = sum(float(pre.get(pl, 0) or 0) for pl in st_)
        best = gameday.optimal_lineup(sd["players"], ctx["slots"], sd["actual"], pos_of, prefer=st_)
        bench[o] = sum(sd["actual"].get(pl, 0.0) for _sl, pl in best if pl) - pts[o]
    games = []
    for sa, sb in _pairs(ctx):
        a, b = sa["owner"], sb["owner"]
        w, l = (a, b) if pts[a] >= pts[b] else (b, a)
        games.append({"w": w, "l": l, "margin": pts[w] - pts[l]})
    if not games:
        return {}
    star = max(((pl, o, sd["actual"].get(pl, 0.0)) for o, sd in ctx["sides"].items()
                for pl in sd["starters"] if pl and pl != "0"), key=lambda x: x[2], default=None)
    upsets = [g for g in games if proj_tot[g["w"]] < proj_tot[g["l"]]]
    upset = max(upsets, key=lambda g: proj_tot[g["l"]] - proj_tot[g["w"]]) if upsets else None
    lucky = min(games, key=lambda g: pts[g["w"]])
    beaten_by = sum(1 for o in pts if pts[o] > pts[lucky["w"]])
    return {"week": week, "pts": pts, "bench": bench,
            "blowout": max(games, key=lambda g: g["margin"]),
            "close": min(games, key=lambda g: g["margin"]),
            "upset": upset, "upset_gap": proj_tot[upset["l"]] - proj_tot[upset["w"]] if upset else 0,
            "lucky": lucky, "lucky_beaten": beaten_by,
            "top": max(pts, key=pts.get), "star": star,
            "benchiest": max(bench, key=bench.get)}


def _render_week_review(week: int) -> None:
    r = get_week_review(week)
    if not r:
        return
    pts, bench = r["pts"], r["bench"]
    st.markdown(_ThemeShim.section_head(f'Week {week} in <span class="g">Review</span>',
                                        "the final box scores"), unsafe_allow_html=True)
    order = sorted(pts.items(), key=lambda kv: -kv[1])
    top_v = max(1.0, order[0][1])
    towers = []
    for i, (o, v) in enumerate(order):
        c = "var(--kr2)" if o == VIEW else "var(--kg)" if i == 0 else "#57505a"
        towers.append(f'<div class="sky-t" style="--c:{c}">{_mgr_face(o)}<b>{v:.0f}</b>'
                      f'<div class="sky-s" style="--h:{140 * v / top_v:.0f}px;--dl:{i * .06:.2f}s"></div>'
                      f'<span>{esc(_first(o))}</span></div>')
    st.markdown('<div class="kx sky">' + "".join(towers) + '</div>', unsafe_allow_html=True)
    b, c, lk = r["blowout"], r["close"], r["lucky"]
    tiles = [("Blowout", f'{_first(b["w"])} by {b["margin"]:.1f}',
              f'{pts[b["w"]]:.1f} over {_first(b["l"])}', ""),
             ("Nail-biter", f'{_first(c["w"])} by {c["margin"]:.1f}',
              f'{pts[c["w"]]:.1f}&ndash;{pts[c["l"]]:.1f} over {_first(c["l"])}', "")]
    if r["upset"]:
        u = r["upset"]
        tiles.append(("Upset", f'{_first(u["w"])} over {_first(u["l"])}',
                      f'projected {r["upset_gap"]:.1f} worse before kickoff', "amber"))
    if r["star"]:
        pid, o, v = r["star"]
        tiles.append(("Player of the week", esc(_pname(pid)), f'{v:.1f} for {_first(o)}', ""))
    tiles.append(("Luckiest win", f'{_first(lk["w"])} {pts[lk["w"]]:.1f}',
                  (f'{r["lucky_beaten"]} team{"s" if r["lucky_beaten"] != 1 else ""} scored more '
                   f'and he still won' if r["lucky_beaten"] else "the week's top score, no luck needed"), ""))
    # fill whole rows: 6 tiles = 3 across, 7-8 = 4 across with the last widened
    cols = 3 if len(tiles) in (3, 6) else 4
    gap = (-len(tiles)) % cols
    wide = f' style="grid-column:span {gap + 1}"' if gap else ""
    html = "".join(f'<div{wide if i == len(tiles) - 1 else ""}>'
                   f'<span>{k}</span><b class="{cl}">{v}</b><i>{s_}</i></div>'
                   for i, (k, v, s_, cl) in enumerate(tiles))
    st.markdown(f'<div class="kx xb-tiles wr" style="--wr-cols:{cols}">{html}</div>',
                unsafe_allow_html=True)
    rows = sorted(bench.items(), key=lambda kv: -kv[1])
    st.markdown('<div class="kx wr-bench"><div class="weyebrow">Points left on the bench</div>'
                + "".join(f'<div class="wr-b">{_mgr_face(o)}<b>{esc(_first(o))}</b>'
                          f'<div class="wr-bar"><i style="width:{100 * v / max(1.0, rows[0][1]):.0f}%"></i></div>'
                          f'<em>{v:.1f}</em></div>' for o, v in rows) + '</div>', unsafe_allow_html=True)


def _render_around_league(cur: int, me=None, cover: bool = False) -> None:
    """Every game this week, biggest stakes first: the live score, a meter for
    how much it moves the league's playoff odds, and who `me` should root for.
    With `cover`, the Game of the Week leads as the poster and its own row is
    left out of the list below it rather than shown twice."""
    ctx = get_week_ctx(cur)
    pairs = _pairs(ctx, me)
    if not pairs:
        return
    done = gameday.week_complete(ctx["games"])
    games = get_stakes(cur).get("games") or []
    by_pair = {frozenset((x["a"], x["b"])): x for x in games}
    top = max((x["stakes"] for x in games), default=0) or 1
    gotw = frozenset((games[0]["a"], games[0]["b"])) if games and games[0]["stakes"] else None
    roots = stakes.rooting(games, me)
    st.markdown(_ThemeShim.section_head(
        'Around the <span class="g">League</span>',
        f"week {cur} &middot; {'final' if done else 'biggest stakes first' if games else f'all {len(pairs)} games'}"),
        unsafe_allow_html=True)
    pairs = sorted(pairs, key=lambda pr: -(by_pair.get(frozenset((pr[0]["owner"], pr[1]["owner"]))) or {}).get("stakes", 0))
    if cover and gotw:
        st.markdown(_gotw_cover(ctx, games[0], games, me, cur), unsafe_allow_html=True)
        pairs = [pr for pr in pairs if frozenset((pr[0]["owner"], pr[1]["owner"])) != gotw]
    rows = []
    for sa, sb in pairs:
        a, b = _outlook(ctx, sa), _outlook(ctx, sb)
        to_play = a["left"] + b["left"]
        key = frozenset((sa["owner"], sb["owner"]))
        gm = by_pair.get(key)
        hot = key == gotw

        def team(o, right=False, won=False):
            rec = _rec_of(o)
            txt = (f'<div><b{" class=w" if won else ""}>{esc(_team_of(o))}</b>'
                   f'<span>{esc(_first(o))}{" &middot; " + rec if rec else ""}</span></div>')
            return (f'<div class="gw-lt{" r" if right else ""}">'
                    + (txt + _mgr_face(o) if right else _mgr_face(o) + txt) + '</div>')
        if gm:
            meter = (f'<div class="gw-meter"><i style="width:{100 * gm["stakes"] / top:.0f}%"></i></div>'
                     f'<span>{gm["stakes"]} pts of playoff odds at stake</span>'
                     + ('<em class="gw-tag">Game of the Week</em>' if hot else ""))
        else:
            meter = ""
        r = roots.get((gm["a"], gm["b"])) if gm else "none"
        if me in (sa["owner"], sb["owner"]) and gm:
            root = (f'<span class="gw-root you">your game &middot; '
                    f'&plusmn;{abs(gm["if_a"].get(me, 0) - gm["if_b"].get(me, 0))}</span>')
        elif r and r != "none" and r[1] >= 1:
            root = f'<span class="gw-root">root for <b>{esc(_first(r[0]))}</b> +{r[1]}</span>'
        elif r and r != "none":
            root = '<span class="gw-root">doesn&rsquo;t move you</span>'
        else:
            root = ""
        rows.append(
            f'<div class="gw-lr{" hot" if hot else ""}">{team(sa["owner"], won=a["final"] > b["final"])}'
            f'<div class="gw-mid"><div class="gw-sc"><b>{a["points"]:.1f}</b><i>&ndash;</i>'
            f'<b>{b["points"]:.1f}</b></div>'
            f'<span class="gw-tp2">{f"{to_play} to play" if to_play else "final"}</span>{meter}</div>'
            f'{team(sb["owner"], right=True, won=b["final"] > a["final"])}{root}</div>')
    if rows:
        st.markdown('<div class="kx gw-ladder">' + "".join(rows) + "</div>", unsafe_allow_html=True)
    if me and games:
        st.caption("Root for = which result helps your own playoff odds, and by how much "
                   "(the playoff sim run both ways).")


def _faceoff_html(ctx: dict, sa: dict, sb: dict) -> str:
    pos_of, team_of = _pos_team_maps()

    def cell(side, pid, right=False):
        if not pid or pid == "0":
            return f'<div class="fo{" r" if right else ""}"><div class="fn"><b>Empty</b><em>&mdash;</em></div><div class="fp">0.0</div></div>'
        tm = team_of.get(pid, "")
        s = gameday.status(ctx["games"], tm)
        val = (f'{side["actual"].get(pid, 0.0):.1f}' if s in ("post", "in", "bye")
               else f'<span class="proj">{ctx["proj"].get(pid, 0.0):.1f}</span>')
        cls = {"pre": "live", "in": "inplay"}.get(s, "")
        return (f'<div class="fo {"r" if right else ""} {cls}"><div class="fn"><b>{_pname(pid)}</b>'
                f'<em>{pos_of.get(pid, "")} &middot; <span class="gl">{gameday.game_label(ctx["games"], tm)}</span>'
                f'<span class="gs">{gameday.game_label(ctx["games"], tm, short=True)}</span></em></div>'
                f'<div class="fp">{val}</div></div>')

    rows = []
    for slot, pa, pb in zip(ctx["slots"], sa["starters"], sb["starters"]):
        done = all(gameday.status(ctx["games"], team_of.get(p, "")) in ("post", "bye") for p in (pa, pb))
        d = sa["actual"].get(pa, 0.0) - sb["actual"].get(pb, 0.0) if done else None
        mid = _slot_chip(pos_of.get(pa) or pos_of.get(pb, ""), slot) + (
            f'<i class="{"pos" if d > 0 else "neg" if d < 0 else ""}">{d:+.1f}</i>' if d is not None else "<i>&middot;</i>")
        rows.append(f'<div class="forow">{cell(sa, pa)}<div class="fm">{mid}</div>{cell(sb, pb, True)}</div>')
    return "".join(rows)


def _h2h_html(ctx: dict, sa: dict, sb: dict) -> str:
    """Slot by slot as head-to-head rows: points (actual once his game has
    started, projection before) and an edge bar that fills toward the winner."""
    pos_of, team_of = _pos_team_maps()

    def val(side, pid):
        if not pid or pid == "0":
            return 0.0, False
        stt = gameday.status(ctx["games"], team_of.get(pid, ""))
        if stt in ("in", "post"):
            return side["actual"].get(pid, 0.0), True
        return ctx["proj"].get(pid, 0.0), False
    rows = []
    for slot, pa, pb in zip(ctx["slots"], sa["starters"], sb["starters"]):
        va, la = val(sa, pa)
        vb, lb = val(sb, pb)
        d = va - vb
        w = min(100.0, abs(d) / 20 * 100)
        fill = f'<i style="width:{w:.0f}%"></i>'
        na = _pname(pa) if pa and pa != "0" else "Empty"
        nb = _pname(pb) if pb and pb != "0" else "Empty"
        rows.append(
            f'<div class="khs"><span class="xl-s">{slot}</span><b class="hn">{na}</b>'
            f'<b class="hp{" win" if d > 0 else ""}{"" if la else " pj"}">{va:.1f}</b>'
            f'<div class="he"><div class="hh l">{fill if d > 0 else ""}</div><span>{d:+.1f}</span>'
            f'<div class="hh r">{fill if d < 0 else ""}</div></div>'
            f'<b class="hp{" win" if d < 0 else ""}{"" if lb else " pj"}{" zero" if vb == 0 else ""}">{vb:.1f}</b>'
            f'<b class="hn r">{nb}</b></div>')
    return "".join(rows)


def render_live() -> None:
    st.markdown(_ThemeShim.section_head('<span class="g">Live</span>', "every matchup in the league", page=True),
                unsafe_allow_html=True)
    cur = season.current_week()
    if not cur:
        st.info("🏈 Live scores show up here once the season kicks off.")
        return
    me = _me()
    auto = st.toggle("Auto-refresh while a game is on", value=True, key="live_auto")
    every = 30 if (auto and get_week_ctx(cur)["live"]) else None

    @st.fragment(run_every=every)
    def _body():
        ctx = get_week_ctx(cur)
        import datetime as dt
        from zoneinfo import ZoneInfo
        now = dt.datetime.now(ZoneInfo("America/New_York"))
        st.caption(f"Updated {now:%-I:%M:%S %p} ET · "
                   + ("refreshes every 30s while a game is on" if every
                      else "no game on right now — reload to update" if auto else "auto-refresh off"))
        homes = sorted(((t, g) for t, g in ctx["games"].items() if g.get("home")),
                       key=lambda tg: ({"in": 0, "pre": 1, "post": 2}.get(tg[1]["state"], 3),
                                       gameday.kickoff_ts(tg[1])))
        tiles = "".join(
            f'<div class="gm {g["state"]}"><span>{g["opp"]}</span><b>{"" if g["state"] == "pre" else int(g["opp_score"])}</b>'
            f'<span>{t}</span><b>{"" if g["state"] == "pre" else int(g["score"])}</b>'
            f'<em>{gameday.game_label(ctx["games"], t, short=True)}</em></div>' for t, g in homes)
        if tiles:
            st.markdown(f'<div class="weyebrow">The slate &middot; week {cur}</div><div class="wstrip">{tiles}</div>',
                        unsafe_allow_html=True)
        pairs = _pairs(ctx, me)
        st.markdown(_ThemeShim.section_head("Every <span class=\"g\">Matchup</span>",
                                       "yours first &middot; what each one is worth" if me else ""),
                    unsafe_allow_html=True)
        # What each game moves: the stakes meter and the rooting tip ride on
        # the card itself instead of a second list of the same four games.
        sk = get_stakes(cur).get("games") or []
        by_pair = {frozenset((x["a"], x["b"])): x for x in sk}
        top_st = max((x["stakes"] for x in sk), default=0) or 1
        roots = stakes.rooting(sk, me)
        cards = []
        for i, (sa, sb) in enumerate(pairs):
            a, b = _outlook(ctx, sa), _outlook(ctx, sb)
            wp = _wp(a, b)
            mine = me is not None and sa["owner"] == me
            gm = by_pair.get(frozenset((sa["owner"], sb["owner"])))
            if gm:
                hot = sk and gm is sk[0] and gm["stakes"] > 0
                r_ = roots.get((gm["a"], gm["b"]))
                tip = ("your game &middot; &plusmn;%d" % abs(gm["if_a"].get(me, 0) - gm["if_b"].get(me, 0))
                       if mine else ("root for <b>%s</b> +%d" % (esc(_first(r_[0])), r_[1]) if r_ and r_[1] >= 1
                                     else "doesn&rsquo;t move you" if r_ else ""))
                stake_html = (f'<div class="mm-stk{" hot" if hot else ""}"><div class="gw-meter">'
                              f'<i style="width:{100 * gm["stakes"] / top_st:.0f}%"></i></div>'
                              f'<span>{gm["stakes"]} pts of playoff odds at stake'
                              + (' &middot; <em class="gw-tag">Game of the Week</em>' if hot else "")
                              + f'</span><span class="gw-root">{tip}</span></div>')
            else:
                stake_html = ""

            def half(side, o, cls):
                r = _rec_of(side["owner"])
                img = (_mgr_face(side["owner"], "mm-mf") if _mgr_photo(str(side["owner"]))
                       else _ph_img(_top_pid(ctx, side), "mm-f"))
                last = st.session_state.setdefault("_flaps", {})
                old = last.get((cur, side["owner"]))
                last[(cur, side["owner"])] = o["points"]
                gain = (f'<em class="fl-d">+{o["points"] - old:.1f}</em>'
                        if isinstance(old, (int, float)) and o["points"] - old >= 0.05 else "")
                txt = (f'<div><span>{_team_of(side["owner"])}{" &middot; " + r if r else ""}</span>'
                       f'<b class="flb">{_flap(o["points"], old)}{gain}</b>'
                       f'<i>proj {o["final"]:.0f} &middot; {o["left"]} to play</i></div>')
                return f'<div class="mm-s {cls}">' + (img + txt if cls == "a" else txt + img) + '</div>'
            cards.append(
                f'<div class="mm{" me" if mine else ""}">{half(sa, a, "a")}'
                f'<div class="mm-m"><b>{wp * 100:.0f}<sup>%</sup></b><div class="mm-bar"><i style="width:{wp * 100:.0f}%"></i></div></div>'
                f'{half(sb, b, "b")}</div>' + stake_html
                + (f'<div class="weyebrow pad">Your matchup &middot; slot by slot</div>{_h2h_html(ctx, sa, sb)}' if mine else ""))
        st.markdown('<div class="kx">' + "".join(cards) + '</div>', unsafe_allow_html=True)
        if not me:
            st.caption("Pick your team (masthead, top right) to see your matchup slot by slot.")

    _body()
    # Outside the fragment: none of these change on a 30-second refresh.
    _render_gotw(cur, me)
    _render_week_review(cur - 1)
    _render_recap_download(cur - 1)


def render_matchup() -> None:
    st.markdown(_ThemeShim.section_head('<span class="g">Matchup</span>', "your next game &middot; start / sit", page=True),
                unsafe_allow_html=True)
    me = _need_me("Matchup")
    cur = season.current_week()
    if me is None:
        return
    if not cur:
        st.info("🏈 Matchups show up here once the season kicks off.")
        return
    aw = gameday.advice_week(cur, get_week_ctx(cur)["games"])
    adv = _advice(me, aw)
    ctx = get_week_ctx(aw)
    pair = next((ab for ab in _pairs(ctx, me) if ab[0]["owner"] == me), None)
    if not adv or not pair:
        st.info(f"No matchup for you in Week {aw}.")
        return
    sa, sb = pair
    a, b = _outlook(ctx, sa), _outlook(ctx, sb)
    best = [p for _, p in adv["best"] if p]
    fixed = _outlook(ctx, sa, starters=best)
    pre = sorted((g for g in ctx["games"].values() if g.get("state") == "pre"), key=gameday.kickoff_ts)
    started = _week_started(ctx)
    st.markdown(_hero_html(
        me, sb["owner"], photo_a=_top_pid(ctx, sa), photo_b=_top_pid(ctx, sb), pill=f"Week {aw} &middot; {'live' if started else 'preview'}",
        big_a=a["final"], big_b=b["final"], kicker="projected final", wp=_wp(a, b),
        sub_a="you &middot; lineup as set", sub_b="their lineup as set",
        cells=[("Lineup", f'{len(adv["swaps"])} change{"s" if len(adv["swaps"]) != 1 else ""}'
                + (f' + {len(adv["holes"])} hole' if adv["holes"] else ""),
                f'worth +{adv["best_total"] - adv["set_total"]:.1f} pts'
                + (f' &middot; no {", ".join(adv["holes"])}' if adv["holes"] else ""),
                "amber" if adv["swaps"] or adv["holes"] else "good"),
               ("On bye", str(len(adv["byes"])), "of your skill players", "bad" if adv["byes"] else ""),
               ("Next lock", gameday.kickoff_label(pre[0]) if pre else "&mdash;",
                "first game still to kick off" if pre else "every game has started", ""),
               ("Win prob if fixed", f"{_wp(fixed, b) * 100:.0f}%",
                f"from {_wp(a, b) * 100:.0f}% as it stands", "good")]),
        unsafe_allow_html=True)
    pos_of, team_of = _pos_team_maps()
    flag_out = {o for _, o, _g in adv["swaps"]}
    flag_in = {i for i, _o, _g in adv["swaps"]}
    bench = sorted((p for p in sa["players"] if p not in sa["starters"] and pos_of.get(p) in gameday.SKILL),
                   key=lambda p: -ctx["proj"].get(p, 0.0))
    brows = "".join(
        f'<tr class="{"swap" if p in flag_in else ""}"><td class="two"><b>{_pname(p)}<span class="pos">{pos_of.get(p, "")}</span></b>'
        f'<span>{team_of.get(p, "")}</span></td>'
        f'<td class="num mut">{gameday.game_label(ctx["games"], team_of.get(p, ""), short=True)}</td>'
        f'{_risk_td(ctx, p)}<td class="num">{ctx["proj"].get(p, 0.0):.1f}</td>'
        f'<td>{_START_CHIP if p in flag_in else ""}</td></tr>'
        for p in bench)
    st.markdown(
        f'<div class="lockline"></div><div class="wk-cols">'
        f'<div><div class="weyebrow">What to do &middot; Week {aw}</div>{_todo_html(me, adv)}'
        f'<div class="weyebrow pad">Your bench</div><table class="dt">{brows}</table></div>'
        f'<div><div class="weyebrow">Your lineup as set on Sleeper</div>'
        f'{_lineup_rows(ctx, sa, flag=flag_out, show_actual=started)}</div></div>',
        unsafe_allow_html=True)
    with st.expander(f"{_team_of(sb['owner'])}'s lineup as set"):
        st.markdown(_lineup_rows(ctx, sb, show_actual=started), unsafe_allow_html=True)
    st.caption(f'As set: {adv["set_total"]:.1f} projected; best available {adv["best_total"]:.1f}. '
               "Projections from Sleeper; a player on bye projects 0. Players whose game has started "
               "stay where they are. " + _RISK_NOTE + " Win probability treats each lineup's total as a range, wider "
               "for riskier positions — Draft Room's model.")




# ------------------------------------------------------------- keeper outlook
# The Kreeper hub's "next year's keepers" screen on this league's engine: what
# each player on your roster would cost to keep next season, how the price
# climbs, and which you'd keep. Built off valueboard.rows, so the prices,
# owned-pick bumps and rookie-slot assignment are exactly the keeper board's.
def _surname(name: str) -> str:
    parts = [w for w in name.split() if w.rstrip(".") not in ("Jr", "Sr", "II", "III", "IV", "V")]
    return parts[-1] if parts else name


def _ladder_steps(r: dict) -> list:
    """[(season, price), ...] for keeping `r` every year he can be kept, then
    the wall. Rookie keepers have no clock. Shared by the keeper outlook and
    the contract cards on Home, so the two can never disagree."""
    nxt = SEASON + 1
    max_years = int(config.keeper_rules()["max_years"])
    if r.get("kind") == "rookie":
        return [(str(nxt), "R%d" % r["cost"]), ("then", "no clock")]
    y = int(r.get("year") or 1)
    anchor = r.get("drafted_round")
    steps = [(str(nxt), "R%d" % r["cost"])]
    for k in range(y + 1, max_years + 1):
        opts = engine.regular_options(anchor, k, r.get("adp"),
                                      from_rookie_draft=bool(r.get("from_rookie_draft")))
        rec = engine.recommended(opts) if opts else None
        steps.append((str(nxt + k - y), "ADP if it helps" if k >= 3 else ("R%d" % rec if rec else "&mdash;")))
    steps.append(("", "the wall" if y < max_years else "franchise or gone"))
    return steps


def _keeper_outlook_rows(owner: str) -> list:
    nxt = SEASON + 1
    kr = config.keeper_rules()
    max_years = int(kr["max_years"])
    pmap = players_map()
    rows = []
    for r in value_rows():
        if str(r["owner_id"]) != str(owner) or r.get("position") not in ("QB", "RB", "WR", "TE"):
            continue
        meta = pmap.get(str(r["player_id"])) or {}
        x = {"_pid": str(r["player_id"]), "name": r["name"], "Pos": r["position"],
             "adp": r.get("adp_rank"), "adp_rd": r.get("adp"), "nfl": meta.get("team") or "",
             "Rookie": r["kind"] == "rookie", "cost": r.get("cost"), "Value": r.get("surplus"),
             "ladder": [], "how": "", "blocked": ""}
        if not r.get("eligible") or not r.get("cost"):
            x["blocked"] = esc(r.get("reason") or "can't be kept")
            x["Value"] = None
        elif x["Rookie"]:
            x["ladder"] = [(str(nxt), "R%d" % r["cost"]), ("then", "no clock")]
            x["how"] = "Rookie keeper &middot; your last picks, no clock"
        else:
            y = int(r.get("year") or 1)
            anchor = r.get("drafted_round")
            x["ladder"] = _ladder_steps(r)
            x["how"] = ("Year %d%s%s" % (y, " &middot; from the rookie draft" if r.get("from_rookie_draft") else "",
                                        (" &middot; drafted R%d" % anchor) if anchor else " &middot; undrafted pickup"))
            if r.get("bumped"):
                x["how"] += " &middot; bumped to a pick you own"
        rows.append(x)

    # The slip: rookie slots from rookie-designated keepers, regular slots from
    # everyone else, best keeper value first.
    n_reg, n_rook = int(kr["regular"]), int(kr["rookie"])
    # A keeper worth less than the pick he costs isn't kept: leave the slot open.
    cands = [x for x in rows if x["Value"] is not None and x["Value"] > 0]
    rook = sorted((x for x in cands if x["Rookie"]), key=lambda x: -x["Value"])[:n_rook]
    reg = sorted((x for x in cands if not x["Rookie"]), key=lambda x: -x["Value"])[:n_reg]
    keep_ids = [x["_pid"] for x in rook + reg]
    for x in rows:
        x["verdict"] = "keep" if x["_pid"] in keep_ids else "blocked" if x["blocked"] else "cut"
        x["slot"] = "rookie" if x in rook else "regular"
    cuts = sorted((x for x in rows if x["verdict"] == "cut" and x["Value"] is not None), key=lambda x: -x["Value"])
    if cuts:
        cuts[0]["verdict"] = "next"
    order = {"keep": 0, "next": 1, "cut": 2, "blocked": 3}
    rows.sort(key=lambda x: (order[x["verdict"]], -(x["Value"] if x["Value"] is not None else -99)))
    return rows


def _headshot(pid: str) -> str:
    return (f'<img class="kh-img" src="https://sleepercdn.com/content/nfl/players/thumb/{pid}.jpg" '
            f'onerror="this.style.visibility=\'hidden\'" alt="">')


_VERDICT = {"keep": ("keep", "good"), "next": ("first out", "amber"), "cut": ("cut", ""),
            "blocked": ("blocked", "bad")}


def _keeper_card_html(r: dict) -> str:
    lab, tone = _VERDICT[r["verdict"]]
    steps = "".join(
        f'<span class="ks{" now" if i == 0 else ""}"><i>{yr}</i><b>{price}</b></span>'
        + ('<span class="ka">&rarr;</span>' if i < len(r["ladder"]) - 1 else "")
        for i, (yr, price) in enumerate(r["ladder"]))
    if r["blocked"]:
        steps = f'<span class="kb">{r["blocked"]}</span>'
    v = r["Value"]
    val = (f'<div class="kv {"good" if v > 0 else "bad" if v < 0 else ""}"><b>{v:+d}</b><i>value</i></div>'
           if v is not None else
           f'<div class="kv"><b>&mdash;</b><i>{"blocked" if r["blocked"] else "no ADP"}</i></div>')
    adp = f'{SEASON + 1} ADP R{r["adp_rd"]} (#{int(r["adp"])})' if r["adp"] else "no ADP"
    return (f'<div class="kcard2 {r["verdict"]}">{_headshot(r["_pid"])}<div class="kc-main">'
            f'<div class="kc-top"><b>{r["name"]}</b><span class="pos">{r["Pos"]} &middot; {r["nfl"] or "FA"}</span>'
            f'<span class="wchip {tone}">{lab}</span></div>'
            f'<div class="kladder">{steps}</div>'
            f'<div class="kc-how">{r["how"] or "&nbsp;"} &middot; {adp}</div></div>{val}</div>')


def _render_slip_outlook(me: str, on_slip: set) -> None:
    """What used to be the in-season "2027 Keepers" page, under the slip it
    duplicated: what the slip means for the rest of this season, and every
    player on the roster priced year by year. Keep / first-out / cut come from
    the slip above, so the two can never tell you different things."""
    nxt = SEASON + 1
    rows = _keeper_outlook_rows(me)
    if not rows:
        return
    for r in rows:
        if r["verdict"] != "blocked":
            r["verdict"] = "keep" if r["_pid"] in on_slip else "cut"
    cuts = sorted((r for r in rows if r["verdict"] == "cut" and r["Value"] is not None),
                  key=lambda r: -r["Value"])
    if cuts:
        cuts[0]["verdict"] = "next"
    order = {"keep": 0, "next": 1, "cut": 2, "blocked": 3}
    rows.sort(key=lambda r: (order[r["verdict"]], -(r["Value"] if r["Value"] is not None else -99)))
    keeps = [r for r in rows if r["verdict"] == "keep"]
    blocked = [r for r in rows if r["verdict"] == "blocked"]
    notes = []
    for b in blocked[:1]:
        notes.append(("&#8856;", f'{b["name"]} can\'t be kept in {nxt}',
                      f'{b["blocked"].replace("&middot;", "—")}. From here he\'s a rental, so his trade value only falls.',
                      "bad"))
    cheap = [r for r in keeps if (r["Value"] or 0) >= 25]
    if cheap:
        notes.append(("&#9678;", ", ".join(r["name"] for r in cheap[:3]),
                      "Cost a late pick and are worth an early one — build trades around them, don't sell them.",
                      "good"))
    nxt_out = next((r for r in rows if r["verdict"] == "next"), None)
    if nxt_out:
        notes.append(("!", f'{nxt_out["name"]} is the first one out',
                      f'{nxt_out["Value"]:+d} value. If a keeper above gets hurt or traded, he\'s the replacement.',
                      ""))
    notes.append(("$", "A waiver add keeps at your last pick",
                  "So a mid-season breakout is the cheapest keeper there is.", "good"))
    st.markdown('<div class="weyebrow pad">What this changes now</div>' + "".join(
        f'<div class="todo {c}"><span class="ic">{ic}</span><div><b>{t}</b><span>{s_}</span></div></div>'
        for ic, t, s_, c in notes), unsafe_allow_html=True)
    st.markdown(_ThemeShim.section_head("Your roster, <span class=\"g\">priced year by year</span>",
                                        "keep / first out / cut, straight off the slip above"),
                unsafe_allow_html=True)
    st.markdown('<div class="kgrid">' + "".join(_keeper_card_html(r) for r in rows) + "</div>",
                unsafe_allow_html=True)


@st.cache_data(ttl=900, show_spinner="Simulating the rest of the season…")
def get_playoff_outlook(me, week):
    return playoffs.outlook(league_id=config.league_id(), season=SEASON, week=week, me=me)


@st.cache_data(ttl=3600, show_spinner=False)
def get_playoff_slate(me, week, slots, weeks):
    return playoffs.playoff_slate(config.league_id(), SEASON, week, me, list(slots), list(weeks))


def _render_lit_bracket() -> None:
    """Both brackets as they stand, on one tilted plane. The top four play for
    the title; the bottom four are the Chase, and they are the ones that glow -
    in this league they play for the FAAB pot and for lottery balls."""
    try:
        rows = season.standings()
    except Exception:          # noqa: BLE001
        return
    if not rows or not any(r["results"] for r in rows):
        return
    cut = int(config.league()["playoff_teams"])

    def seat(r, i, cls):
        o = r["owner_id"]
        return (f'<div class="seat {cls}{" me" if o == VIEW else ""}" style="--dl:{i * .07:.2f}s">'
                f'<em>{r["place"]}</em>{_mgr_face(o)}<b>{esc(team_of(o))}</b>'
                f'<span>{esc(r["record"])} &middot; {r["points_for"]:,.0f}</span></div>')
    top = [r for r in rows if r["place"] <= cut]
    rest = [r for r in rows if r["place"] > cut]
    theme.bar("Both brackets", "as it stands &middot; top %d for the title, the rest for the pot" % cut)
    st.markdown('<div class="kx brk"><div class="brk-c"><span>The bracket</span>'
                + "".join(seat(r, i, "pot") for i, r in enumerate(top))
                + '</div><div class="brk-c cz"><span>The Chase &middot; FAAB pot + lottery balls</span>'
                + "".join(seat(r, i + len(top), "chase") for i, r in enumerate(rest))
                + '</div></div>', unsafe_allow_html=True)


@st.cache_data(ttl=300, show_spinner=False)
def _chase_points(weeks: tuple) -> dict:
    """{roster_id: points} summed over `weeks` - a Chase round is two weeks."""
    out = {}
    for wk in weeks:
        try:
            rows = sleeper.get_matchups(LG, int(wk), ttl=120) or []
        except Exception:      # noqa: BLE001
            continue
        for r in rows:
            out[int(r["roster_id"])] = out.get(int(r["roster_id"]), 0.0) + float(r.get("points") or 0)
    return out


def render_chase() -> None:
    """The Chase: the four teams that miss the playoffs, weeks 14-17, playing
    for the FAAB pot and for lottery balls. Before week 14 it is the bracket as
    Sleeper has it seeded today; from week 14 it is live, round by round."""
    s_ = playoffs._settings(LG)
    pw = list(s_["playoff_weeks"])
    rw = list(s_.get("round_weeks") or [2, 2])
    cur = season.current_week() or 1
    r2o = {int(r["roster_id"]): str(r.get("owner_id")) for r in sleeper.get_rosters(LG) or []}
    try:
        bracket = sleeper.get_losers_bracket(LG) or []
    except Exception:          # noqa: BLE001
        bracket = []
    rows = season.standings()
    spent = sum(r["spent"] for r in rows)
    cap = int(pot.cap_amount()[0])
    to_winner = min(spent, cap)
    started = cur >= pw[0] if pw else False
    weights = config.lottery_weights()
    cut = int(config.league()["playoff_teams"])
    chase_balls = list(weights[:len(rows) - cut])          # [lost out, third, runner-up, winner]

    st.markdown(_bh("royal", "The Chase · weeks %d–%d" % (pw[0], pw[-1]) if pw else "The Chase",
                    "$%d" % to_winner,
                    "to the Chase winner %s &mdash; and %d lottery balls instead of %d" % (
                        "right now" if spent < cap else "(the cap, full)",
                        chase_balls[-1] if chase_balls else 0, chase_balls[0] if chase_balls else 0)),
                unsafe_allow_html=True)
    if not started:
        st.markdown('<div class="tiny" style="margin:0 0 12px">The Chase starts in week %d. Until '
                    'then this is the bracket as Sleeper has it seeded <b>today</b> &mdash; the bottom '
                    'four of the table &mdash; and it moves every Sunday.</div>' % pw[0],
                    unsafe_allow_html=True)

    def round_weeks(r):
        a = sum(rw[:r - 1])
        return tuple(pw[a:a + rw[r - 1]]) if r - 1 < len(rw) else ()

    def team(rid, pts, won, live_):
        o = r2o.get(int(rid)) if rid else None
        if not o:
            return '<div class="ch-t tbd"><b>To be decided</b></div>'
        sc = ("%.1f" % pts) if live_ else ""
        return (f'<div class="ch-t{" w" if won else ""}{" me" if o == VIEW else ""}">{_mgr_face(o)}'
                f'<div><b>{esc(team_of(o))}</b><span>{esc(_first(o))} &middot; {_rec_of(o)}</span></div>'
                f'<em>{sc}</em></div>')

    names = {1: "Semi-final", 2: "Final"}
    for r in sorted({m["r"] for m in bracket}):
        wks = round_weeks(r)
        live_ = bool(wks) and cur >= wks[0]
        pts = _chase_points(wks) if live_ else {}
        done = bool(wks) and cur > wks[-1]
        theme.bar("Round %d · %s" % (r, names.get(r, "Round %d" % r)),
                  "weeks %s &middot; %s" % ("–".join(str(w) for w in (wks[0], wks[-1])) if wks else "?",
                                            "final" if done else "live" if live_ else "two weeks of points"))
        cards = []
        for m in sorted((m for m in bracket if m["r"] == r), key=lambda m: m.get("p") or 0):
            t1, t2 = m.get("t1"), m.get("t2")
            p1, p2 = pts.get(int(t1), 0.0) if t1 else 0.0, pts.get(int(t2), 0.0) if t2 else 0.0
            w = m.get("w")
            label = {1: "for the pot", 3: "for third"}.get(m.get("p"), "")
            stake = ""
            if m.get("p") == 1:
                stake = ("winner takes $%d and %d balls &middot; loser %d balls"
                         % (to_winner, chase_balls[-1], chase_balls[-2])) if len(chase_balls) >= 2 else ""
            elif m.get("p") == 3 and len(chase_balls) >= 4:
                stake = "winner %d balls &middot; loser %d balls" % (chase_balls[1], chase_balls[0])
            else:
                stake = "winner plays for the pot"
            cards.append(
                f'<div class="ch-m">{team(t1, p1, w and int(w) == int(t1 or -1), live_)}'
                f'<div class="ch-v">{label or "v"}</div>{team(t2, p2, w and int(w) == int(t2 or -1), live_)}'
                f'<div class="ch-s">{stake}</div></div>')
        st.markdown('<div class="kx ch-r">' + "".join(cards) + '</div>', unsafe_allow_html=True)

    _render_lit_bracket()
    st.markdown('<div class="tiny" style="margin-top:6px">The pot is every FAAB dollar bid this '
                'season; the Chase winner takes the first $%d of it and anything over the cap '
                'goes back into the payout. Balls are next year\'s lottery weight &mdash; winning '
                'the Chase costs you %d of them against losing out.</div>' % (
                    cap, (chase_balls[0] - chase_balls[-1]) if chase_balls else 0),
                unsafe_allow_html=True)


def render_playoffs() -> None:
    """The Draft Room's Playoffs tab: the rest of the season 10,000 times on the
    real schedule — your seed spread, win % each week, the biggest game, the
    league table and your starters' playoff-week matchups. The Chase bracket's
    money is on The Pot; this is only who gets in."""
    wk = season.current_week() or 1
    out = get_playoff_outlook(VIEW, wk)
    slate = None
    if VIEW and out["settings"]["playoff_weeks"]:
        try:
            slate = get_playoff_slate(VIEW, wk, tuple(out["settings"]["slots"]),
                                      tuple(out["settings"]["playoff_weeks"]))
        except Exception:  # noqa: BLE001 — a schedule hiccup must not take the page down
            slate = {"rows": []}
    playoffs_view.render(out, VIEW, who, slate,
                         pick_team_hint="Pick your team from the masthead to see where you finish.")


def render_week(leaf=None):
    {"live": render_live, "matchup": render_matchup,
     }.get(leaf or "live", render_live)()


def render_home(leaf=None):
    """The in-season front page.

    Ordered the way the question gets asked on a Sunday: who am I playing, what
    are the other games worth to me, where does that leave the table, what is
    the money doing, and what has everyone else been up to. Everything deeper
    has one home elsewhere - the lineup on Matchup, last week's story and the
    Game of the Week's tale of the tape on Live, the contracts on the Wire. The league votes used to live here and have come off - all
    four are called, and a settled rule belongs in the rulebook rather than on a
    running list of recent news. The results are still on the Rules page with
    the tallies intact.
    """
    cur = season.current_week()
    try:
        has_game = bool(cur and get_week_ctx(cur)["sides"].get(VIEW))
    except Exception:          # noqa: BLE001 - no weekly data: fall back, don't crash Home
        has_game = False
    render_keeper_deadline()
    if has_game:
        _render_home_my_week(VIEW, cur)
    else:
        my_card(VIEW)          # before kickoff there's no matchup to lead with
    render_taxi_deadline()
    if has_game:
        # The Game of the Week is the top row of Around the League rather than
        # a section of its own: same four games, one list, the biggest first.
        _render_around_league(cur, VIEW, cover=True)
    else:
        render_matchups()
    render_power()
    render_pot_strip()
    render_transactions()


# ---------------------------------------------------------------------------
# RULES  - the reference document
# ---------------------------------------------------------------------------

def render_block(kind, *rest) -> str:
    if kind == "p":
        return "<p>%s</p>" % rest[0]
    if kind == "list":
        return "<ul>%s</ul>" % "".join("<li>%s</li>" % i for i in rest[0])
    if kind == "note":
        return '<div class="banner" style="margin:0 0 14px">%s</div>' % rest[0]
    if kind == "table":
        headers, rows = rest
        head = "".join("<th>%s</th>" % h for h in headers)
        body = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % c for c in r) for r in rows)
        return "<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (head, body)
    if kind == "worked":
        title, lines = rest
        rows = "".join(
            '<div class="wr"><div class="l">%s</div><div class="v">%s</div>'
            '<div class="d">%s</div></div>' % (l, v, d) for l, v, d in lines)
        return '<div class="worked"><div class="wh">%s</div>%s</div>' % (title, rows)
    return ""


def render_settled_votes() -> None:
    """Every called vote, with the options that lost still attached.

    The rulebook carries the RULE. This carries how the room got to it: what
    the alternatives were, what each one would have meant, how the count fell,
    and who did not vote. A results line that says only "Week 12" throws away
    the reason Week 10 and Week 13 were on the ballot, which is the part
    somebody re-reading this in March actually needs.

    Driven off agenda.py rather than a hand-written table, so the questions and
    the answers cannot drift apart.
    """
    items = agenda.closed_items()
    if not items:
        return
    theme.bar("Put to a vote", "%s &middot; %s" % (agenda.settled_on(), agenda.turnout()))
    for it in items:
        opts = []
        for i, (label, note) in enumerate(it["options"]):
            won = (i == it["won"])
            opts.append(
                '<div class="o%s"><div class="lab">%s%s</div><div class="d">%s</div></div>' % (
                    " lead" if won else "", esc(label),
                    ' <span class="you">carried</span>' if won else "", note))
        st.markdown(
            '<div class="agenda"><div class="it">'
            '<div class="h"><span class="t">%s</span></div>'
            '<div class="why">%s</div><div class="opts">%s</div>'
            '<div class="foot"><b>%s</b> &mdash; %s. %s</div></div></div>' % (
                esc(it["title"]), it["why"], "".join(opts),
                esc(it["answer"]), esc(it["tally"]), it["verdict"]),
            unsafe_allow_html=True)


def render_rules(leaf=None):
    secs = rulebook.sections()
    theme.bar("The short version", "everything the engine enforces, in one screen")
    st.markdown('<div class="card">%s</div>' % "".join(
        '<div style="padding:11px 0;border-top:%s">'
        '<div style="font-weight:650;font-size:13.5px;margin-bottom:2px">%s</div>'
        '<div class="tiny" style="font-size:12.5px">%s</div></div>' % (
            "none" if i == 0 else "1px solid var(--line)", t, d)
        for i, (t, d) in enumerate(RULES_LEDGER)), unsafe_allow_html=True)
    theme.bar("The long version", "%d sections" % len(secs))
    st.markdown(
        '<div class="banner">This is the rulebook. Everything here is what the dashboard '
        'actually enforces — the numbers are read out of the same config the engine runs on, so '
        'the two cannot drift apart. It is our first season, so treat the last section as '
        'genuinely open.</div>', unsafe_allow_html=True)
    st.markdown('<div class="toc">%s%s</div>' % (
        "".join('<a href="#%s">%s</a>' % (a, esc(t)) for a, t, _, _ in secs),
        '<a href="#minutes-%s">Minutes</a>' % esc(minutes.latest().get("date", ""))
        if minutes.count() else ""), unsafe_allow_html=True)

    render_settled_votes()

    for anchor_id, title, stand, blocks in secs:
        theme.bar(title, "")
        st.markdown(
            '<div class="rule" id="%s"><div class="stand">%s</div>%s</div>' % (
                anchor_id, stand, "".join(render_block(*b) for b in blocks)),
            unsafe_allow_html=True)

    render_minutes()


def outline(items) -> str:
    """Nested list, kept at whatever depth it was written at."""
    return "<ul>%s</ul>" % "".join(
        "<li>%s%s</li>" % (line, outline(kids) if kids else "") for line, kids in items)


def render_minutes() -> None:
    """The other record of a meeting.

    The rulebook above says what was decided. This says what it was like, which
    is the one anybody will actually reread in three years. Transcribed verbatim
    - tidying somebody else's jokes is how you kill them.
    """
    if not minutes.count():
        return
    theme.bar("Minutes", "%d meeting%s &middot; verbatim" % (
        minutes.count(), "" if minutes.count() == 1 else "s"))
    for m in minutes.MEETINGS:
        st.markdown(
            '<div class="mins" id="minutes-%s"><div class="head">'
            '<div class="t"><small>%s</small>%s</div>'
            '<div class="by">minuted by %s</div></div>%s%s</div>' % (
                esc(m["date"]), esc(m["date"]), esc(m["title"]), esc(m["minuted_by"]),
                ('<div class="note">%s</div>' % m["note"]) if m.get("note") else "",
                outline(m["items"])), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# KEEPERS
# ---------------------------------------------------------------------------

def contract_path(draft_round, becomes):
    """Cost path for a player drafted in `draft_round` who plays like a
    round-`becomes` player from then on. Year 4 is the wall."""
    return [engine.recommended(engine.regular_options(draft_round, y, becomes))
            for y in (1, 2, 3)]


def three_year_surplus(draft_round, becomes):
    """Rounds of value banked over the full three-year run.

    Year three always prices at the market, so it contributes exactly nothing -
    which is the single most useful thing to know about this ruleset. All the
    profit is in years one and two.
    """
    return sum((c - becomes) for c in contract_path(draft_round, becomes) if c)


def render_keepers(leaf=None):
    kr = config.keeper_rules()
    # Only true before the draft: once rosters exist the slip below is priced
    # and this would contradict it - and on the Wire it was never the topic.
    if FIRST and leaf in (None, "matrix") and not _draft_done("veteran"):
        st.markdown(
            '<div class="banner"><b>Nothing to keep yet.</b> Your first slip is due after this '
            'season. What matters right now is the draft: where you take a player decides what he '
            'costs you to hold for the next three years, and the gap between that price and what '
            'he turns out to be worth is the only thing that ever makes a keeper worth a '
            'slot.</div>', unsafe_allow_html=True)

    if leaf in (None, "matrix"):
        st.markdown(
            '<div class="note" style="margin-bottom:12px">Rows are the round you draft him in. '
            'Columns are what he turns into. The cell is the rounds of value you bank across the '
            'whole three-year run, before he hits the wall. Two things fall out of it: a pick that '
            'performs exactly to its draft slot is worth <b>nothing</b> to keep, and year three is '
            'always priced at the market, so every rounds of profit you will ever make comes from '
            'years one and two.</div>', unsafe_allow_html=True)

        becomes_cols = [1, 2, 3, 5, 8]
        _n = config.keeper_rounds()
        grid = {(r, b): three_year_surplus(r, b) for r in range(1, _n + 1) for b in becomes_cols if b < r}
        _vmax = max([abs(v) for v in grid.values()] + [1])
        _best = max(grid.items(), key=lambda kv: kv[1], default=None)
        if _best:
            (_r, _b), _v = _best
            st.markdown(_bh("ink", "Where the value is · rounds banked over a three-year hold", theme.signed(_v),
                            f"rounds banked by an <b>R{_r}</b> pick who turns into an R{_b} — "
                            "a pick that plays to its slot banks nothing"), unsafe_allow_html=True)
        head = '<div class="hmx-r hd"><span>Drafted in</span>' + "".join(
            f"<span>becomes R{b}</span>" for b in becomes_cols) + "</div>"
        body = ""
        for r in range(1, _n + 1):
            cells = ""
            for b in becomes_cols:
                if b >= r:
                    cells += '<span class="hmx-c none">&middot;</span>'
                    continue
                v = grid[(r, b)]
                cells += (f'<span class="hmx-c" style="--h:{max(0.0, v) / _vmax:.2f}">'
                          f'{theme.signed(v)}</span>')
            body += f'<div class="hmx-r"><span class="hmx-t">R{r}</span>{cells}</div>'
        st.markdown(f'<div class="kx hmx">{head}{body}</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="tiny" style="margin-top:8px">Blank cells are players who never beat where '
            'you took them. Reading down any column shows the thesis: the later you find him, the '
            'more he is worth to hold - a round-3 player found in the 12th banks %d rounds, the same '
            'player taken in the 4th banks %d.</div>' % (
                three_year_surplus(12, 3), three_year_surplus(4, 3)), unsafe_allow_html=True)

        theme.bar("Who is actually there", "consensus board by round")
        c1, c2 = st.columns([1, 3])
        with c1:
            rd = st.number_input("Round", 1, config.veteran_rounds(), 8, key="board_round")
        with c2:
            pos_filter = st.multiselect("Positions", ["QB", "RB", "WR", "TE"],
                                        default=["QB", "RB", "WR", "TE"], key="board_pos")
        pool = [v for v in adp_board.by_round().get(int(rd), [])
                if (v.get("position") or "").upper() in pos_filter]
        if pool:
            breaks = max(1, int(rd) - 5)
            hold = contract_path(int(rd), int(rd))
            boom = contract_path(int(rd), breaks)
            st.markdown(
                '<div class="banner" style="margin-bottom:10px">Take one of these at R%d and hold '
                'him. If he stays an R%d player you pay <b>%s</b> and he was never worth a keeper '
                'slot. If he turns into an R%d player you pay <b>%s</b> - the year-two price drops to '
                'your draft round minus three the moment that is cheaper than his market - and you '
                'bank <b>%s rounds</b>.</div>' % (
                    rd, rd, " / ".join("R%s" % c for c in hold),
                    breaks, " / ".join("R%s" % c for c in boom),
                    theme.signed(three_year_surplus(int(rd), breaks))),
                unsafe_allow_html=True)
            ledger_table(
                ["Player", "Pos", "ADP", "Overall rank"],
                [['<div style="font-weight:650">%s</div>' % esc(v["name"]),
                  '<span class="chip">%s</span>' % esc(v["position"]),
                  '<span class="mono">%.1f</span>' % (v.get("adp") or 0.0),
                  '<span class="mono">%d</span>' % int(v["rank"])] for v in pool[:40]])
        else:
            st.markdown('<div class="banner">Nobody at those positions in round %d.</div>' % rd,
                        unsafe_allow_html=True)

        # ---- live slip (only once there is a roster to build one from) ----------

        # The grid above answers "which rounds are worth keeping". This
        # answers "what am I signing if I spend THIS one", which is the
        # question you have with a board in front of you.

        theme.bar("What this pick locks you into", "the draft is where keeper value is made")
        st.markdown(
            '<div class="note" style="margin-bottom:12px">The draft is offline, so this is the bit '
            'to have open next to the board. Pick the round you are about to spend and it shows the '
            'contract you are signing: what he costs to hold each year, and what you bank if he turns '
            'out better than where you took him.</div>', unsafe_allow_html=True)

        pick_round = st.slider("Round", 1, config.veteran_rounds(), min(9, config.veteran_rounds()),
                               key="draft_round")
        path = contract_path(pick_round, None)
        ladder = [
            ("Year 1", path[0], "the round you took him, or his market \u2014 whichever is cheaper"),
            ("Year 2", path[1], "R%d minus %d" % (pick_round, int(config.keeper_rules()["year2_bump"]))),
            ("Year 3", "ADP", "the market, no choice \u2014 which is why it banks nothing"),
            ("Year 4", "the wall", "gone unless he is your one franchise player"),
        ]
        st.markdown(
            '<div class="worked"><div class="wh">If you take him in round %d</div>%s</div>' % (
                pick_round, "".join(
                    '<div class="wr"><div class="l">%s</div><div class="v">%s</div>'
                    '<div class="d">%s</div></div>' % (
                        lbl, ("R%d" % v) if isinstance(v, int) else v, note)
                    for lbl, v, note in ladder)), unsafe_allow_html=True)

        lev = [(b, three_year_surplus(pick_round, b)) for b in (1, 2, 3, 5, 8)
               if b < pick_round]
        if lev:
            st.markdown(
                '<div class="card" style="margin-top:10px"><div class="eyebrow">If he outperforms</div>'
                '<div class="glance" style="grid-template-columns:repeat(%d,minmax(0,1fr));gap:10px">'
                '%s</div><div class="tiny" style="margin-top:10px">Rounds banked across the whole '
                'three-year hold. This is the argument for spending a late pick on upside rather than '
                'a safe floor: the same player is worth far more to hold if you found him late.</div>'
                '</div>' % (len(lev), "".join(
                    '<div style="text-align:center"><div style="font-family:var(--f-display);'
                    'font-weight:800;font-size:30px;color:var(--acc)">%s</div>'
                    '<div class="tiny">becomes an R%d</div></div>' % (theme.signed(v), b)
                    for b, v in lev)), unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="banner">A round-1 pick cannot outperform where you took him, so there is '
                'no keeper value in it at all. That is not a bug in the maths \u2014 it is the whole '
                'reason the early rounds are about winning now and the late rounds are about next '
                'year.</div>', unsafe_allow_html=True)

        here = adp_board.by_round().get(pick_round, [])[:12]
        if here:
            st.markdown(
                '<div class="tiny" style="margin:12px 0 6px">Who the market has in round %d</div>'
                '<div style="display:flex;gap:6px;flex-wrap:wrap">%s</div>' % (
                    pick_round, "".join(
                        '<span class="chip">%s <span style="opacity:.6">%s</span></span>' % (
                            esc(p["name"]), esc(p["position"])) for p in here)),
                unsafe_allow_html=True)
    if leaf in (None, "slip"):
        my_roster = next((r for r in (state["rosters"] or [])
                          if str(r.get("owner_id")) == VIEW), None)
        my_players = (my_roster or {}).get("players") or []
        if not my_players:
            theme.bar("Your slip", "%d regular · %d rookie · %d franchise" % (
                int(kr["regular"]), int(kr["rookie"]), int(config.franchise_rules()["slots"])))
            st.markdown(
                '<div class="banner">Your roster is empty, so there is no slip to submit. It opens '
                'after the %d season, when everyone has held someone for a year. The engine, the '
                'bump rule and the franchise optimiser are all wired and unit-tested — they just have '
                'nothing to price yet.</div>' % SEASON, unsafe_allow_html=True)
        else:
            pmap = players_map()
            hist = history.build(LG)
            owned = owned_map().get(VIEW, Counter())
            prices = []
            for pid in my_players:
                meta = pmap.get(str(pid)) or {}
                name = meta.get("full_name") or str(pid)
                adp = adp_board.adp_round_for_player(meta) if meta else None
                yr = hist.keeper_year(str(pid)) + 1
                dr = hist.draft_round(str(pid)) or config.keeper_rounds()
                from_rookie = hist.has_rookie_draft_provenance(str(pid))
                if hist.is_rookie_keeper_eligible(str(pid)):
                    prices.append(engine.price_rookie(
                        str(pid), name, meta.get("position") or "", slot=0,
                        last_round=config.keeper_rounds(), adp_round=adp))
                else:
                    # A rookie-draft player has no veteran round; the premium stands
                    # in for one and price_regular ignores draft_round entirely.
                    prices.append(engine.price_regular(
                        str(pid), name, meta.get("position") or "",
                        draft_round=hist.keeper_anchor(str(pid)) or dr, year=yr,
                        adp_round=adp, from_rookie_draft=from_rookie))
            value_rows()              # installs the keeper-value curve
            for p_ in prices:         # ...and value needs each player's ADP rank
                r_ = valueboard._market_rank(p_.player_id, pmap)
                if r_ < 1e9:
                    p_.adp_rank = r_
            engine.allocate(prices, owned)
            slip = engine.best_slip(prices)
            _tot = engine.total_surplus(slip)
            _best = max(slip, key=lambda p: p.surplus or -99, default=None)
            st.markdown(_bh("ink", "Your slip · %d keepers · %d regular, %d rookie, %d franchise" % (
                len(slip), int(kr["regular"]), int(kr["rookie"]), int(config.franchise_rules()["slots"])),
                            theme.signed(_tot),
                            "keeper value across the slip" + (
                                f' — <b>{esc(_best.name)}</b> at R{_best.final_round} is the best of it'
                                if _best and _best.final_round else ""),
                            photo=_best.player_id if _best else None), unsafe_allow_html=True)
            st.markdown("".join(contract_card(p) for p in slip), unsafe_allow_html=True)
            errs = engine.validate(slip)
            if errs:
                for e in errs:
                    st.markdown('<div class="banner" style="border-color:var(--bad);'
                                'color:var(--bad)">%s</div>' % esc(e), unsafe_allow_html=True)
            _render_slip_outlook(VIEW, {str(p_.player_id) for p_ in slip})


        # ---------------------------------------------------------------- value board
    if leaf in (None, "wire"):
        # Both destinations price off the same history, so build it once out
        # here - the wire needs it even when the rostered board is not shown.
        try:
            hist_all = history.build(LG)
            board = valueboard.rows(LG, SEASON, hist=hist_all)
        except Exception:
            hist_all, board = None, []

        if True:
            theme.bar("Value board", "what everyone would cost to keep next year")

            if board:
                scope = st.radio("Scope", ["Whole league", "Just my team"],
                                 horizontal=True, label_visibility="collapsed", key="vb_scope")
                shown = board if scope == "Whole league" else [
                    r for r in board if r["owner_id"] == VIEW]
                ranked = sorted(shown, key=lambda x: -(x["surplus"] if x["surplus"] is not None else -99))[:60]
                best5 = [r for r in ranked if r.get("eligible") and r.get("cost")
                         and r.get("surplus") is not None][:5]
                if best5:
                    st.markdown('<div class="weyebrow">%s &middot; tap one for the ladder</div>'
                                % ("The best contracts in the league" if scope == "Whole league"
                                   else "Your best contracts"), unsafe_allow_html=True)
                    st.markdown(_contract_flips_html(best5), unsafe_allow_html=True)
                shown_ids = {r["player_id"] for r in best5}
                ranked = [r for r in ranked if r["player_id"] not in shown_ids]
                if ranked:
                    st.markdown('<div class="weyebrow pad">Everyone else, by keeper value</div>',
                                unsafe_allow_html=True)
                vmax = max([abs(r["surplus"] or 0) for r in ranked] + [1])
                rows_vb = []
                for r in ranked:
                    tags = []
                    if r["kind"] == "rookie":
                        tags.append("rookie slot")
                    if r["from_rookie_draft"]:
                        tags.append("R%d premium" % engine.rookie_draft_premium())
                    if r["bumped"]:
                        tags.append("bumped")
                    if not r["eligible"]:
                        tags.append("wall")
                    sv = r["surplus"]
                    rows_vb.append(
                        f'<div class="wv{" me" if r["owner_id"] == VIEW else ""}">{_ph_img(r["player_id"], "xl-f")}'
                        f'<div class="wv-n"><b>{esc(r["name"])}</b><span>{esc(r["position"])} &middot; {esc(team_of(r["owner_id"]))}</span></div>'
                        f'<div class="wv-c"><b>{"R%d" % r["cost"] if r["cost"] else "&mdash;"}</b>'
                        f'<span>{_dtxt(r)} &middot; market {"R%d" % r["adp"] if r["adp"] else "&mdash;"}</span></div>'
                        f'<div class="wv-b"><i class="{"neg" if (sv or 0) < 0 else ""}" style="width:{max(3, 100 * abs(sv or 0) / vmax):.0f}%"></i></div>'
                        f'<em class="{"neg" if (sv or 0) < 0 else ""}">{theme.signed(sv)}</em>'
                        f'<span class="wv-t">{" &middot; ".join(tags)}</span></div>')
                st.markdown('<div class="kx">' + "".join(rows_vb) + "</div>", unsafe_allow_html=True)
                st.markdown(
                    '<div class="tiny" style="margin-top:8px">Sorted by keeper value &mdash; his '
                    'talent minus what his cost round\'s pick would actually land once every '
                    'team\'s keepers are off the board, so an elite player kept early counts too. A '
                    'drafted player keeps at <b>the round he was drafted in</b>, so his price no '
                    'longer moves with ADP and the two columns say genuinely different things. '
                    'Market is next summer\'s ADP, projected from FantasyCalc\'s trade market &mdash; '
                    'dynasty and redraft value averaged, dynasty alone for a player on IR or out for '
                    'the year &mdash; with the preseason board for anyone it doesn\'t price. Prices include the bump, so they are true in the context of the rest '
                    'of that manager\'s slip.</div>', unsafe_allow_html=True)
            else:
                st.markdown(
                    '<div class="banner"><b>Nobody is on a roster yet.</b> The moment the veteran draft '
                    'ends this fills with every player in the league, priced for whoever holds him and '
                    'sorted by keeper value \u2014 which is the thing worth checking before you spend FAAB in '
                    'week 6, because a claim here is the first year of a three-year contract.</div>',
                    unsafe_allow_html=True)

        # The cheap list is the tail of the same board, off the same history
        # build - it was never worth its own tap.
        if (not FIRST or (state["rosters"]
                          and any(r.get("players") for r in state["rosters"]))):
            theme.bar("Cheapest available", "unrostered, priced as if you claimed him today")
            try:
                fa = valueboard.free_agents(LG, limit=20, hist=hist_all)
            except Exception:
                fa = []
            ledger_table(["Player", "Would keep at", "Market", "Surplus", ""], [[
                '<div style="font-weight:650">%s</div><div class="tiny">%s</div>' % (
                    esc(f["name"]), esc(f["position"])),
                '<span class="mono">R%d</span>' % f["cost"],
                '<span class="mono">R%d</span>' % f["adp"],
                '<span class="surplus %s">%s</span>' % (
                    theme.surplus_class(f["surplus"]), theme.signed(f["surplus"])),
                ('<span class="chip warn">carries R%d</span>' % f["cost"]) if f["carried"]
                else '<span class="chip good">never drafted here</span>',
            ] for f in fa])
            st.markdown(
                '<div class="tiny" style="margin-top:8px">Only a player who has <b>never been drafted '
                'in this league</b> is genuinely cheap \u2014 he keeps at your last available round. '
                'Anyone who has been drafted here carries that round and his clock straight onto your '
                'roster, because dropping a player does not launder his keeper price. A 2nd-rounder '
                'somebody cut in a bye week is still a 2nd-round keeper.</div>',
                unsafe_allow_html=True)
            _render_bid_helper()

        # ---------------------------------------------------------------- franchise
    # The tag is a decision made about the same five slots, so it belongs on the
    # slip rather than a page of its own.
    if leaf in (None, "slip"):
        try:
            hist_all = history.build(LG)
        except Exception:
            hist_all = None
        theme.bar("Franchise tag", "one player, years %d and %d, price frozen" % (
            int(kr["max_years"]) + 1, int(kr["max_years"]) + int(config.franchise_rules()["extra_years"])))
        try:
            cands = valueboard.franchise_candidates(VIEW, LG, hist=hist_all)
        except Exception:
            cands = []
        if cands:
            best = cands[0]

            def contract(c):
                tagged = c is best and c["banked"] > 0 and c["at_the_wall"]
                # The recommended tag gets the stamp: it presses down the Z
                # axis and the row shakes, because this is a once-ever call.
                stamp = ('<div class="stamp"><b>R%d</b><span>Franchise</span></div>' % c["frozen"]
                         if tagged else "")
                return (
                    '<div class="contract %s"><div class="who">'
                    '<div class="nm">%s <span class="tiny">%s</span></div>'
                    '<div class="meta">%s &#183; frozen at R%d &#183; market R%d</div>'
                    '<div class="tags2">%s<span class="chip">Freeze R%d</span>'
                    '<span class="chip">ADP R%d</span></div></div>'
                    '<div class="price"><div class="rd" style="color:%s">%s</div>'
                    '<div class="sub">rds over yr %d-%d</div></div>%s</div>' % (
                        ("fr frs go" if tagged else "fr") if c is best and c["banked"] > 0 else "",
                        esc(c["name"]), esc(c["position"]),
                        ("year %d \u2014 at the wall" % c["year"]) if c["at_the_wall"]
                        else "year %d \u2014 not eligible until year %d" % (
                            c["year"], int(kr["max_years"]) + 1),
                        c["frozen"], c["adp"],
                        '<span class="chip solid">Tag this one</span>' if tagged else "",
                        c["frozen"], c["adp"],
                        "var(--good)" if c["banked"] > 0 else "var(--dim)",
                        theme.signed(c["banked"]), int(kr["max_years"]) + 1,
                        int(kr["max_years"]) + int(config.franchise_rules()["extra_years"]),
                        stamp))
            if not any(c["at_the_wall"] for c in cands):
                first_tag = SEASON + int(kr["max_years"]) + 1
                st.markdown(
                    '<div class="frs go"><div class="stamp"><b>%d</b><span>first tag</span></div>'
                    '<div class="banner" style="padding-right:140px;margin-bottom:10px"><b>Nobody here is '
                    'at the wall yet.</b> The tag only works on a player who has already been kept %d '
                    'times, so the first one anybody can use is in %d. These are the players who would '
                    'bank the most from it, if their clocks ran that far.</div></div>'
                    % (first_tag, int(kr["max_years"]), first_tag), unsafe_allow_html=True)
            st.markdown("".join(contract(c) for c in cands[:6]), unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="frs go"><div class="stamp"><b>%d</b><span>first tag</span></div>'
                '<div class="banner" style="padding-right:140px"><b>Nobody is eligible, and nobody will be until %d.</b> The tag '
                'only does anything for a player who has already been kept three times, so the first '
                'real decision is four offseasons away. What it will rank then is which of your '
                'year-four players banks the most, and the answer is counterintuitive: the freeze is '
                'at the <em>most expensive</em> round you ever paid, so the tag is worth the most on a '
                'late find whose market ran away from him and exactly nothing on a career '
                'first-rounder.</div></div>' % (SEASON + int(kr["max_years"]) + 1, SEASON + int(kr["max_years"]) + 1),
                unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# TAXI BAY
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# THE POT
# ---------------------------------------------------------------------------

def render_pot(leaf=None):
    fr = config.faab_rules()
    # Page-level: settlement is what both the burn-down and the ledger read.
    spends = {}
    try:
        spends = pot.spend_from_rosters(LG)
        try:
            traded = pot.traded_net(LG)
        except Exception:
            traded = {}
    except Exception:
        spends = {}
    spends = {o: spends.get(o, 0) for o in owner_ids()}
    settlement = pot.settle(spends, traded=traded)
    complete = (lg.get("status") or "") == "complete"

    if leaf in (None, "pot"):
        if complete:
            theme.bar("The pot", "what you bid is what you owe")
        played = sum(b.spent for b in settlement.bills) > 0

        if FIRST:
            st.markdown(
                '<div class="banner"><b>No pot in year one.</b> It needs a full season of FAAB '
                'data to settle against, so nothing is billed until the %d offseason. The running '
                'total still tracks live all season &mdash; the height of your line <em>is</em> '
                'the bill, and it is worth watching from week one.</div>' % (SEASON + 1),
                unsafe_allow_html=True)

        if complete:
            glance([
                {"pct": 1.0, "color": "var(--bad)", "big": "$%d" % settlement.total,
                 "label": "Comes due", "note": "every dollar bid, all 8 teams"},
                {"pct": settlement.to_chase / max(1, settlement.cap), "color": "var(--acc)",
                 "big": "$%d" % settlement.chase_total,
                 "label": "To the Chase winner",
                 "note": "$%d capped at the third-place prize, plus $%d of overflow &mdash; "
                         "the same as third place takes home" % (
                             settlement.to_chase, settlement.to_chase_bonus)},
                {"pct": 1.0 if settlement.overflow else 0.0, "color": "var(--acc2)",
                 "big": "$%d" % settlement.overflow,
                 "label": "Back to the bracket",
                 "note": "above the cap \u2014 $%d / $%d / $%d / $%d to champion, runner-up, "
                         "third and the Chase winner" % (
                             settlement.to_champion, settlement.to_second,
                             settlement.to_third, settlement.to_chase_bonus)},
                {"pct": 1.0, "color": "var(--acc2)", "big": "$%d" % int(fr["budget"]),
                 "label": "Budget each",
                 "note": "before any FAAB changed hands by trade"},
            ])
        else:
            spent_total = sum(b.spent for b in settlement.bills)
            pool = int(fr["budget"]) * len(settlement.bills)
            _ovr = config.overflow_split()
            cap = int(settlement.cap)
            to_chase = min(spent_total, cap)
            over = max(0, spent_total - cap)
            mine = next((b for b in settlement.bills if b.owner_id == VIEW), None)
            budget = int(fr["budget"])
            # The pot fills against the WHOLE pool, not against the cap. Scaled
            # to the cap it pins full the moment the cap is met and then tells
            # you nothing for the rest of the season.
            _bidders = sum(1 for b in settlement.bills if b.spent > 0)
            st.markdown(_bh(
                "ink", "The pot · what you bid is what you owe", f"${spent_total}",
                "in the pot — " + (f"all of it to the <b>Chase</b> winner, capped and full" if to_chase >= cap
                                   else f"the first ${cap} goes to the <b>Chase</b> winner"),
                grid=[("Chase takes", f"${to_chase}", "capped · full" if to_chase >= cap else f"of the ${cap} cap"),
                      ("Overflow", f"${over}", ("splits %d/%d/%d/%d into the bracket" % (
                          int(_ovr["first"]), int(_ovr["second"]), int(_ovr["third"]), int(_ovr["chase"])))
                       if over else "nothing above the cap yet"),
                      ("Your bill", f"${mine.owed if mine else 0}", f"of your ${budget}"),
                      ("Teams bidding", str(_bidders), f"of {len(settlement.bills)}")]),
                unsafe_allow_html=True)
            # The vessel: every spender's coin drops in, biggest first; it fills
            # against the whole pool, with the Chase cap marked on the glass.
            spenders = sorted((b for b in settlement.bills if b.spent > 0), key=lambda b: -b.spent)
            if spenders:
                # Scaled to twice the cap rather than the whole pool: against
                # $800 the first $135 is a puddle, and the cap - the line that
                # actually decides where money goes - sits on the floor.
                room = min(pool, max(2 * cap, int(spent_total * 1.25)))
                lvl = min(100.0, 100.0 * spent_total / max(1, room))
                cap_at = min(100.0, 100.0 * cap / max(1, room))
                spill = min(70, 18 + int(140 * over / max(1, pool))) if over else 0
                coins = "".join(
                    f'<div class="coin" style="--dl:{.2 + i * .28:.2f}s">{_mgr_face(b.owner_id)}'
                    f'<b>${b.spent}</b>{esc(_first(b.owner_id))}</div>'
                    for i, b in enumerate(spenders[:8]))
                st.markdown(
                    f'<div class="kx vbox"><div class="coins">{coins}</div>'
                    f'<div class="vessel"><div class="vs-in"><div class="glassv"><div class="fillv" style="--lvl:{lvl:.0f}%"></div></div>'
                    f'<div class="capv" style="bottom:{cap_at:.0f}%"><span>${cap} Chase cap</span></div>'
                    f'<div class="spill" style="--sp:{spill}px"></div></div></div>'
                    f'<div class="vnote"><b>${spent_total}</b>of the ${pool} anyone could spend. '
                    + (f'The Chase winner&rsquo;s ${cap} is full and <b style="display:inline;font-size:inherit;'
                       f'font-family:inherit;color:var(--kg)">${over}</b> has run over into the bracket.'
                       if over else f'Everything up to the dashed line goes to the Chase winner; past it, it '
                                    f'spills into the bracket.')
                    + '</div></div>', unsafe_allow_html=True)
            # (this used to say "nobody has bid yet" whatever the pot held)
            if spent_total == 0:
                st.markdown(
                    '<div class="tiny" style="margin-top:8px">Nobody has bid yet, so the pot is '
                    'empty and the "owed" column below is zero for everyone. It fills as claims '
                    'land.</div>', unsafe_allow_html=True)

        theme.bar("Into the pot", "week 1 \u2192 %d &middot; what each has bid, running total" % WEEKS)
        try:
            weekly = pot.weekly_spend(LG, list(range(1, WEEKS + 1)))
            curves = pot.running_total(weekly)
        except Exception:
            curves = {}
        if any(any(v) for v in curves.values()):
            worst = max(settlement.bills, key=lambda b: b.owed).owner_id
            series = []
            for oid in owner_ids():
                key = oid in (VIEW, worst)
                series.append({
                    "name": who(oid).split(" ")[0] + " " + who(oid).split(" ")[-1][:1],
                    "values": curves.get(oid) or [0],
                    "colour": ("var(--acc)" if oid == VIEW else
                               "var(--bad)" if oid == worst else "var(--dim)"),
                    "key": key})
            st.markdown('<div class="card">%s</div>' % theme.burndown(
                series, int(fr["budget"]), WEEKS), unsafe_allow_html=True)
            st.markdown(
                '<div class="tiny" style="margin-top:8px">The gap between a line and the ceiling in '
                'the final week <em>is</em> the bill. Flat lines are the tell.</div>',
                unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="banner">Nothing to plot yet \u2014 waivers open in week 2. From then on '
                'this draws every team\'s cumulative spend against the $%d ceiling, and the gap '
                'above your line at week %d is what you will owe.</div>' % (
                    int(fr["budget"]), WEEKS), unsafe_allow_html=True)

    # Settlement is where the burn-down ends up; two views of one pot.
    if leaf in (None, "pot"):
        theme.bar("Settlement", "who owes what")
        _bud = max(1, int(fr["budget"]))
        rows = "".join(
            f'<div class="sp{" me" if b.owner_id == VIEW else ""}"><b>{esc(who(b.owner_id))}</b>'
            f'<div class="sp-b"><i class="live" style="width:{min(100, 100 * b.spent / _bud):.0f}%"></i></div>'
            f'<em>${b.owed}</em><span>owed &middot; ${b.spent} bid</span></div>'
            for b in sorted(settlement.bills, key=lambda b: -b.owed))
        st.markdown('<div class="kx">' + rows + "</div>", unsafe_allow_html=True)

        _ov = config.overflow_split()
        st.markdown(
            '<div class="banner" style="margin-top:12px"><b>The cap is a ceiling, not a discount.</b> '
            'Every dollar you bid comes due. The first <b>$%d</b> goes to whoever wins the Chase '
            'bracket &mdash; that is the third-place prize. Everything above it is split '
            '<b>%d/%d/%d/%d</b> between the champion, the runner-up, third place and the Chase '
            'winner, so a low-spend year lifts the whole bracket rather than one person. The '
            'arithmetic lands somewhere neat: once the pot clears the cap the Chase winner and '
            'third place take home <b>exactly the same amount</b>, and below it the Chase winner '
            'takes the whole smaller pot. The consolation ties a playoff finish at best and '
            'never beats one.</div>' % (
                settlement.cap, int(_ov["first"]), int(_ov["second"]),
                int(_ov["third"]), int(_ov["chase"])),
            unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# DRAFT
# ---------------------------------------------------------------------------


def board_note(kind: int, drawn: bool) -> None:
    """Say which of the three things this board is showing.

    The drum draws a SELECTION order - who picks a slot first - and first choice
    takes any spot they want. So there are three states, and conflating them is
    how you get somebody arguing that the board is wrong: the slots people
    actually chose, the drum order standing in before they have, or nothing at
    all.
    """
    chosen = _live_order(kind)
    if chosen:
        st.markdown(
            '<div class="tiny" style="margin-bottom:8px">These are the slots managers '
            '<b>actually chose</b>, straight off Sleeper. The drum decided who picked a slot '
            'first, not who picks where &mdash; so this is not meant to match the draw.</div>',
            unsafe_allow_html=True)
    elif drawn:
        st.markdown(
            '<div class="tiny" style="margin-bottom:8px">Standing in the drum\'s <b>selection '
            'order</b> until managers pick their slots. First choice can take any spot on the '
            'board, so this will change.</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="banner">No drum and no board yet &mdash; this is config order. Draw it '
            'on <b>Pre-Season &rsaquo; Lottery</b>.</div>', unsafe_allow_html=True)


def _live_order(kind: int) -> List[str]:
    """The slot order Sleeper is actually running, if it has one."""
    try:
        s = live.state(kind, LG)
    except Exception:
        return []
    order = s.get("order") or []
    return [str(o) for o in order] if order and all(order) else []


def live_draft(kind: int) -> None:
    """The board while it is running.

    A 24-hour pick clock makes the draft a fortnight-long background event, so
    the two things worth putting at the top are whose pick it is and how long
    they have left. Everything below it is the board as drawn.
    """
    try:
        s = live.state(kind, LG)
    except Exception:
        return
    if not s:
        return

    for warn in live.disagreements(s, kind):
        st.markdown('<div class="banner" style="border-color:var(--bad);color:var(--bad)">'
                    '<b>Sleeper and the rulebook disagree.</b> %s Sleeper is what the league '
                    'actually drafts on, so it wins until somebody changes it.</div>' % warn,
                    unsafe_allow_html=True)

    if s["status"] == "pre_draft":
        st.markdown('<div class="tiny" style="margin-bottom:8px">Not started on Sleeper yet.</div>',
                    unsafe_allow_html=True)
        return

    # Count against what the LEAGUE is running, not what Sleeper is set to.
    if s["stop_now"]:
        st.markdown(
            '<div class="clockcard late"><div class="l"><div class="k">Stop the draft</div>'
            '<div class="w">All %d picks are in</div>'
            '<div class="tm">Pause it on Sleeper &mdash; anything from here is not a pick in '
            'this league, and the boards below ignore it.</div></div>'
            '<div class="r"><div class="k">Overrun</div><div class="v">%d</div>'
            '<div class="tm">picks past the rulebook</div></div></div>' % (
                s["league_total"], s["voided"]), unsafe_allow_html=True)
    elif s["on_clock"]:
        left = live.countdown(s["deadline"])
        late = left.startswith("on the clock past")
        st.markdown(
            '<div class="clockcard%s"><div class="l">'
            '<div class="k">On the clock</div><div class="w">%s</div>'
            '<div class="tm">%s</div></div>'
            '<div class="r"><div class="k">Pick</div><div class="v">%d.%02d</div>'
            '<div class="tm">%d of %d made</div></div></div>' % (
                " late" if late else "", esc(who(s["on_clock"])),
                esc(team_of(s["on_clock"])), s["round"], s["pick"],
                s["made"], s["league_total"]),
            unsafe_allow_html=True)
        bits = [esc(left) if left else "no pick timer set"]
        if s["last_before_stop"]:
            bits.append("<b>last pick before you pause it</b>")
        st.markdown('<div class="tiny" style="margin:6px 0 10px;color:%s">%s</div>' % (
            "var(--bad)" if late else "var(--warn)", " &middot; ".join(bits)),
            unsafe_allow_html=True)
    elif s["made"] >= s["league_total"] and s["league_total"]:
        st.markdown('<div class="banner" style="border-color:var(--good)"><b>Draft complete.</b> '
                    'All %d picks are in.</div>' % s["league_total"], unsafe_allow_html=True)

    picked = live.slots_chosen(s, kind)
    if picked and any(p for _, _, p in picked):
        theme.bar("Who took what", "the drum picked the order &middot; they picked the spot")
        ledger_table(["Slot", "Manager", "Drum"], [[
            '<span class="mono">%d</span>' % slot,
            '<div style="font-weight:650">%s</div><div class="tiny">%s</div>' % (
                esc(who(owner)), esc(team_of(owner))),
            ('<span class="chip acc">%s choice</span>' % ordinal(pos)) if pos
            else '<span class="tiny">&mdash;</span>',
        ] for slot, owner, pos in picked],
            me_row=next((i for i, (_, o, _) in enumerate(picked) if o == VIEW), None))

    got = live.rows(s, players_map())
    if got:
        theme.bar("Picks so far", "newest first")
        ledger_table(["Pick", "Player", "To"], [[
            '<span class="mono">%d.%02d</span>' % (r["round"], r["pick"] or 0),
            '<div style="font-weight:650">%s</div><div class="tiny">%s%s</div>' % (
                esc(r["name"]), esc(r["position"]),
                (" &middot; " + esc(r["team"])) if r["team"] else ""),
            '<span class="tiny">%s</span>' % esc(who(r["owner_id"]) if r["owner_id"] else "&mdash;"),
        ] for r in got[:40]])


@st.cache_resource(show_spinner=False)
def _voice_component():
    """A real component, so the transcript arrives over the websocket Streamlit
    already has open instead of by navigating the page. Cached because
    declare_component registers a route and must not run twice."""
    return components.declare_component(
        "hm_voice", path=str(Path(__file__).resolve().parent / "halfmen" / "components" / "voice"))


def player_pool() -> List[dict]:
    """Everyone draftable, once. Built from Sleeper's map, skinny on purpose -
    this list is searched on every keystroke in a room full of people."""
    try:
        pmap = players_map()
    except Exception:
        pmap = {}
    out = []
    for pid, m in (pmap or {}).items():
        pos = (m.get("position") or "").upper()
        if pos not in ("QB", "RB", "WR", "TE"):
            continue
        if not m.get("full_name") or not m.get("team"):
            continue
        out.append({"id": str(pid), "name": m["full_name"], "position": pos,
                    "team": m.get("team") or ""})
    out.sort(key=lambda r: r["name"])
    return out


def draft_room(leaf=None) -> None:
    """Eight people round a table, one screen, one pick at a time.

    No ADP, no suggestions, no rankings - somebody walks up, says or types a
    name, and it goes on the board. Everything here is the record: picks are
    written to the season blob, which the value board and every keeper price
    read from.
    """
    kind = picks.VETERAN
    rounds = config.veteran_rounds(SEASON)
    snake = bool(config.drafts().get("snake", True))
    order = (_live_order(live.VETERAN) or config.veteran_slots()
             or first_draw().get("veteran") or owner_ids())

    made = len(picks.load(kind, SEASON))
    total = rounds * len(order)
    live_board = made < total
    theme.bar("Draft room", "%d rounds &middot; %d picks &middot; %s" % (
        rounds, total,
        "live &middot; refreshing every %ds" % _ROOM_POLL if live_board
        else "complete &middot; this app is the record"))
    (room_live if live_board else room_done)(kind, order, rounds, snake)


# How often an open draft room repaints itself for everyone watching.
#
# Deliberately a shade longer than remote._TTL (5s), so the process-wide read
# cache absorbs the whole room: eight people polling on their own timers still
# cost one GitHub read per cache window, not eight. Babies and Boomer ran this
# at 5s with no cache in front of it and burned the 5,000/hour REST quota - per
# GitHub USER, shared across every token - in minutes on draft night, which
# blanked the board for the rest of the hour.
#
# Only an UNFINISHED board polls. See draft_room.
_ROOM_POLL = 6


def save_or_say(what: str, fn, *args, **kwargs) -> bool:
    """Run a write that goes to GitHub, and SAY SO when it fails.

    Every one of these used to raise straight through the fragment, which in
    Streamlit means the board vanishes for that viewer until something else
    triggers a rerun - during a live draft, with eight people watching, and
    with no clue that the pick did not land.

    Throttling is the realistic cause: the REST quota is per GitHub user and a
    room full of refreshes eats it. The board itself keeps rendering from cache,
    so the right answer is to keep the page up and tell whoever pressed the
    button what to do next.
    """
    try:
        fn(*args, **kwargs)
        return True
    except Exception as exc:
        st.error(
            "Couldn't save %s \u2014 GitHub is throttling writes. The board stays live and "
            "nothing already recorded is lost. Write this one down and log it again in a "
            "minute. (%s)" % (what, type(exc).__name__))
        return False


@st.fragment(run_every=_ROOM_POLL)
def room_live(kind, order, rounds, snake) -> None:
    """The open board, repainting itself every few seconds for the whole room.

    Without this only the person who entered the pick saw it land; everyone
    else sat on a stale board until they touched something. `run_every` is what
    makes it a shared screen rather than eight private ones.
    """
    room_body(kind, order, rounds, snake)


def room_done(kind, order, rounds, snake) -> None:
    """The finished board. Same render, no polling - a completed draft cannot
    change, and a page that reruns every few seconds forever is a page that
    keeps asking GitHub about a file nobody is writing."""
    room_body(kind, order, rounds, snake)


def room_body(kind, order, rounds, snake) -> None:
    """Clock, entry and board, all in one fragment.

    Everything that changes when a pick lands lives in here, so
    `st.rerun(scope="fragment")` repaints exactly this and leaves the masthead,
    the nav and the rest of the page alone. Together with the voice component
    handing its transcript back over the websocket, entering a pick stopped
    being a page load and became a small update to the part that changed.
    """
    made = picks.load(kind, SEASON)
    taken = {str(p["player_id"]) for p in made}
    seats = picks.board_seats(order, rounds, snake)
    seat = seats[len(made)] if len(made) < len(seats) else None
    unlocked = room_unlocked()

    if seat is None:
        st.markdown('<div class="banner" style="border-color:var(--good)"><b>Draft complete.</b> '
                    'All %d picks are in.</div>' % len(seats), unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="clockcard"><div class="l"><div class="k">On the clock</div>'
            '<div class="w">%s</div><div class="tm">%s</div></div>'
            '<div class="r"><div class="k">Pick</div><div class="v">%s</div>'
            '<div class="tm">%d of %d &middot; round %d %s</div></div></div>' % (
                esc(who(seat["owner_id"])), esc(team_of(seat["owner_id"])), seat["label"],
                len(made), len(seats), seat["round"],
                "&larr; snaking back" if (snake and seat["round"] % 2 == 0) else "&rarr;"),
            unsafe_allow_html=True)

    if seat is not None:
        if not unlocked:
            room_lock_ui()
        else:
            room_controls(kind, order, rounds, snake, made, taken)
        storage_note()

    room_board(kind, order, rounds, snake)


def rerun_here() -> None:
    """Repaint the fragment if we are inside a fragment rerun, else the page.

    `st.rerun(scope="fragment")` is only legal DURING a fragment rerun - on the
    first full script run that happens to render the fragment it raises, which
    means the very first pick of the night would have thrown rather than
    landing. Try the cheap repaint, fall back to the whole page.
    """
    try:
        st.rerun(scope="fragment")
    except Exception:
        st.rerun()


def room_controls(kind, order, rounds, snake, made, taken) -> None:
    """Say it or type it. Called from inside the fragment, so every path here
    reruns the fragment rather than the page."""
    pool = player_pool()

    said = _voice_component()(key="hm_voice", default=None)
    if said and said.get("seq") != st.session_state.get("voice_seq"):
        st.session_state["voice_seq"] = said.get("seq")
        heard = said.get("text", "")
        got = voice.match(heard, pool, exclude=taken)
        if got and got["sure"]:
            if save_or_say("that pick", picks.add, kind, got["player"],
                           order, rounds, snake, SEASON):
                rerun_here()
        elif got:
            st.session_state["room_pick"] = got["player"]["name"]
            st.markdown('<div class="heardline"><span class="k">Heard</span>&ldquo;%s&rdquo; '
                        '&rarr; <b>%s</b> &mdash; not sure enough, confirm below.</div>' % (
                            esc(heard), esc(got["player"]["name"])), unsafe_allow_html=True)
        else:
            st.markdown('<div class="heardline bad"><span class="k">Heard</span>&ldquo;%s&rdquo; '
                        '&mdash; no match. Say the surname again, or type it.</div>'
                        % esc(heard), unsafe_allow_html=True)

    labels = {"%s  \u00b7  %s %s" % (p["name"], p["position"], p["team"]): p
              for p in pool if p["id"] not in taken}
    keys = list(labels)
    pre = st.session_state.pop("room_pick", None)
    idx = next((i for i, k in enumerate(keys) if k.startswith(pre + "  \u00b7")), None) \
        if pre else None
    chosen = st.selectbox("Player", keys, index=idx,
                          placeholder="Say the name, or start typing\u2026",
                          label_visibility="collapsed", key="room_search_%d" % len(made))
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("Lock it in", type="primary", disabled=not chosen,
                     use_container_width=True):
            if save_or_say("that pick", picks.add, kind, labels[chosen],
                           order, rounds, snake, SEASON):
                rerun_here()
    with c2:
        if st.button("Undo last pick", disabled=not made):
            if save_or_say("the undo", picks.undo, kind, SEASON):
                rerun_here()


def room_board(kind, order, rounds, snake) -> None:
    """The grid. Split out so the fragment can repaint it without the page."""
    made = picks.load(kind, SEASON)
    seats = picks.board_seats(order, rounds, snake)
    seat = seats[len(made)] if len(made) < len(seats) else None
    st.markdown('<div class="poskey">%s</div>' % "".join(
        '<span><i style="background:var(--%s)"></i>%s</span>' % (p.lower(), p)
        for p in ("QB", "RB", "WR", "TE")), unsafe_allow_html=True)

    by_seat = {}
    for i, p in enumerate(made):
        by_seat[i] = p
    cells = []
    for r in range(1, rounds + 1):
        row = ["<td class='rh'>R%d</td>" % r]
        for c, owner in enumerate(order):
            i = (r - 1) * len(order) + (
                (len(order) - 1 - c) if (snake and r % 2 == 0) else c)
            got = by_seat.get(i)
            lbl = seats[i]["label"] if i < len(seats) else ""
            cls = []
            if got:
                cls += ["dhas", "p-%s" % (got.get("position") or "")]
            if seat and i == len(made):
                cls.append("dnow")
            if owner == VIEW:
                cls.append("dmine")
            row.append(
                "<td class='%s'><div class='dcell'><div class='l'>%s</div>%s</div></td>" % (
                    " ".join(cls), lbl,
                    ("<div class='n'>%s</div><div class='p pos-%s'>%s</div>" % (
                        esc(got["name"]), got.get("position", ""),
                        " &middot; ".join(
                            esc(x) for x in (got.get("position"), got.get("team")) if x)))
                    if got else ""))
        cells.append("<tr>%s</tr>" % "".join(row))
    st.markdown(
        '<div class="dboard"><table class="dboard"><colgroup><col class="rh">%s</colgroup>'
        '<tr><th class="rh"></th>%s</tr>%s</table></div>' % (
            "".join("<col>" for _ in order),
            "".join("<th title='%s'>%s</th>" % (esc(team_of(o)), esc(who(o).split()[0]))
                    for o in order),
            "".join(cells)), unsafe_allow_html=True)


def draft_entry(which: str, pick_order, rounds: int, snake: bool) -> None:
    """Record a draft held in a room, under the board it belongs to.

    This had its own nav leaf, which meant choosing rookie-or-veteran from
    a radio when the page you came from already knew the answer.
    """
    theme.bar("Enter results", "%d rounds &middot; %d picks" % (
        rounds, rounds * len(pick_order)))
    unlocked = draw_lock_ui(
        "password to record picks",
        "Reading only. Anyone can see what has been entered; only the commissioner types it "
        "in, so eight people cannot overwrite the board at once.")
    st.markdown(
        '<div class="banner" style="margin-top:14px">Every live board in this app reads rosters from Sleeper. If '
        'the draft happened in a room and never got keyed in anywhere, the value board, the '
        'wire, the taxi bay and every keeper price stay empty <b>permanently</b>. Enter the '
        'results in Sleeper if you can &mdash; that is the real record. This is here so a '
        'paper draft is not a dead end.</div>', unsafe_allow_html=True)

    existing = picks.load(which, SEASON)
    st.markdown('<div class="tiny" style="margin:6px 0">%d of %d picks recorded. Paste one '
                'player per line, in pick order &mdash; or prefix a line with its slot '
                '(<code>3.05 Bijan Robinson</code>) to place it exactly. Round and pick are '
                'optional; everything else is read as a name.</div>' % (
                    len(existing), rounds * len(pick_order)), unsafe_allow_html=True)

    pasted = st.text_area("Results", height=180, key="paste_%s" % which,
                          placeholder="Ja'Marr Chase\nBijan Robinson\n3.05 Puka Nacua",
                          label_visibility="collapsed", disabled=not unlocked)
    c1, c2 = st.columns([1, 4])
    with c1:
        do_import = st.button("Import", key="imp_%s" % which,
                                 disabled=not unlocked or not pasted.strip())
    with c2:
        if st.button("Clear this draft", key="clr_%s" % which,
                         disabled=not unlocked or not existing):
            picks.clear(which, SEASON); st.rerun()
    storage_note(check=unlocked)

    if do_import:
        got = picks.parse(pasted, pick_order, rounds, snake)
        if got["problems"]:
            st.markdown("".join(
                '<div class="banner" style="border-color:var(--bad);color:var(--bad);'
                'margin-bottom:6px">%s</div>' % esc(p) for p in got["problems"][:12]),
                unsafe_allow_html=True)
        if got["picks"] and save_or_say("those picks", picks.save, which,
                                        got["picks"], SEASON):
            st.markdown('<div class="banner" style="border-color:var(--acc)">Recorded '
                        '<b>%d</b> of %d picks. Anything flagged above was skipped &mdash; '
                        'fix the name and paste those lines again.</div>' % (
                            len(got["picks"]), len(got["picks"]) + len(got["problems"])),
                        unsafe_allow_html=True)
            st.rerun()

    if existing:
        ledger_table(["Pick", "Player", "To"], [[
            '<span class="mono">%d.%02d</span>' % (p["round"], p["pick"]),
            '<div style="font-weight:650">%s</div><div class="tiny">%s</div>' % (
                esc(p["name"]), esc(p.get("position", ""))),
            '<span class="tiny">%s</span>' % esc(who(p["owner_id"])),
        ] for p in existing])


def render_draft(leaf=None):
    # Page-level: the capital strip needs the same order the board draws in.
    draw = first_draw()
    order = _live_order(live.VETERAN) or draw.get("veteran") or owner_ids()
    if leaf in (None, "room"):
        draft_room()

    if leaf in (None, "rookie"):
        # Sleeper's own order wins once the draft exists there. The drum decides
        # what the order SHOULD be; Sleeper is what the picks are actually
        # landing against, and a board that disagreed with the picks listed
        # above it would just look broken.
        rk_order = _live_order(live.ROOKIE) or draw.get("rookie") or owner_ids()
        theme.bar("Rookie draft", "%d rounds &middot; %d picks &middot; held first" % (
            config.rookie_rounds(), draftboard.rookie_pick_count()))
        live_draft(live.ROOKIE)
        board_note(live.ROOKIE, bool(draw.get("rookie")))

        rk_done = _draft_done("rookie")
        rk = [] if rk_done else draftboard.rookie_grid(rk_order, SEASON)
        head = "".join('<th title="%s">%s</th>' % (esc(team_of(o)), esc(who(o).split(" ")[0]))
                       for o in rk_order)
        body = "".join(
            '<tr><td class="rd">R%d</td>%s</tr>' % (
                r + 1, "".join('<td><div class="cell open">%s</div></td>' % c.pick_label
                               for c in row))
            for r, row in enumerate(rk))
        # Once the draft is done, "Who took what" above IS the board; an empty
        # grid of open cells underneath it was the same draft drawn blank.
        if not rk_done:
            st.markdown('<div class="boardwrap"><table class="board">'
                        '<thead><tr><th></th>%s</tr></thead><tbody>%s</tbody></table></div>' % (
                            head, body), unsafe_allow_html=True)
            st.markdown(
                '<div class="tiny" style="margin-top:8px">No keeper ever strikes a pick off this '
                'board &mdash; a keeper costs a <b>veteran</b> round. Round two %s.</div>' % (
                    "snakes back" if config.drafts().get("rookie_snake", True)
                    else "repeats round one"), unsafe_allow_html=True)

        # The point of this board is not the grid, it is what a pick here is
        # worth to hold - which is different from every other pick in the league.
        prem = engine.rookie_draft_premium()
        last = config.veteran_rounds()
        st.markdown(
            '<div class="card" style="margin-top:12px"><div class="eyebrow">What a pick here '
            'buys you</div>%s</div>' % "".join(
                '<div class="wr" style="display:grid;grid-template-columns:190px 90px 1fr;'
                'gap:14px;padding:10px 0;border-top:1px solid var(--line);align-items:baseline">'
                '<div style="font-size:13.5px;color:var(--ink2)">%s</div>'
                '<div style="font-family:var(--f-display);font-weight:800;font-size:21px;'
                'color:var(--acc)">%s</div><div class="tiny">%s</div></div>' % (a, b, c)
                for a, b, c in (
                    ("In a rookie keeper slot", "R%d / R%d" % (last, last - 1),
                     "no clock, yours for his career &mdash; but only two slots a team"),
                    ("In a regular keeper slot", "R%d" % prem,
                     "flat in year one, then %d, then the market. He has no veteran round, "
                     "so the premium stands in for one" % max(1, prem - 3)),
                    ("Stashed on taxi", "free",
                     "two years, no keeper slot, and promoting him keeps the rookie "
                     "designation"),
                    ("Left in the pool", "&mdash;",
                     "he goes into the veteran draft and anybody can take him at a real round"),
                )), unsafe_allow_html=True)
        st.markdown(
            '<div class="tiny" style="margin-top:10px">Only <b>%d</b> of the %d players taken '
            'here can end up in rookie keeper slots on any one team. The rest are R%d regular '
            'keepers, taxi stashes, or cuts &mdash; which is what makes the back half of this '
            'board a different decision from the front.</div>' % (
                int(config.keeper_rules()["rookie"]), draftboard.rookie_pick_count(), prem),
            unsafe_allow_html=True)

        if not rk_done:        # the entry form is for a draft still being held
            draft_entry("rookie", rk_order, config.rookie_rounds(),
                        bool(config.drafts().get("rookie_snake", True)))

    if leaf in (None, "capital"):
        # Once this season's draft has run, its picks are spent - the capital
        # that matters is next year's, and from 2027 that is the one 16-round board.
        cap_year = SEASON + 1 if _phase() in ("pre_season", "in_season", "offseason") else SEASON
        owned_by = draftboard.owned_rounds(LG, cap_year)
        keep_by = submitted_keepers()
        rounds_n = config.veteran_rounds(cap_year)
        _mine = owned_by.get(VIEW, Counter())
        _missing = [r for r in range(1, rounds_n + 1) if _mine.get(r, 0) <= 0]
        _extra = [r for r in range(1, rounds_n + 1) if _mine.get(r, 0) > 1]
        if VIEW:
            st.markdown(_bh("ink", f"Draft capital · the {cap_year} draft"
                            + (" · one board" if config.single_drum(cap_year) else " · veteran draft"),
                            str(sum(_mine.values())),
                            "picks you hold" + (
                                f" — missing R{', R'.join(map(str, _missing))}" if _missing else " — every round of your own")
                            + (f", plus extra R{', R'.join(map(str, _extra))}" if _extra else "")),
                        unsafe_allow_html=True)
        cap_rows = []
        for c in draftboard.capital(order, keep_by, cap_year, LG):
            oid = c["owner_id"]
            held = owned_by.get(oid, Counter())
            eaten_rounds = {int(k.get("round")) for k in (keep_by.get(oid) or [])
                            if k.get("round")}
            states = []
            for r in range(1, rounds_n + 1):
                n = held.get(r, 0)
                states.append("traded" if n <= 0 else
                              "eaten" if r in eaten_rounds else
                              "extra" if n > 1 else "live")
            cap_rows.append([
                '<div style="font-weight:650">%s</div><div class="tiny">%s</div>' % (
                    esc(who(oid)), esc(team_of(oid))),
                theme.capital_strip(states),
                '<span class="mono" style="font-weight:700">%d</span>' % c["live"],
                '<span class="mono">%d</span>' % c["rookie_picks"],
            ])
        ledger_table(["Owner", "Round 1 \u2192 %d" % rounds_n, "Live", "Rookie"], cap_rows)
        st.markdown(
            '<div class="legend" style="margin-top:10px">'
            '<span><b style="background:var(--line2)"></b> Held</span>'
            '<span><b style="background:var(--acc)"></b> Eaten by a keeper</span>'
            '<span><b style="box-shadow:inset 0 0 0 1px var(--warn)"></b> Traded away</span>'
            '<span><b style="background:var(--acc2)"></b> Extra, acquired in a trade</span>'
            '</div>'
            '<div class="tiny" style="margin-top:8px">Which rounds are missing matters more than how '
            'many. A team without its 1st and 2nd is in a completely different position from one '
            'without its %dth and %dth, and a count cannot say so.</div>' % (
                rounds_n - 1, rounds_n), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# LOTTERY
# ---------------------------------------------------------------------------

@st.cache_data(ttl=900, show_spinner=False)
def _final_places() -> dict:
    """{owner: final_rank} once the brackets have results: 1-4 from the
    winners bracket, 5-8 from the Chase. Empty until then, and the drum falls
    back to the table as it stands."""
    try:
        r2o = {int(r["roster_id"]): str(r.get("owner_id")) for r in sleeper.get_rosters(LG) or []}
        out = {}
        for rows, base in ((sleeper.get_winners_bracket(LG) or [], 0),
                           (sleeper.get_losers_bracket(LG) or [], len(r2o) // 2)):
            for m in rows:
                p_ = m.get("p")
                if p_ and m.get("w") and m.get("l"):
                    out[r2o.get(int(m["w"]))] = base + int(p_)
                    out[r2o.get(int(m["l"]))] = base + int(p_) + 1
        return {k: v for k, v in out.items() if k}
    except Exception:          # noqa: BLE001
        return {}


def _drum_standings() -> list:
    """The drum's inputs as of now: final places where the brackets have
    settled them, the table where they have not. Nobody is champion until the
    final has a winner, so nobody is floored until then."""
    rows = season.standings()
    fin = _final_places()
    champ = next((o for o, r in fin.items() if r == 1), None)
    return [{"owner_id": r["owner_id"], "wins": r["wins"], "final_rank": fin.get(r["owner_id"], r["place"]),
             "champion": r["owner_id"] == champ} for r in rows]


def _prev_first(draft_year: int):
    """First choice of the draw that ordered the PREVIOUS year's draft."""
    try:
        d = storage.load_draw(draft_year - 1) or {}
    except Exception:          # noqa: BLE001
        d = {}
    order = d.get("drum") or d.get("veteran") or []
    return order[0] if order else None


def render_lottery(leaf=None):
    """One drum from 2027: the consolidated draft has one board, so it has
    one order. The 2026 two-drum draw is kept below, folded away, as history."""
    lr = config.lottery_rules()
    nxt = SEASON + 1                      # the draft this season's results order
    st.markdown(
        '<div class="banner"><b>One drum from %d.</b> One board means one order. The drum runs '
        'on <b>final standing</b>: the four playoff teams by where they finish, the champion '
        'always on the smallest weight; the four Chase teams by where they finish the Chase, so '
        'winning it pays up to $%d and costs you balls. The drum picks a <b>selection order</b>, '
        'not a slot &mdash; first choice takes any spot on the board. Nobody wins first choice two '
        'years running.</div>' % (config.lottery_rules().get("single_drum_from", 2027),
                                  int(pot.cap_amount()[0])), unsafe_allow_html=True)

    use_alt = st.toggle("Use the steeper spread (%s)" % ", ".join(
        str(x) for x in config.lottery_weights(alt=True)), value=False, key="alt_weights")
    weights = config.lottery_weights(alt=use_alt)

    try:
        today = _drum_standings()
    except Exception:          # noqa: BLE001
        today = []
    prev = _prev_first(nxt)
    locked = lottery.locked_out_for(nxt, prev, nxt - 1)
    seats = lottery.build_single(today, weights=weights, locked_out=locked) if today else []
    complete = (lg.get("status") or "") == "complete"
    fin = _final_places()

    if leaf in (None, "drums") and seats:
        theme.bar("The drum", "for the %d draft &middot; %s &middot; ball size is the weight" % (
            nxt, "final" if complete else "if the season ended now"))
        st.markdown('<div class="kx drums">' + _drum3d(seats, "var(--kr2)", "rgba(251,8,73,.22)",
                    "%d draft &middot; one drum" % nxt) + '</div>', unsafe_allow_html=True)

        def why(s_, t):
            if s_.champion:
                return "champion &middot; floored"
            if s_.locked_out:
                return "won first choice last year &middot; barred from it"
            if t["final_rank"] in fin.values() and s_.owner_id in fin:
                return "finished %s" % ordinal(t["final_rank"])
            cut = int(config.league()["playoff_teams"])
            return ("%s &middot; in the bracket" % ordinal(t["final_rank"]) if t["final_rank"] <= cut
                    else "%s &middot; in the Chase" % ordinal(t["final_rank"]))
        rows_ = []
        for s_ in seats:
            t = next(d for d in today if d["owner_id"] == s_.owner_id)
            rows_.append(
                '<div class="lotrow"><div class="lotname">%s<small>%s</small></div>'
                '<div class="lotbars"><i style="width:%d%%;background:%s">%d balls</i>'
                '<i style="width:%d%%;background:var(--card2)"></i></div></div>' % (
                    esc(who(s_.owner_id)), why(s_, t), s_.weight * 3,
                    "var(--dim)" if s_.locked_out else ("var(--acc2)" if s_.champion else "var(--acc)"),
                    s_.weight, 100 - s_.weight * 3))
        st.markdown('<div class="card"><div class="lot">%s</div></div>' % "".join(rows_),
                    unsafe_allow_html=True)
        cut = int(config.league()["playoff_teams"])
        chase_w = list(weights[:len(seats) - cut])[::-1]
        st.markdown(
            '<div class="tiny" style="margin-top:8px">Chase teams: win it and you hold <b>%d</b> '
            'balls, lose out and you hold <b>%d</b>. Playoff teams hold %s by finish. %d selections '
            'are drawn; everyone after that falls in ball order.%s</div>' % (
                chase_w[0] if chase_w else 0, chase_w[-1] if chase_w else 0,
                " / ".join(str(w) for w in weights[len(seats) - cut:]),
                int(lr.get("lottery_slots", 2)),
                (" %s won first choice of the %d draw, but that draw was flat and random, so it does "
                 "not lock him out." % (esc(who(prev)), nxt - 1)) if prev and not locked else ""),
            unsafe_allow_html=True)

        # The draw itself: opens once the Chase is over and the order is real.
        theme.bar("The %d draw" % nxt, "after slips lock &middot; read from the back")
        drawn = {}
        try:
            drawn = storage.load_draw(nxt) or {}
        except Exception:      # noqa: BLE001
            drawn = {}
        unlocked = draw_lock_ui()
        c1, c2 = st.columns([1, 2])
        with c1:
            seed = st.number_input("Draw seed", 0, 10 ** 6, int(drawn.get("seed", 0)),
                                   key="seed_one", disabled=not (unlocked and complete))
            if st.button("Run the draw", disabled=not (unlocked and complete)):
                order = lottery.draw(seats, rng=__import__("random").Random(int(seed)))
                storage.save_single_draw(int(seed), order, nxt)
                st.rerun()
        with c2:
            if not complete:
                st.markdown('<div class="tiny">Opens when the Chase final is played: the order has '
                            'to come from final standing, and the drum above is still the table as '
                            'it stands.</div>', unsafe_allow_html=True)
        order = drawn.get("drum") or []
        if order:
            n = len(order)
            shown = int(drawn.get("reveal", 0))
            cA, cB = st.columns([1, 3])
            with cA:
                if st.button("Open next", disabled=(shown >= n or not unlocked), use_container_width=True):
                    storage.set_reveal(shown + 1, nxt); st.rerun()
            with cB:
                if st.button("Reset the reveal", disabled=(not shown or not unlocked)):
                    storage.set_reveal(0, nxt); st.rerun()
            if shown < n:
                st.markdown('<div class="hat">%s</div>' % "".join(
                    '<span>%s</span>' % esc(who(o)) for o in order[:n - shown]), unsafe_allow_html=True)
            st.markdown('<div class="draw">%s</div>' % "".join(
                theme.draw_slot(i + 1, esc(who(o)), esc(team_of(o)), revealed=(i >= n - shown),
                                fresh=(i == n - shown), final=(i == 0))
                for i, o in enumerate(order)), unsafe_allow_html=True)
            if shown >= n:
                st.markdown('<div class="tiny" style="margin-top:8px">Seed <b style="color:var(--acc)">%s</b> '
                            '&mdash; anyone can reproduce this exact order.</div>' % esc(str(drawn.get("seed"))),
                            unsafe_allow_html=True)

    if leaf in (None, "sim") and seats:
        theme.bar("Simulate the %d drum" % nxt, " / ".join(str(w) for w in weights))
        n_ = st.select_slider("Runs", [2000, 5000, 20000], value=5000, key="sim_n")
        res = lottery.simulate_one(seats, n=int(n_), seed=17)
        out = []
        for s_ in seats:
            row = res["drum"][s_.owner_id]
            p1, p2 = row[0], row[1]
            rest = 100 - p1 - p2
            out.append(
                '<div class="lotrow"><div class="lotname">%s<small>1st %.1f%% · median %d</small>'
                '</div><div class="lotbars">%s%s'
                '<i style="width:%.1f%%;background:var(--card2);color:var(--dim)">%s</i>'
                '</div></div>' % (
                    esc(who(s_.owner_id)), p1, lottery.median_slot(row),
                    '<i style="width:%.1f%%;background:var(--acc)">%s</i>' % (
                        p1, "%.0f%%" % p1 if p1 > 13 else "") if p1 > 0.05 else "",
                    '<i style="width:%.1f%%;background:var(--acc2)">%s</i>' % (
                        p2, "%.0f%%" % p2 if p2 > 13 else "") if p2 > 0.05 else "",
                    rest, "3rd+" if rest > 30 else ""))
        st.markdown('<div class="card"><div class="eyebrow">%d draft</div><h3 class="k">Selection odds'
                    '</h3><div class="lot">%s</div></div>' % (nxt, "".join(out)), unsafe_allow_html=True)
        st.markdown('<div class="tiny" style="margin-top:8px">%d runs on the table as it stands. First '
                    'choice in red, second in blue.</div>' % res["n"], unsafe_allow_html=True)

    if not seats:
        st.info("The drum fills in once there are standings to weight it.")

    # The draw that ordered THIS season's draft, kept as history rather than
    # left on top of the page it no longer runs.
    if leaf in (None, "drums") and (FIRST or storage.load_draw(SEASON)):
        with st.expander("The %d draw — done%s" % (SEASON, " (two drums, drawn flat)" if FIRST else "")):
            _render_first_draw()


def _render_first_draw() -> None:
    """Season one's flat two-drum draw: the seed, the controls, the envelopes."""
    draw = None
    if True:
        unlocked = draw_unlocked()   # the page already shows the one unlock box
        c1, c2 = st.columns([1, 2])
        with c1:
            existing = first_draw()
            seed = st.number_input("Draw seed", 0, 10 ** 6,
                                   int(existing.get("seed", 0)), key="seed_first",
                                   disabled=not unlocked)
            if st.button("Draw both orders", disabled=not unlocked):
                storage.save_draw(
                    int(seed),
                    lottery.first_season_order(owner_ids(), seed=int(seed)),
                    lottery.first_season_order(owner_ids(), seed=int(seed) + 1),
                    SEASON)
                st.rerun()
            if existing:
                st.markdown(
                    '<div class="tiny" style="margin-top:8px">Drawn from seed '
                    '<b style="color:var(--acc)">%s</b> on %s. Anyone can put that seed in '
                    'and get this exact order back &mdash; the draw is reproducible, not '
                    'something you have to take on trust. Re-drawing overwrites it.</div>' % (
                        existing.get("seed"), esc((existing.get("drawn_at") or "")[:10])),
                    unsafe_allow_html=True)
            storage_note()
        draw = first_draw()

    if draw:
        unlocked = draw_unlocked()
        # Read out LAST pick first and work up to first choice. That is how a
        # lottery is meant to be run: the room learns who is stuck at the back
        # while the prize is still in the hat, and the last envelope is the
        # only one anybody remembers.
        acts = [("rookie", "Rookie draft"), ("veteran", "Veteran draft")]
        n = len(owner_ids())
        total = n * len(acts)
        shown = int(draw.get("reveal", 0))

        theme.bar("The draw", "read from the back &mdash; %d of %d opened" % (shown, total))
        cA, cB, cC, cD = st.columns([1, 1, 1, 2])
        with cA:
            if st.button("Open next", disabled=(shown >= total or not unlocked),
                         use_container_width=True):
                storage.set_reveal(shown + 1, SEASON); st.rerun()
        with cB:
            auto = st.toggle("Auto", value=False, key="auto_reveal",
                             disabled=(shown >= total or not unlocked))
        with cC:
            pause = st.number_input("Pause", 1, 20, 6, key="reveal_pause",
                                    label_visibility="collapsed", disabled=not unlocked)
        with cD:
            if st.button("Reset the reveal", disabled=(not shown or not unlocked)):
                storage.set_reveal(0, SEASON); st.rerun()
            st.markdown('<div class="tiny">Seconds between envelopes when Auto is on. '
                        'Nothing is random here &mdash; the order was fixed by the seed '
                        'before the first envelope opened.</div>', unsafe_allow_html=True)

        for act, (key, label) in enumerate(acts):
            order = draw.get(key) or []
            done_here = max(0, min(n, shown - act * n))
            st.markdown('<div class="eyebrow" style="margin-top:16px">%s &mdash; selection '
                        'order</div>' % label, unsafe_allow_html=True)
            if done_here < n:
                left = order[:n - done_here]
                st.markdown('<div class="hat">%s</div>' % "".join(
                    '<span>%s</span>' % esc(who(o)) for o in left), unsafe_allow_html=True)
            st.markdown('<div class="draw">%s</div>' % "".join(
                theme.draw_slot(
                    i + 1, esc(who(o)), esc(team_of(o)),
                    revealed=(i >= n - done_here),
                    fresh=(i == n - done_here and shown == act * n + done_here),
                    final=(i == 0))
                for i, o in enumerate(order)), unsafe_allow_html=True)

        if shown >= total:
            st.markdown(
                '<div class="banner" style="border-color:var(--acc);margin-top:14px">'
                '<b>That is the board.</b> Both orders are selection order, not slots &mdash; '
                'first choice takes any spot they want, second choice takes any that is left. '
                'Seed <b style="color:var(--acc)">%s</b>, so anyone can reproduce this exact '
                'draw.</div>' % esc(str(draw.get("seed"))), unsafe_allow_html=True)
        elif auto:
            time.sleep(int(pause))
            storage.set_reveal(shown + 1, SEASON)
            st.rerun()



# ---------------------------------------------------------------------------
# the bottom bar
# ---------------------------------------------------------------------------

def _keep() -> str:
    """The query bits that have to survive a navigation.

    The bottom bar rebuilds the whole query string from scratch, so anything not
    named here is dropped - which is how choosing a team and then tapping a page
    silently put you back on your own.
    """
    bits = []
    if VIEW and VIEW != DEFAULT_VIEW:
        bits.append("team=%s" % VIEW)
    if _qp("k"):                       # keep the draft room unlocked across pages
        bits.append("k=%s" % _qp("k"))
    return ("&" + "&".join(bits)) if bits else ""


def _popover(section: str, label: str) -> str:
    """Every leaf in a section, on one sheet, one tap away.

    This used to be a drill-down: tap the section, tap the group, tap the leaf.
    Three taps to reach a page, and the middle one existed only because the
    sheet could not hold everything. It can - six leaves under Pre-Season, four
    under In-Season - so the groups became headings and the drill-down went.
    """
    groups = GROUPS[section]
    body = "".join(
        '%s%s' % (
            ('<div class="bb-group">%s</div>' % glabel) if glabel else "",
            "".join(
                '<a class="bb-item leaf%s" href="?p=%s&g=%s&t=%s%s" target="_self">%s</a>' % (
                    " on" if (PAGE == section and GROUP == gk and LEAF == lk) else "",
                    section, gk, lk, _keep(), llabel)
                for lk, llabel in leaves))
        for gk, glabel, leaves in groups)
    return ('<div class="bb-pop" id="bb-pop-%s">'
            '<div class="bb-head"><span class="bb-title">%s</span></div>%s</div>' % (
                section, label, body))


def _me_popover() -> str:
    """The masthead's team dropdown: every team, each a link to THIS page as
    that team."""
    from urllib.parse import urlencode
    items = []
    for o in owner_ids():
        q = {k: _qp(k) for k in st.query_params.keys()}
        q["team"] = o
        items.append('<a class="bb-item leaf%s" href="?%s" target="_self">%s<span class="sub">%s</span></a>' % (
            " on" if o == VIEW else "", urlencode(q), esc(team_of(o)), esc(who(o))))
    return ('<div class="bb-pop bb-pop-me" id="bb-pop-me"><div class="bb-head">'
            '<span class="bb-title">Whose team?</span></div>%s</div>' % "".join(items))


# Installed once per page load in the PAGE's own JS realm (window.parent.eval),
# not the components iframe's: Streamlit rebuilds the iframe and the masthead on
# reruns, so per-element listeners bound from the iframe go stale. One delegated
# capture-phase handler covers the section sheets, the team chip, the scrim,
# and appending the remembered team to every in-app link.
_NAV_JS = r"""
(function(){
  if (document.__hmNav) return;
  document.__hmNav = true;
  var KEY = 'halfmen_team';
  function closeAll(){
    document.querySelectorAll('.bb-pop').forEach(function(p){ p.classList.remove('on'); });
    var sc = document.getElementById('bb-scrim'); if (sc) sc.classList.remove('on');
  }
  document.addEventListener('click', function(e){
    var tg = e.target.closest('[data-toggle]');
    if (tg) {
      e.preventDefault(); e.stopPropagation();
      var pop = document.getElementById(tg.getAttribute('data-toggle'));
      var was = pop && pop.classList.contains('on');
      closeAll();
      if (pop && !was) {
        pop.classList.add('on');
        var sc = document.getElementById('bb-scrim'); if (sc) sc.classList.add('on');
        var cur = pop.querySelector('.bb-item.on');
        if (cur) pop.scrollTop = Math.max(0, cur.offsetTop - pop.clientHeight / 2);
      }
      return;
    }
    if (e.target.id === 'bb-scrim') { closeAll(); return; }
    var a = e.target.closest('a[href]');
    if (!a) return;
    var h = a.getAttribute('href') || '';
    if (h.charAt(0) !== '?') return;
    var u = new URLSearchParams(h.slice(1));
    if (u.get('team')) { try { localStorage.setItem(KEY, u.get('team')); } catch(_) {} return; }
    var m = null; try { m = localStorage.getItem(KEY); } catch(_) {}
    if (m) { u.set('team', m); a.setAttribute('href', '?' + u.toString()); }
  }, true);
  // manager cards and contract cards flip on tap / Enter / Space; the taxi
  // turntable turns to the other slot
  function act(c){
    if (c.classList.contains('txc-stage')) {
      var t = c.querySelector('.txc-in');
      var n = (parseInt(t.style.getPropertyValue('--turn') || '0', 10) + 1) % 2;
      t.style.setProperty('--turn', n);
    } else c.classList.toggle('on');
  }
  document.addEventListener('click', function(e){
    var c = e.target.closest && e.target.closest('.mcard, .kflip, .txc-stage');
    if (c) act(c);
  });
  document.addEventListener('keydown', function(e){
    var c = e.target.closest && e.target.closest('.mcard, .kflip, .txc-stage');
    if (c && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); act(c); }
  });
  // tilt + shine: the covers and award cards lean toward the pointer (or a
  // dragging finger) and a glint follows it across
  var still = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var cur = null;
  function reset(el){ if (!el) return; el.style.transform = ''; el.style.setProperty('--sx', '130%'); }
  if (!still) {
    document.addEventListener('pointermove', function(e){
      var el = e.target.closest && e.target.closest('.kx.gw, .kx.xb, .kx .sup');
      if (el !== cur) { reset(cur); cur = el; }
      if (!el) return;
      var r = el.getBoundingClientRect();
      var x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
      var k = el.classList.contains('sup') ? 2 : 1;
      el.style.transform = 'perspective(1100px) rotateY(' + (x * 8 * k).toFixed(2) + 'deg) rotateX(' + (-y * 6 * k).toFixed(2) + 'deg)';
      el.style.setProperty('--sx', (110 - (x + 0.5) * 90).toFixed(1) + '%');
    }, {passive: true});
    ['pointerleave', 'pointerup', 'pointercancel'].forEach(function(t){
      document.addEventListener(t, function(e){ if (t !== 'pointerleave' || !e.relatedTarget) { reset(cur); cur = null; } }, true);
    });
  }
})();
"""


def render_bottom_bar() -> None:
    links = []
    for key, label in SECTIONS:
        cls = " active" if PAGE == key else ""
        if key in GROUPS:
            links.append('<div class="bb-link%s" data-toggle="bb-pop-%s">%s</div>' % (
                cls, key, label))
        else:
            links.append('<a class="bb-link%s" href="?p=%s%s" target="_self">%s</a>' % (
                cls, key, _keep(), label))
    bar = ('<div class="bb-scrim" id="bb-scrim"></div>'
           + "".join(_popover(k, l) for k, l in SECTIONS if k in GROUPS)
           + _me_popover()
           + '<div class="bb-wrap"><div class="bb">%s</div></div>' % "".join(links))

    # st.markdown strips <script>, so this can't live there. components.html
    # runs real JS in a same-origin iframe; window.parent.document is the app's
    # own document (where the stylesheet lives and position:fixed anchors to
    # the real viewport). Cloud's own badge lives a level further out
    # (window.top). Team memory: a URL ?team= is saved to localStorage, and a
    # bare URL with a saved team reloads once with it - through parent.eval,
    # because this iframe is sandboxed without allow-top-navigation.
    components.html(
        "<script>(function(){"
        "const P = window.parent, doc = P.document, topDoc = window.top.document;"
        "const VALID = " + json.dumps(owner_ids()) + ", DEFAULT = " + json.dumps(DEFAULT_VIEW) + ";"
        "try {"
        "  const q = new URLSearchParams(P.location.search);"
        "  const t = q.get('team');"
        "  if (t && VALID.includes(t)) { P.localStorage.setItem('halfmen_team', t); }"
        "  else { const saved = P.localStorage.getItem('halfmen_team');"
        "    if (saved && VALID.includes(saved) && saved !== DEFAULT) { q.set('team', saved);"
        "      P.eval('location.replace(' + JSON.stringify(P.location.pathname + '?' + q.toString()) + ')');"
        "      return; } }"
        "} catch (e) {}"
        "if (!topDoc.getElementById('hm-hide-cloud')) {"
        "  const s = topDoc.createElement('style'); s.id = 'hm-hide-cloud';"
        "  s.textContent = '[class*=\"viewerBadge\"],[class*=\"profileContainer\"],"
        "[data-testid=\"manage-app-button\"],a[href*=\"share.streamlit.io\"]"
        "{display:none !important;}';"
        "  topDoc.head.appendChild(s);"
        "}"
        "const old = doc.getElementById('hm-bottom-bar'); if (old) old.remove();"
        "const root = doc.createElement('div'); root.id = 'hm-bottom-bar';"
        "root.innerHTML = " + json.dumps(bar) + ";"
        "doc.body.appendChild(root);"
        "P.eval(" + json.dumps(_NAV_JS) + ");"
        "})();</script>", height=0)


# ---------------------------------------------------------------------------
# THE LEAGUE  - who everyone is, what they have done, and what they've traded
# ---------------------------------------------------------------------------
# Four pages ported from the Kreeper League. Season one means two of them are
# thin on purpose rather than broken: the record book has no completed season
# to look back on, and the trade log is only as long as the deals made so far.
# Both fill themselves as the league runs - nothing here needs revisiting in
# 2027.

@st.cache_data(ttl=1800, show_spinner=False)
def build_record_book():
    """(seasons newest-first, per-manager aggregate) from every Sleeper season
    BEFORE this one, walking previous_league_id. In 2026 that is empty, and the
    page says so rather than inventing a history."""
    chain = sleeper.league_chain(LG)
    seasons = []
    agg = {o: {"w": 0, "l": 0, "pf": 0.0, "titles": 0, "runner": 0, "seasons": 0}
           for o in config.managers()}
    for c in chain:
        if str(c["season"]) == str(SEASON):
            continue
        rosters = sleeper.get_rosters(c["league_id"]) or []
        r2o = {int(r["roster_id"]): str(r.get("owner_id")) for r in rosters}
        champ = runner = None
        try:
            for m in sleeper.get_winners_bracket(c["league_id"]) or []:
                if m.get("p") == 1:
                    champ, runner = r2o.get(m.get("w")), r2o.get(m.get("l"))
        except Exception:          # noqa: BLE001 - a season with no bracket still counts
            pass
        standings = []
        for r in rosters:
            o = str(r.get("owner_id"))
            cfg = r.get("settings", {}) or {}
            w, l = cfg.get("wins", 0) or 0, cfg.get("losses", 0) or 0
            pf = (cfg.get("fpts", 0) or 0) + (cfg.get("fpts_decimal", 0) or 0) / 100
            standings.append({"owner": o, "name": who(o), "w": w, "l": l, "pf": round(pf, 1)})
            if o in agg:
                agg[o]["w"] += w
                agg[o]["l"] += l
                agg[o]["pf"] += pf
                agg[o]["seasons"] += 1
                if o == champ:
                    agg[o]["titles"] += 1
                if o == runner:
                    agg[o]["runner"] += 1
        standings.sort(key=lambda x: (-x["w"], -x["pf"]))
        seasons.append({"season": c["season"], "standings": standings,
                        "champ": who(champ) if champ else None,
                        "runner": who(runner) if runner else None})
    return seasons, agg


def render_managers() -> None:
    """The league as trading cards: the photo and this season's record on the
    front, the record book on the back. Tap one to flip it."""
    st.markdown(_ThemeShim.section_head('The <span class="g">Managers</span>',
                                        "tap a card to flip it", page=True), unsafe_allow_html=True)
    table = season.standings()
    try:
        _seasons, agg = build_record_book()
    except Exception:              # noqa: BLE001 - no history is not a broken page
        agg = {}
    cur = season.current_week()
    odds = {}
    if cur:
        try:
            odds = {o: v for o, v in
                    ((get_playoff_outlook(None, cur).get("sim") or {}).get("teams") or {}).items()}
        except Exception:          # noqa: BLE001
            odds = {}
    by_pf = {r["owner_id"]: i + 1 for i, r in
             enumerate(sorted(table, key=lambda r: -r["points_for"]))}
    me = VIEW
    cards = []
    for r in table:
        o = r["owner_id"]
        a = agg.get(o) or {}
        ph = _mgr_photo(str(o))
        front = f'<img src="{ph}" alt="">' if ph else f'<em class="mc-ini">{_initials(o)}</em>'
        w_all, l_all = a.get("w", 0) + r["wins"], a.get("l", 0) + r["losses"]
        titles, runner = a.get("titles", 0), a.get("runner", 0)
        rows = [("This season", esc(r["record"])),
                ("Points for", f'{r["points_for"]:,.0f} &middot; #{by_pf.get(o, "-")}')]
        if a.get("seasons"):      # in season one "all-time" is this season again
            rows += [("All-time", f'{w_all}&ndash;{l_all}'),
                     ("Titles", f'{titles}' + (f' &middot; {runner}&times; runner-up' if runner else ""))]
        rows += [
                ("Playoff odds", f'{odds[o]["playoff_pct"]}%' if o in odds else "&mdash;"),
                ("Title odds", f'{odds[o].get("title_pct", 0):.0f}%' if o in odds else "&mdash;"),
                ("FAAB spent", f'${int(r["spent"])} of ${int(r["entitlement"])}')]
        if me and o != me and cur:
            h = get_h2h(me, o, cur)
            if h["games"]:
                rows.append(("vs you", f'{h["b"]}&ndash;{h["a"]}'))
        seasons_in = a.get("seasons", 0) + 1
        note = (f"{titles}-time champion" if titles else
                f"{seasons_in} season{'s' if seasons_in != 1 else ''} in the league")
        cards.append(
            f'<div class="mcard{" me" if o == me else ""}" tabindex="0" role="button" '
            f'aria-label="Flip {esc(team_of(o))}">'
            f'<div class="mc-in"><div class="mc-f"><em class="mc-rk">#{r["place"]}</em>{front}'
            f'<div class="mc-ft"><b>{esc(team_of(o))}</b>'
            f'<small>{esc(who(o))} &middot; {esc(r["record"])}</small></div></div>'
            f'<div class="mc-b"><b class="mc-h">{esc(team_of(o))}</b>'
            + "".join(f'<div class="mc-row"><small>{k}</small><b>{v}</b></div>' for k, v in rows)
            + f'<small class="mc-note">{note}</small></div></div></div>')
    st.markdown('<div class="kx mcards">' + "".join(cards) + "</div>", unsafe_allow_html=True)
    st.caption(("All-time counts every regular season on Sleeper, this one included. "
                if not FIRST else "The record book joins this page's backs once a season has finished. ")
               + "Playoff and title odds come from the same sim the Playoffs page runs.")


def render_record_book() -> None:
    st.markdown(_ThemeShim.section_head('League <span class="g">Record Book</span>', page=True),
                unsafe_allow_html=True)
    seasons, agg = build_record_book()
    live = season.standings()
    if not seasons:
        st.markdown(
            '<div class="tiny" style="margin-bottom:14px">No season has finished yet, so there is '
            'nothing to look back on. What follows is <b>2026 as it stands</b> - the first page '
            'of the book. It closes when the Chase does, and from then on this page carries every '
            'season before the current one.</div>', unsafe_allow_html=True)
    else:
        champs = {x["champ"] for x in seasons if x["champ"]}
        first = min(x["season"] for x in seasons)
        st.markdown(
            f'<div class="tiny" style="margin-bottom:10px">Since {first} &middot; '
            f'{len(champs)} champion{"s" if len(champs) != 1 else ""} in {len(seasons)} '
            f'season{"s" if len(seasons) != 1 else ""}.</div>', unsafe_allow_html=True)
        st.markdown('<div class="kx chs">' + "".join(
            f'<div class="ch"><em>{x["season"]}</em><b>{esc(x["champ"] or "—")}</b>'
            f'<span>{("over " + esc(x["runner"])) if x.get("runner") else ""}</span></div>'
            for x in seasons) + '</div>', unsafe_allow_html=True)

    theme.bar("All-time standings", "every regular season on record, this one included")
    agg_rows = []
    for r in live:
        o = r["owner_id"]
        a = agg.get(o) or {}
        w, l = a.get("w", 0) + r["wins"], a.get("l", 0) + r["losses"]
        agg_rows.append({"owner": o, "w": w, "l": l,
                         "pf": a.get("pf", 0.0) + r["points_for"],
                         "titles": a.get("titles", 0), "finals": a.get("titles", 0) + a.get("runner", 0),
                         "wp": w / max(1, w + l)})
    agg_rows.sort(key=lambda x: (-x["titles"], -x["wp"], -x["pf"]))
    body = []
    for i, x in enumerate(agg_rows, 1):
        rings = ('<span class="chip acc">&times;%d</span>' % x["titles"]) if x["titles"] else ""
        body.append([
            '<span class="mono">%d</span>' % i,
            '<div style="font-weight:%d">%s</div><div class="tiny">%s</div>' % (
                700 if x["owner"] == VIEW else 550, esc(who(x["owner"])), esc(team_of(x["owner"]))),
            '<span class="mono">%d&ndash;%d</span>' % (x["w"], x["l"]),
            '<span class="mono">%.3f</span>' % x["wp"],
            '<span class="mono">%s</span>' % f'{x["pf"]:,.0f}',
            rings or '<span class="tiny">&mdash;</span>',
        ])
    ledger_table(["", "Manager", "All-time", "Win%", "Points", "Titles"], body,
                 me_row=next((i for i, x in enumerate(agg_rows) if x["owner"] == VIEW), None))

    if seasons:
        theme.bar("Season by season", "")
        for s_ in seasons:
            with st.expander(f'{s_["season"]} — {s_["champ"] or "—"}'):
                ledger_table(["", "Team", "Record", "Points"],
                             [['<span class="mono">%d</span>' % i, esc(r["name"]),
                               '<span class="mono">%d&ndash;%d</span>' % (r["w"], r["l"]),
                               '<span class="mono">%.1f</span>' % r["pf"]]
                              for i, r in enumerate(s_["standings"], 1)])


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


@st.cache_data(ttl=1800, show_spinner=False)
def get_recent_trades(limit: int = 12) -> list:
    """Completed trades, newest first, with every asset each side received.

    Players, picks AND faab - Kreeper's version drops the FAAB leg, which
    doesn't matter there. It matters here: traded FAAB moves a manager's
    entitlement, and that is what keeps the pot honest (halfmen/pot.py).
    """
    r2o = {int(r["roster_id"]): str(r.get("owner_id")) for r in sleeper.get_rosters(LG) or []}
    raw = []
    for wk in range(0, 19):
        try:
            txs = sleeper.get_transactions(LG, wk)
        except Exception:          # noqa: BLE001 - a future week simply has none
            continue
        raw.extend(t for t in (txs or [])
                   if t.get("type") == "trade" and t.get("status") == "complete")
    raw.sort(key=lambda t: t.get("status_updated") or 0, reverse=True)

    out = []
    for tx in raw[:limit]:
        roster_ids = tx.get("roster_ids") or []
        receives = {rid: [] for rid in roster_ids}
        pid_of = {}
        for pid, rid in (tx.get("adds") or {}).items():
            if rid in receives:
                nm = _pname(str(pid))
                receives[rid].append(nm)
                pid_of[nm] = str(pid)
        for pk in (tx.get("draft_picks") or []):
            owner = pk.get("owner_id")
            if owner in receives:
                orig = r2o.get(int(pk.get("roster_id") or 0))
                whose = (who(orig).split() or [""])[0] + "'s " if orig else ""
                receives[owner].append(
                    f'{whose}{pk.get("season")} {_ordinal(int(pk.get("round", 0)))}')
        for wb in (tx.get("waiver_budget") or []):
            to = wb.get("receiver")
            if to in receives:
                frm = r2o.get(int(wb.get("sender") or 0))
                whose = (who(frm).split() or [""])[0] + "'s " if frm else ""
                receives[to].append(f'${int(wb.get("amount") or 0)} of {whose}FAAB')
        teams = [(r2o.get(rid, ""), receives.get(rid, [])) for rid in roster_ids]
        ts = tx.get("status_updated")
        import datetime as _dt
        date = _dt.datetime.fromtimestamp(ts / 1000).strftime("%b %-d, %Y") if ts else ""
        out.append({"teams": teams, "date": date, "pid_of": pid_of})
    return out


def render_trades() -> None:
    st.markdown(_ThemeShim.section_head('The <span class="g">Trades</span>', page=True),
                unsafe_allow_html=True)
    st.caption("Every deal carries the keeper round with it - a traded player costs his new "
               "team the round he was drafted in, not a fresh price. Traded FAAB moves the "
               "spender's entitlement with it, so a dollar can only be owed once.")
    trades = get_recent_trades()
    if not trades:
        st.info("No completed trades on record yet.")
        return

    def chips(assets, pid_of):
        return "".join(
            f'<span class="ktp">{_ph_img(pid_of[a], "ktp-f")}{esc(a)}</span>' if a in pid_of
            else f'<span class="ktp pk">{esc(a)}</span>' for a in assets
        ) or '<span class="ktp pk">nothing</span>'
    cards = []
    for t in trades:
        (oa, aa), (ob, ab) = (t["teams"] + [("", [])])[:2]
        na, nb = who(oa) or "?", who(ob) or "?"
        cards.append(
            f'<div class="tc"><div class="tc-h"><b>{esc(na)}</b><span>traded with</span>'
            f'<b>{esc(nb)}</b><em>{t["date"]}</em></div>'
            f'<div class="tc-c"><div><span class="tl">{esc(na)} gets</span>'
            f'{chips(aa, t.get("pid_of", {}))}</div>'
            f'<div class="tc-x">&#8644;</div><div><span class="tl">{esc(nb)} gets</span>'
            f'{chips(ab, t.get("pid_of", {}))}</div></div></div>')
    st.markdown('<div class="kx">' + "".join(cards) + '</div>', unsafe_allow_html=True)

    moved = pot.faab_trades(LG)
    if moved:
        theme.bar("FAAB that changed hands", "it moves the entitlement, not just the balance")
        ledger_table(["From", "To", "Amount"],
                     [[esc(who(m["from"])), esc(who(m["to"])), '<span class="mono">$%d</span>' % m["amount"]]
                      for m in moved])


@st.cache_data(ttl=1800, show_spinner=False)
def finished_week_points(through: int) -> dict:
    """{week: {owner: starter points}} for every FINISHED week before `through`.

    One pass, cached: the awards below ask the same question of the same weeks
    twice over, and each uncached week is a full matchup context.
    """
    out = {}
    for wk in range(1, max(1, through)):
        try:
            if not season.week_is_final(LG, wk):
                continue
            ctx = get_week_ctx(wk)
        except Exception:          # noqa: BLE001 - one bad week shouldn't lose the page
            continue
        pts = {o: sum(sd["actual"].get(p, 0.0) for p in sd["starters"] if p and p != "0")
               for o, sd in ctx["sides"].items()}
        if len(pts) >= 2:
            out[wk] = pts
    return out


def _talent(rank) -> float:
    """Draft-value curve, the #1 player ~ 100 - the same units keeper value is in."""
    return 100.0 * (0.965 ** (max(1.0, float(rank)) - 1)) if rank else 4.0


def render_trade_analyzer() -> None:
    """Build a deal and grade it the way this league prices players: what he
    is worth now, plus what his contract is worth to keep - because the round
    he keeps at travels with him. FAAB is shown for what it does to the pot,
    not folded into the grade: a traded dollar is spending room, not a debt."""
    st.markdown(_ThemeShim.section_head('Trade <span class="g">analyzer</span>',
                                        "grade a deal before you send it", page=True),
                unsafe_allow_html=True)
    cur = season.current_week() or 1
    dl = str((config.settled().get("votes") or {}).get("deadline", {}).get("answer") or "")
    dl_wk = int(re.sub(r"\D", "", dl) or 0) or None
    if dl_wk:
        left = dl_wk - cur
        st.markdown('<div class="tiny" style="margin:-4px 0 10px">Trade deadline: <b>week %d</b> &mdash; %s.'
                    '</div>' % (dl_wk, "%d week%s left" % (left, "s" if left != 1 else "") if left > 0
                                else "this is the last week" if left == 0 else "passed"),
                    unsafe_allow_html=True)
    rows_by_pid = {str(r["player_id"]): r for r in value_rows()}
    pmap = players_map()
    rosters = {str(r.get("owner_id")): r.get("players") or [] for r in (state["rosters"] or [])}
    ids = list(config.managers())
    label = {o: "%s — %s" % (team_of(o), who(o)) for o in ids}
    c1, c2 = st.columns(2)
    with c1:
        a = st.selectbox("Team A", ids, index=ids.index(VIEW) if VIEW in ids else 0,
                         format_func=lambda o: label[o], key="ta_a")
    with c2:
        others = [o for o in ids if o != a]
        b = st.selectbox("Team B", others, format_func=lambda o: label[o], key="ta_b")

    nxt = SEASON + 1
    pick_years = [nxt, nxt + 1]
    owned = {y: draftboard.owned_rounds(LG, y) for y in pick_years}

    def pick_value(year, rnd):
        n = len(ids)
        return _talent((rnd - 1) * n + n // 2) * (0.8 ** (year - nxt))

    def player_opts(o):
        out = {}
        for pid in rosters.get(o, []):
            m = pmap.get(str(pid)) or {}
            if m.get("position") in ("QB", "RB", "WR", "TE"):
                out[str(pid)] = "%s (%s)" % (m.get("full_name") or pid, m.get("position"))
        return dict(sorted(out.items(), key=lambda kv: kv[1]))

    def pick_opts(o):
        out = {}
        for y in pick_years:
            for rnd, cnt in sorted((owned[y].get(o) or {}).items()):
                for k in range(max(0, cnt)):
                    out["%d|%d|%d" % (y, rnd, k)] = "%d R%d%s" % (y, rnd, " (#%d)" % (k + 1) if cnt > 1 else "")
        return out

    def budget_left(o):
        r = next((x for x in season.standings() if x["owner_id"] == o), None)
        return int(r["budget_left"]) if r else 0

    sides = {}
    for col, o, other in ((c1, a, b), (c2, b, a)):
        with col:
            po, pk = player_opts(o), pick_opts(o)
            pl = st.multiselect("%s sends — players" % team_of(o), list(po), format_func=lambda x, po=po: po[x],
                                key="ta_pl_%s" % o)
            pc = st.multiselect("%s sends — picks" % team_of(o), list(pk), format_func=lambda x, pk=pk: pk[x],
                                key="ta_pk_%s" % o)
            fb = st.number_input("%s sends — FAAB $" % team_of(o), 0, max(0, budget_left(o)), 0,
                                 key="ta_fb_%s" % o)
            sides[o] = {"players": pl, "picks": pc, "faab": int(fb), "po": po, "pk": pk}

    if not any(sides[o]["players"] or sides[o]["picks"] or sides[o]["faab"] for o in (a, b)):
        st.info("Pick players, picks or FAAB for each side to grade the deal.")
        return

    def worth(pid):
        r = rows_by_pid.get(str(pid)) or {}
        rank = r.get("adp_rank") or valueboard._market_rank(str(pid), pmap)
        talent = _talent(rank if rank and rank < 1e9 else None)
        keep = max(0, r.get("surplus") or 0) if r.get("eligible") else 0
        return talent, keep, r

    def receives(o_from):
        sd = sides[o_from]
        lines, total = [], 0.0
        for pid in sd["players"]:
            t, k, r = worth(pid)
            total += t + k
            price = ("keeps at R%d" % r["cost"]) if r.get("cost") and r.get("eligible") else (
                "can't be kept" if r else "price unknown")
            lines.append((sd["po"][pid], t + k, "%s &middot; %d now + %d contract" % (price, round(t), round(k))))
        for key in sd["picks"]:
            y, rnd, _k = (int(x) for x in key.split("|"))
            v = pick_value(y, rnd)
            total += v
            lines.append((sd["pk"][key], v, "a pick" + (" a year out, discounted" if y > nxt else "")))
        return total, lines

    a_gets, a_lines = receives(b)
    b_gets, b_lines = receives(a)
    diff = a_gets - b_gets
    even = abs(diff) <= max(10, 0.08 * max(a_gets, b_gets, 1))
    verdict = "Even deal" if even else "Edge to %s" % _first(a if diff > 0 else b)
    share = 100 * a_gets / max(1.0, a_gets + b_gets)
    st.markdown(
        f'<div class="kx xb"><div class="xb-s me"><div class="xb-t"><span>{esc(team_of(a))} receives</span>'
        f'<b>{round(a_gets)}</b><i>{len(a_lines)} asset{"s" if len(a_lines) != 1 else ""}</i></div></div>'
        f'<div class="xb-m"><span class="xb-k">trade grade</span><b style="font-size:40px">{verdict}</b>'
        f'<em>{"both sides roughly equal" if even else "by about %d" % abs(round(diff))}</em>'
        f'<div class="xb-bar"><i style="width:{share:.0f}%"></i></div></div>'
        f'<div class="xb-s op"><div class="xb-t"><span>{esc(team_of(b))} receives</span>'
        f'<b>{round(b_gets)}</b><i>{len(b_lines)} asset{"s" if len(b_lines) != 1 else ""}</i></div></div></div>',
        unsafe_allow_html=True)

    cc1, cc2 = st.columns(2)
    for col, o, lines in ((cc1, a, a_lines), (cc2, b, b_lines)):
        with col:
            st.markdown('<div class="weyebrow pad">%s gets</div><div class="kx">' % esc(team_of(o)) + "".join(
                f'<div class="ta-l"><b>{esc(n)}</b><em>{round(v)}</em><span>{d}</span></div>'
                for n, v, d in lines) + '</div>' if lines else "", unsafe_allow_html=True)

    # FAAB: what it does to the pot, which is the part people get wrong
    for o_from, o_to in ((a, b), (b, a)):
        amt = sides[o_from]["faab"]
        if amt:
            st.markdown(
                '<div class="banner"><b>$%d of FAAB from %s to %s.</b> It is spending room, not money '
                'owed: %s can now spend up to $%d more, and %s&rsquo;s ceiling drops by the same. Nobody owes '
                'a dollar of it until it is bid on a player &mdash; and the pot only ever counts what was '
                'actually spent, so the trade itself moves nothing into it.</div>' % (
                    amt, esc(_first(o_from)), esc(_first(o_to)), esc(_first(o_to)), amt, esc(_first(o_from))),
                unsafe_allow_html=True)
    st.caption("Grade = talent now (the draft-value curve, #1 ≈ 100) + what his contract is worth to keep, "
               "for every player; picks by the round's typical value, next year's at a 20% discount. "
               "A kept player costs his new team the round he was drafted in, landing on the nearest "
               "pick they own. It doesn't model roster need.")


def _render_bid_helper() -> None:
    """What a FAAB bid costs you before you place it. In this league you owe
    what you spend, so a bid is a real-money decision - and where that money
    ends up (the Chase winner up to the cap, the bracket after it) is worth
    seeing at the moment you type the number."""
    rows = season.standings()
    me = next((r for r in rows if r["owner_id"] == VIEW), None)
    if not me:
        return
    spent_all = sum(r["spent"] for r in rows)
    cap = int(pot.cap_amount()[0])
    left = int(me["budget_left"])
    theme.bar("Before you bid", "what it adds to your bill, and where the money goes")
    c1, c2 = st.columns([1, 2])
    with c1:
        bid = st.number_input("Your bid ($)", 0, max(0, left), min(10, left), key="bid_helper",
                              disabled=left <= 0)
    to_chase = max(0, min(int(bid), cap - spent_all))
    over = int(bid) - to_chase
    ov = config.overflow_split()
    with c2:
        if bid:
            split = ", ".join("$%.0f to the %s" % (over * ov[k] / 100.0, n) for k, n in
                              (("first", "champion"), ("second", "runner-up"),
                               ("third", "third place"), ("chase", "Chase winner")) if ov.get(k)) if over else ""
            st.markdown(
                '<div class="kx bidh"><div><span>Your bill</span><b>$%d &rarr; $%d</b></div>'
                '<div><span>Budget left</span><b>$%d &rarr; $%d</b></div>'
                '<div><span>The pot</span><b>$%d &rarr; $%d</b></div></div>'
                '<div class="tiny" style="margin-top:6px">%s%s</div>' % (
                    me["spent"], me["spent"] + int(bid), left, left - int(bid), spent_all, spent_all + int(bid),
                    ("$%d of it fills the Chase winner&rsquo;s $%d. " % (to_chase, cap)) if to_chase else
                    "The Chase winner&rsquo;s $%d is already full. " % cap,
                    ("$%d runs over into the bracket: %s." % (over, split)) if over else ""),
                unsafe_allow_html=True)
        else:
            st.markdown('<div class="tiny">Type a bid to see your bill and where the money goes.</div>',
                        unsafe_allow_html=True)


def render_alerts() -> None:
    """Your lineup problems, on every page: an Out or high-risk starter whose
    game hasn't kicked off, an empty slot, a starter on bye, or a swap worth
    real points. One line, linked to Matchup - silent when there's nothing."""
    try:
        cur = season.current_week()
        if not cur or _phase() != "in_season":
            return
        aw = gameday.advice_week(cur, get_week_ctx(cur)["games"])
        adv = _advice(VIEW, aw)
    except Exception:          # noqa: BLE001 - an alert must never take a page down
        return
    if not adv:
        return
    ctx_ = adv["ctx"]
    _pos, team_of_ = _pos_team_maps()
    starters = [p for p in adv["side"]["starters"] if p and p != "0"]
    unlocked = [p for p in starters
                if gameday.status(ctx_["games"], team_of_.get(p, "")) not in ("in", "post")]
    items = []
    for p in unlocked:
        r = _risk(ctx_, p)
        if r["level"] == "out":
            items.append("<b>%s</b> is %s" % (esc(_pname(p)), esc(r["label"] or "out")))
        elif r["level"] == "high":
            items.append("<b>%s</b> is %s (%s%% risk)" % (esc(_pname(p)), esc(r["label"] or "a doubt"), r["pct"]))
    byes = [p for p in adv["byes"] if p in starters]
    if byes:
        items.append("<b>%s</b> on bye" % ", ".join(esc(_pname(p)) for p in byes[:2]))
    for h in adv["holes"]:
        items.append("no <b>%s</b>" % esc(h))
    big = [x for x in adv["swaps"] if x[2] >= 3]
    if big and not items:
        i, o, g = big[0]
        items.append("start <b>%s</b> over %s (+%.1f)" % (esc(_pname(i)), esc(_pname(o)), g))
    if not items:
        return
    st.markdown(
        '<a class="alert-strip" href="?p=inseason&g=week&t=matchup%s" target="_self">'
        '<span>Week %d</span>%s<em>Fix it on Matchup &rarr;</em></a>' % (
            _keep(), aw, " &middot; ".join(items[:3])), unsafe_allow_html=True)


def render_keeper_deadline() -> None:
    """The keeper-slip countdown, while slips are open. Driven entirely by
    league.keeper_deadline in config.yaml - silent until it is set."""
    when = phase.keeper_deadline()
    if not when:
        return
    import datetime as _dt
    now = _dt.datetime.now(when.tzinfo)
    if now >= when:
        return
    left = when - now
    days = left.days
    hrs = left.seconds // 3600
    big = ("%d day%s" % (days, "s" if days != 1 else "")) if days else ("%d hour%s" % (hrs, "s" if hrs != 1 else ""))
    st.markdown(_bh("royal", "Keeper slips · due %s" % when.strftime("%a %-d %b, %-I:%M %p"), big,
                    "to lock your %d keepers &mdash; %d regular, %d rookie, franchise tag if you are using it. "
                    '<a href="?p=offseason&g=keepers&t=slip%s" target="_self" style="color:inherit">Set my keepers &rarr;</a>'
                    % (int(config.keeper_rules()["regular"]) + int(config.keeper_rules()["rookie"]),
                       int(config.keeper_rules()["regular"]), int(config.keeper_rules()["rookie"]), _keep())),
                unsafe_allow_html=True)


def render_superlatives() -> None:
    """The league's awards, all of them read off data already on other pages.

    Written for this league rather than ported: Kreeper's version leans on its
    own ADP-movement feed and draft-capital builders, neither of which means
    anything here in October of season one.
    """
    st.markdown(_ThemeShim.section_head('<span class="g">Superlatives</span>', page=True),
                unsafe_allow_html=True)
    table = season.standings()
    cur = season.current_week()
    cards = []

    def card(title, winner, sub, cls=""):
        cards.append(f'<div class="sup{" " + cls if cls else ""}">{_mgr_face(winner) if winner else ""}'
                     f'<div><span>{title}</span><b>{esc(who(winner)) if winner else "&mdash;"}</b>'
                     f'<i>{sub}</i></div></div>')

    try:
        board = [r for r in value_rows()
                 if r.get("eligible") and r.get("cost") and r.get("surplus") is not None]
    except Exception:              # noqa: BLE001
        board = []
    if board:
        top = board[0]
        card("Biggest keeper steal", top["owner_id"],
             f'{esc(top["name"])} at R{top["cost"]} &middot; {theme.signed(top["surplus"])}')

    if cur:
        try:
            sim = (get_playoff_outlook(None, cur).get("sim") or {}).get("teams") or {}
        except Exception:          # noqa: BLE001
            sim = {}
        if sim:
            fav = max(sim.items(), key=lambda kv: kv[1].get("title_pct", 0))
            card("Title favourite", fav[0],
                 f'{fav[1].get("title_pct", 0):.1f}% to win it &middot; '
                 f'{fav[1].get("playoff_pct", 0)}% to make the bracket')

    # Luck: this league plays the median every week, so "expected wins" has to
    # count both results. A team's expected H2H wins in a week is the share of
    # the league it outscored; the median win is simply scoring above it.
    weeks = finished_week_points(cur or 1)
    exp = {r["owner_id"]: 0.0 for r in table}
    for pts in weeks.values():
        order = sorted(pts.values())
        mid = (order[len(order) // 2 - 1] + order[len(order) // 2]) / 2
        for o, v in pts.items():
            beat = sum(1 for x in pts.values() if v > x)
            exp[o] = exp.get(o, 0.0) + beat / (len(pts) - 1) + (1.0 if v > mid else 0.0)
    played = len(weeks)
    if played:
        luck = sorted(((r["owner_id"], r["wins"] - exp.get(r["owner_id"], 0.0)) for r in table),
                      key=lambda kv: kv[1])
        unl, lk = luck[0], luck[-1]
        card("Unluckiest", unl[0],
             f'{dict((r["owner_id"], r["wins"]) for r in table)[unl[0]]} wins on '
             f'{exp[unl[0]]:.1f} expected', "bad")
        card("Luckiest", lk[0],
             f'{dict((r["owner_id"], r["wins"]) for r in table)[lk[0]]} wins on '
             f'{exp[lk[0]]:.1f} expected')

    best_wk = None
    for wk, pts in weeks.items():
        for o, v in pts.items():
            if best_wk is None or v > best_wk[2]:
                best_wk = (o, wk, v)
    if best_wk:
        card("Biggest week", best_wk[0], f'{best_wk[2]:.1f} in week {best_wk[1]}')

    spenders = [r for r in table if r["spent"]]
    if spenders:
        big = max(spenders, key=lambda r: r["spent"])
        card("Deepest pockets", big["owner_id"],
             f'${int(big["spent"])} of FAAB spent &middot; that is ${int(big["spent"])} he owes the pot')
    quiet = [r for r in table if not r["spent"]]
    if quiet and spenders:
        card("Tightest wallet", max(quiet, key=lambda r: r["points_for"])["owner_id"],
             "has not spent a dollar of FAAB all season")

    try:
        pods = season.taxi() or []
    except Exception:              # noqa: BLE001
        pods = []
    if pods:
        full = max(pods, key=lambda t: t["used"])
        if full["used"]:
            card("Best stocked taxi", full["owner_id"],
                 f'{full["used"]} rookie{"s" if full["used"] != 1 else ""} parked for the season')
        wasting = [t for t in pods if t.get("wasting")]
        if wasting:
            card("Left a slot empty", wasting[0]["owner_id"],
                 f'{wasting[0]["open"]} taxi slot{"s" if wasting[0]["open"] != 1 else ""} open '
                 f'with a rookie who could have filled {"them" if wasting[0]["open"] != 1 else "it"}',
                 "bad")


    st.markdown('<div class="kx sups">' + "".join(cards) + "</div>", unsafe_allow_html=True)
    st.caption("Expected wins account for the median match: your share of the league you "
               "outscored, plus the median win if you cleared it. Everything here comes off "
               "finished weeks only - this week's games are still moving.")


def render_league(leaf=None):
    {"managers": render_managers, "record": render_record_book,
     "trades": render_trades, "analyzer": render_trade_analyzer,
     "superlatives": render_superlatives}.get(
        leaf or "managers", render_managers)()


PAGES = {"home": render_home, "rules": render_rules}
GROUP_PAGES = {"week": render_week, "keepers": render_keepers, "draft": render_draft,
               "lottery": render_lottery, "wire": render_keepers, "pot": render_pot,
               "taxi": render_taxi_league,
               "playoffs": lambda leaf=None: render_chase() if leaf == "chase" else render_playoffs(),
               "league": render_league}

player_data_warning()
if not (PAGE == "home" or (PAGE == "inseason" and GROUP == "week" and LEAF in ("matchup", None))):
    render_alerts()        # Home and Matchup already lead with the full to-do

if PAGE in PAGES:
    PAGES[PAGE]()
else:
    GROUP_PAGES[GROUP](LEAF)

render_bottom_bar()
