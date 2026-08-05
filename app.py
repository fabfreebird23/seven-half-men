"""7 1/2 Men - keeper dashboard.

Six sections: Home, Keepers, Taxi Bay, The Pot, Draft, Lottery.

The league starts in 2026 with empty rosters and no keepers, so most screens
have two modes: a "season one" state that shows the rule and what it will do,
and the live state once there is data behind it. The engine underneath is the
full ruleset either way - nothing here is stubbed for year one.
"""
from __future__ import annotations

import html
import json
import math
from collections import Counter
from typing import Dict, List, Optional

import streamlit as st
import streamlit.components.v1 as components

from halfmen import (adp_board, config, draftboard, engine, history, lottery,
                     pot, rulebook, sleeper, storage, taxi, theme, valueboard)

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


@st.cache_data(ttl=1800, show_spinner=False)
def owned_map() -> Dict[str, Counter]:
    try:
        return draftboard.owned_rounds(LG, SEASON)
    except Exception:
        rounds = config.veteran_rounds()
        return {o: Counter({r: 1 for r in range(1, rounds + 1)}) for o in config.managers()}


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

head_l, head_r = st.columns([3, 2])
with head_l:
    theme.masthead("%d \u00b7 %s" % (SEASON, "season one" if FIRST else "offseason"))
with head_r:
    _ids = owner_ids()
    VIEW = _viewer()
    _picked = st.selectbox(
        "Viewing as", _ids, index=_ids.index(VIEW) if VIEW in _ids else 0,
        format_func=lambda o: "%s \u00b7 %s" % (who(o), team_of(o)),
        label_visibility="collapsed", key="viewer")
    if _picked != VIEW:
        st.query_params["team"] = _picked
        st.rerun()
    VIEW = _picked

# ---------------------------------------------------------------------------
# navigation
#
# Grouped by season PHASE rather than by content type, and routed entirely
# through ?p=&g=&t= so the bottom bar can deep-link to a leaf instead of
# dropping you at the top of a page and making you scroll past three other
# sections. Same shape the Kreeper and Babies & Boomer apps converged on.
# ---------------------------------------------------------------------------

GROUPS = {
    "preseason": [
        ("keepers", "Keepers", [("matrix", "Where the value is"),
                                ("slip", "Set my keepers"),
                                ("franchise", "Franchise tag")]),
        ("draft", "Draft", [("board", "Draft board"),
                            ("locks", "What a pick locks you into"),
                            ("capital", "Draft capital")]),
        ("young", "Rookies & Taxi", [("bay", "Taxi bay"),
                                     ("compliance", "Taxi compliance"),
                                     ("counts", "Who counts as a rookie keeper")]),
        ("lottery", "Lottery", [("drums", "The drums"),
                                ("sim", "Simulate"),
                                ("guards", "The guardrails")]),
    ],
    "inseason": [
        ("wire", "The Wire", [("value", "Value board"),
                              ("cheap", "Cheapest available")]),
        ("pot", "The Pot", [("burn", "Burn-down"),
                            ("settle", "Settlement")]),
    ],
}
SECTIONS = [("home", "Home"), ("preseason", "Pre-Season"),
            ("inseason", "In-Season"), ("rules", "Rules")]


def _qp(key: str, default: str = "") -> str:
    v = st.query_params.get(key)
    return str(v[0] if isinstance(v, list) else (v or default))


PAGE = _qp("p", "home")
if PAGE not in dict(SECTIONS):
    PAGE = "home"
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
        chips.append('<span class="chip">ADP R%d</span>' % p.adp_round)
    if p.bumped:
        chips.append('<span class="chip warn">Bumped from R%d</span>' % p.base_round)
    if sur is not None:
        chips.append('<span class="chip %s">%s rd surplus</span>' % (
            "good" if sur > 0 else "bad" if sur < 0 else "", theme.signed(sur)))

    price = ('<div class="rd">R%d</div><div class="sub">cost</div>' % p.final_round
             if p.final_round else '<div class="rd">&mdash;</div><div class="sub">no price</div>')

    return ('<div class="contract %s"><div class="who">'
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
    ("The price climbs", "Year 1 the cheaper of your draft round or ADP. Year 2 your draft "
                         "round minus three, or ADP. Year 3 ADP, no choice. Year 4 is the wall."),
    ("Franchise tag", "One player, years four and five, frozen at the most expensive round you "
                      "have ever paid for him. Gone after year five. It still uses a keeper slot."),
    ("Rookie keepers", "Any NFL rookie you <b>drafted</b> — rookie draft or veteran draft, not a "
                       "waiver pickup. Costs your last picks, no clock, yours for his career. "
                       "Trade him and he becomes a regular keeper at his original draft round "
                       "with the clock back at year one."),
    ("Owning the pick", "A keeper lands on a round you actually hold. If it is gone he bumps to "
                        "the next-earliest round you own. The price travels with the player on a "
                        "trade — an R7 keeper is an R7 again for an owner who has their R7."),
    ("Taxi", "Two slots, two-year clocks, that year's rookie draft only. Never startable. "
             "Promotion is permanent."),
    ("The pot", "Unspent FAAB comes due. The first $%d goes to the Chase-bracket winner and "
                "everything above it goes to the champion." % int(config.faab_rules()["pot_cap"])),
    ("Two lotteries", "Rookie drum on regular-season record, veteran drum on final standing "
                      "including the Chase bracket. Champion always at the floor. Nobody wins "
                      "first choice in both. Win a top-two selection and you sit out the top two "
                      "next year."),
]


# ---------------------------------------------------------------------------
# HOME
# ---------------------------------------------------------------------------

def render_home(leaf=None):
    rosters = state["rosters"] or []
    filled = sum(1 for r in rosters if (r.get("players") or []))
    n_managers = len(config.managers())

    if FIRST:
        st.markdown(
            '<div class="banner"><b>Season one.</b> Empty rosters, nobody has held anyone yet, '
            'and every clock starts at zero after this year. The rookie draft runs first (%d '
            'rounds), then the veteran draft (%d rounds). Both orders are drawn flat at random — '
            'there are no standings to weight a lottery with. The keeper machinery below is live '
            'and priced off real ADP, so you can already see what a pick will cost you to hold.'
            '</div>' % (config.rookie_rounds(), config.veteran_rounds()),
            unsafe_allow_html=True)

    theme.bar("The league", "%s · %s" % (esc(lg.get("name") or ""),
                                         esc((lg.get("status") or "").replace("_", " "))))
    glance([
        {"pct": n_managers / 8.0, "color": "var(--acc)", "big": str(n_managers),
         "label": "Managers", "note": "all 8 seats filled"},
        {"pct": (filled / max(1, len(rosters))), "color": "var(--acc2)",
         "big": str(filled),
         "label": "Rosters", "note": "0 of 8 \u2014 they fill at the draft"},
        {"pct": min(1.0, adp_board.size() / 300.0), "color": "var(--acc2)",
         "big": str(adp_board.size()),
         "label": "ADP board", "note": "players on the consensus board, refreshed daily"},
        {"pct": 1.0, "color": "var(--good)", "big": str(config.veteran_rounds()),
         "label": "Vet draft", "note": "rounds \u2014 13 in year one so a rookie can be promoted"},
    ])

    theme.bar("Who's in", "%d managers" % n_managers)
    rows = []
    for oid in owner_ids():
        rows.append([
            '<div style="font-weight:650">%s</div><div class="tiny">%s</div>' % (
                esc(who(oid)), esc(team_of(oid))),
            '<span class="chip good">in</span>' if oid in {str(r.get("owner_id")) for r in rosters}
            else '<span class="chip warn">pending</span>',
        ])
    ledger_table(["Owner", "Roster"], rows,
                 me_row=owner_ids().index(VIEW) if VIEW in owner_ids() else None)



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
    st.markdown('<div class="toc">%s</div>' % "".join(
        '<a href="#%s">%s</a>' % (a, esc(t)) for a, t, _, _ in secs), unsafe_allow_html=True)

    for anchor_id, title, stand, blocks in secs:
        theme.bar(title, "")
        st.markdown(
            '<div class="rule" id="%s"><div class="stand">%s</div>%s</div>' % (
                anchor_id, stand, "".join(render_block(*b) for b in blocks)),
            unsafe_allow_html=True)


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
    if FIRST:
        st.markdown(
            '<div class="banner"><b>Nothing to keep yet.</b> Your first slip is due after this '
            'season. What matters right now is the draft: where you take a player decides what he '
            'costs you to hold for the next three years, and the gap between that price and what '
            'he turns out to be worth is the only thing that ever makes a keeper worth a '
            'slot.</div>', unsafe_allow_html=True)

    if leaf in (None, "matrix"):
        theme.bar("Where the value is", "rounds banked over a three-year hold")
        st.markdown(
            '<div class="note" style="margin-bottom:12px">Rows are the round you draft him in. '
            'Columns are what he turns into. The cell is the rounds of value you bank across the '
            'whole three-year run, before he hits the wall. Two things fall out of it: a pick that '
            'performs exactly to its draft slot is worth <b>nothing</b> to keep, and year three is '
            'always priced at the market, so every rounds of profit you will ever make comes from '
            'years one and two.</div>', unsafe_allow_html=True)

        becomes_cols = [1, 2, 3, 5, 8]
        head = ["Drafted in"] + ["Becomes an R%d" % b for b in becomes_cols]
        rows = []
        for r in range(1, config.veteran_rounds() + 1):
            cells = ['<span class="mono" style="font-weight:700">R%d</span>' % r]
            for b in becomes_cols:
                if b >= r:
                    cells.append('<span class="tiny">-</span>')
                    continue
                v = three_year_surplus(r, b)
                cells.append('<span class="surplus %s">%s</span>' % (
                    theme.surplus_class(v), theme.signed(v)))
            rows.append(cells)
        ledger_table(head, rows)
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
    if leaf in (None, "slip"):
        theme.bar("Your slip", "%d regular · %d rookie · %d franchise" % (
            int(kr["regular"]), int(kr["rookie"]), int(config.franchise_rules()["slots"])))
        my_roster = next((r for r in (state["rosters"] or [])
                          if str(r.get("owner_id")) == VIEW), None)
        my_players = (my_roster or {}).get("players") or []
        if not my_players:
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
                dr = hist.draft_round(str(pid)) or config.veteran_rounds()
                from_rookie = hist.has_rookie_draft_provenance(str(pid))
                if hist.is_rookie_keeper_eligible(str(pid)):
                    prices.append(engine.price_rookie(
                        str(pid), name, meta.get("position") or "", slot=0,
                        last_round=config.veteran_rounds(), adp_round=adp))
                else:
                    # A rookie-draft player has no veteran round; the premium stands
                    # in for one and price_regular ignores draft_round entirely.
                    prices.append(engine.price_regular(
                        str(pid), name, meta.get("position") or "",
                        draft_round=hist.keeper_anchor(str(pid)) or dr, year=yr,
                        adp_round=adp, from_rookie_draft=from_rookie))
            engine.allocate(prices, owned)
            slip = engine.best_slip(prices)
            st.markdown("".join(contract_card(p) for p in slip), unsafe_allow_html=True)
            errs = engine.validate(slip)
            if errs:
                for e in errs:
                    st.markdown('<div class="banner" style="border-color:var(--bad);'
                                'color:var(--bad)">%s</div>' % esc(e), unsafe_allow_html=True)
            st.markdown('<div class="card" style="margin-top:10px"><div class="eyebrow">'
                        'Total surplus vs. market</div><div style="font-family:var(--f-display);'
                        'font-size:30px">%s rounds</div></div>' % theme.signed(
                            engine.total_surplus(slip)), unsafe_allow_html=True)


        # ---------------------------------------------------------------- value board
    if leaf in (None, "value", "cheap"):
        # Both destinations price off the same history, so build it once out
        # here - the wire needs it even when the rostered board is not shown.
        try:
            hist_all = history.build(LG)
            board = valueboard.rows(LG, SEASON, hist=hist_all)
        except Exception:
            hist_all, board = None, []

        if leaf in (None, "value"):
            theme.bar("Value board", "what everyone would cost to keep next year")

            if board:
                scope = st.radio("Scope", ["Whole league", "Just my team"],
                                 horizontal=True, label_visibility="collapsed", key="vb_scope")
                shown = board if scope == "Whole league" else [
                    r for r in board if r["owner_id"] == VIEW]
                rows_vb = []
                for r in shown[:60]:
                    sur = r["surplus"]
                    chips = []
                    if r["kind"] == "rookie":
                        chips.append('<span class="chip mag">rookie</span>')
                    if r["from_rookie_draft"]:
                        chips.append('<span class="chip acc">R%d</span>' % engine.rookie_draft_premium())
                    if r["bumped"]:
                        chips.append('<span class="chip warn">bumped</span>')
                    if not r["eligible"]:
                        chips.append('<span class="chip bad">wall</span>')
                    rows_vb.append([
                        '<div style="font-weight:650">%s</div><div class="tiny">%s &#183; %s</div>' % (
                            esc(r["name"]), esc(r["position"]), esc(team_of(r["owner_id"]))),
                        '<span class="mono">%s</span>' % ("R%d" % r["cost"] if r["cost"] else "&mdash;"),
                        '<span class="mono">%s</span>' % ("R%d" % r["adp"] if r["adp"] else "&mdash;"),
                        '<span class="surplus %s">%s</span>' % (
                            theme.surplus_class(sur), theme.signed(sur)),
                        " ".join(chips),
                    ])
                ledger_table(["Player", "Costs", "Market", "Surplus", ""], rows_vb)
                st.markdown(
                    '<div class="tiny" style="margin-top:8px">Sorted by surplus, which is the only number '
                    'that decides whether a slot is worth spending. Prices include the bump, so they are '
                    'true in the context of the rest of that manager\'s slip rather than in isolation.'
                    '</div>', unsafe_allow_html=True)
            else:
                st.markdown(
                    '<div class="banner"><b>Nobody is on a roster yet.</b> The moment the veteran draft '
                    'ends this fills with every player in the league, priced for whoever holds him and '
                    'sorted by surplus \u2014 which is the thing worth checking before you spend FAAB in '
                    'week 6, because a claim here is the first year of a three-year contract.</div>',
                    unsafe_allow_html=True)

        if leaf in (None, "cheap") and (
                not FIRST or (state["rosters"]
                              and any(r.get("players") for r in state["rosters"]))):
            theme.bar("Cheapest available", "unrostered, priced as if you claimed him today")
            try:
                fa = valueboard.free_agents(LG, limit=20, hist=hist_all)
            except Exception:
                fa = []
            ledger_table(["Player", "Costs", "Market", "Surplus", ""], [[
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

        # ---------------------------------------------------------------- franchise
    if leaf in (None, "franchise"):
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
            st.markdown("".join(
                '<div class="contract %s"><div class="who">'
                '<div class="nm">%s <span class="tiny">%s</span></div>'
                '<div class="meta">%s &#183; frozen at R%d &#183; market R%d</div>'
                '<div class="tags2">%s<span class="chip">Freeze R%d</span>'
                '<span class="chip">ADP R%d</span></div></div>'
                '<div class="price"><div class="rd" style="color:%s">%s</div>'
                '<div class="sub">rds over yr %d-%d</div></div></div>' % (
                    "fr" if c is best and c["banked"] > 0 else "",
                    esc(c["name"]), esc(c["position"]),
                    ("year %d \u2014 at the wall" % c["year"]) if c["at_the_wall"]
                    else "year %d \u2014 not eligible until year %d" % (
                        c["year"], int(kr["max_years"]) + 1),
                    c["frozen"], c["adp"],
                    '<span class="chip solid">Tag this one</span>'
                    if c is best and c["banked"] > 0 and c["at_the_wall"] else "",
                    c["frozen"], c["adp"],
                    "var(--good)" if c["banked"] > 0 else "var(--dim)",
                    theme.signed(c["banked"]), int(kr["max_years"]) + 1,
                    int(kr["max_years"]) + int(config.franchise_rules()["extra_years"]))
                for c in cands[:6]), unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="banner"><b>Nobody is eligible, and nobody will be until %d.</b> The tag '
                'only does anything for a player who has already been kept three times, so the first '
                'real decision is four offseasons away. What it will rank then is which of your '
                'year-four players banks the most, and the answer is counterintuitive: the freeze is '
                'at the <em>most expensive</em> round you ever paid, so the tag is worth the most on a '
                'late find whose market ran away from him and exactly nothing on a career '
                'first-rounder.</div>' % (SEASON + int(kr["max_years"]) + 1),
                unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# TAXI BAY
# ---------------------------------------------------------------------------

def render_taxi(leaf=None):
    tr = config.taxi_rules()
    if leaf in (None, "bay"):
        theme.bar("Taxi bay", "%d slots · %d-year clocks · promotion is permanent" % (
            int(tr["slots"]), int(tr["years"])))
        bays = {}
        try:
            bays = taxi.build(LG, SEASON)
        except Exception:
            bays = {}

        if not any(b.pods for b in bays.values()):
            st.markdown('<div class="banner"><b>%s</b><br>%s Nothing is stashed yet — the bays fill '
                        'from this year\'s rookie draft.</div>' % (
                            esc(taxi.eligibility_note()), esc(taxi.promote_cost_note())),
                        unsafe_allow_html=True)

        st.markdown(
            '<div class="banner" style="margin-top:10px;border-style:solid;border-color:var(--acc)">'
            '<b>Stashing costs you nothing but time.</b> Taxi burns no keeper slot and no bench spot, '
            'and promoting a player off it — in year one or year two — leaves his rookie-keeper '
            'designation intact. He keeps the last-round price and the no-clock; he just stops being '
            'free and starts costing one of your %d rookie keeper slots. So a taxi stint is a free '
            'two-year option on a rookie keeper, not a gamble on one. The scarce thing is the slot, '
            'not the player.</div>' % int(config.keeper_rules()["rookie"]),
            unsafe_allow_html=True)

        mine = bays.get(VIEW) or taxi.Bay(owner_id=VIEW, pods=[])
        mine.incoming_picks = config.rookie_rounds()
        theme.bar("Your bay", "%d of %d filled \u00b7 %d rookie picks incoming" % (
            len(mine.pods), mine.slots, mine.incoming_picks))
        pods = []
        for i in range(mine.slots):
            if i < len(mine.pods):
                pod = mine.pods[i]
                last = pod.year >= int(tr["years"])
                pods.append(theme.taxi_pod(
                    pod.name, pod.position, "slot %d" % (i + 1), pod.year, int(tr["years"]),
                    note=("Clock is up. Promote him \u2014 permanent, and he starts costing a rookie "
                          "keeper slot \u2014 or release him." if last else
                          "One more year of runway. Holding him is what creates the squeeze.")))
            else:
                pods.append(
                    '<div class="pod" style="border-style:dashed">'
                    '<div class="podtop"><span class="slotno">slot %d</span>'
                    '<span class="chip good">open</span></div>'
                    '<div class="podname" style="color:var(--dim)">Empty</div>'
                    '<div class="podmeta">room for a rookie from this year\'s rookie draft</div>'
                    '</div>' % (i + 1))
        st.markdown('<div class="bay">%s</div>' % "".join(pods), unsafe_allow_html=True)
        if mine.squeeze:
            st.markdown(
                '<div class="banner" style="border-color:var(--bad);margin-top:12px">'
                '<b>%d with nowhere to go.</b> Two slots, %d rookie picks incoming, and %d of your '
                'pods still has runway. One of this year\'s rookies has to make the active roster or '
                'be passed on.</div>' % (
                    mine.squeeze, mine.incoming_picks, len(mine.pods) - len(mine.expiring)),
                unsafe_allow_html=True)

        theme.bar("Every bay", "%d managers" % len(owner_ids()))
        rows = []
        for oid in owner_ids():
            b = bays.get(oid) or taxi.Bay(owner_id=oid, pods=[])
            b.incoming_picks = config.rookie_rounds()
            rows.append([
                '<div style="font-weight:650">%s</div><div class="tiny">%s</div>' % (
                    esc(who(oid)), esc(team_of(oid))),
                '<span class="mono">%d / %d</span>' % (len(b.pods), b.slots),
                "<br>".join('%s <span class="tiny">%s · yr %d</span>' % (
                    esc(p.name), esc(p.position), p.year) for p in b.pods) or
                '<span class="tiny">empty</span>',
                '<span class="mono">%d</span>' % b.incoming_picks,
                ('<span class="chip bad">%d homeless</span>' % b.squeeze) if b.squeeze
                else '<span class="chip good">room</span>',
            ])
        ledger_table(["Owner", "Slots", "Stashed", "Incoming picks", "Squeeze"], rows,
                     me_row=owner_ids().index(VIEW) if VIEW in owner_ids() else None)

        # Sleeper's taxi_allow_vets only blocks veterans - it will let someone stash
        # a rookie they took in the VETERAN draft, which our rules do not allow.
        # Nothing prevents it at the source, so we police it here.
    if leaf in (None, "compliance"):
        theme.bar("Taxi compliance", "Sleeper cannot enforce this rule for us")
        try:
            flagged = taxi.compliance(bays, history.build(LG))
        except Exception:
            flagged = {}
        if flagged:
            st.markdown("".join(
                '<div class="banner" style="border-color:var(--bad);margin-bottom:8px">'
                '<b>%s</b> is stashing %s, who was not taken in the rookie draft. '
                'Taxi is rookie-draft picks only — he has to come off.</div>' % (
                    esc(who(o)), ", ".join(esc(p.name) for p in pods))
                for o, pods in flagged.items()), unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="banner"><b>Every taxi squad is legal.</b> Sleeper polices taxi by a '
                'player\'s NFL experience, not by which of our drafts he came from — '
                '<code>taxi_allow_vets</code> only blocks veterans. So it will happily let someone '
                'stash a rookie they took in the veteran draft, and this check is the only thing '
                'standing between the rule and the honour system. It runs against the rookie-draft '
                'log every time this page loads.</div>', unsafe_allow_html=True)

    if leaf in (None, "counts"):
        theme.bar("Who counts as a rookie keeper", "any NFL rookie you drafted · not waivers")
        st.markdown(
            '<div class="card"><div class="note">A %d-round rookie draft is %d picks. A '
            'fantasy-relevant NFL class is closer to thirty. So every year a dozen-plus real rookies '
            'reach the veteran draft or the waiver wire, and the rule has to say what happens to '
            'them.</div>'
            '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));'
            'gap:12px;margin-top:14px">%s</div>'
            '<div class="banner" style="margin-top:14px;border-style:solid;border-color:var(--acc)">'
            '<b>The rule: any NFL rookie you drafted, in either draft. Not waivers.</b> '
            'It does not dilute rookie picks the way it looks like it might — you only get two rookie '
            'keeper slots either way, so the binding constraint is the slots, not the entry route. '
            'What a rookie pick really buys is first crack at the class.</div></div>' % (
                config.rookie_rounds(), config.rookie_rounds() * 8,
                "".join(
                    '<div style="border:1px solid var(--line);border-radius:9px;padding:13px;'
                    'background:var(--card2)"><div class="eyebrow">%s</div>'
                    '<div style="font-family:var(--f-display);font-size:18px;text-transform:uppercase;'
                    'letter-spacing:.03em">%s</div>%s<div class="tiny" style="margin-top:8px">%s</div>'
                    '</div>' % (a, b, c, d)
                    for a, b, c, d in [
                        ("Scenario 1", "The rookie pick", '<span class="chip good">eligible</span>',
                         "Taken at 1.03 in the rookie draft. Last pick to keep, no clock, his whole career."),
                        ("Scenario 2", "The 17th man", '<span class="chip good">eligible</span>',
                         "Rookie draft ends, he is still on the board, you take him in round 12 of the "
                         "veteran draft. He counts — this is the case the rule turns on."),
                        ("Scenario 3", "The waiver find", '<span class="chip bad">not eligible</span>',
                         "Undrafted in both drafts, explodes in week 4, you win him on FAAB. Normal "
                         "keeper on the three-year clock. The cheapest permanent asset in the league "
                         "should not be won at auction."),
                        ("Scenario 4", "The trade", '<span class="chip warn">status is lost</span>',
                         "Trading a rookie keeper kills the status forever. For his new owner he is a "
                         "regular keeper at his original draft round, clock back at year one."),
                    ])), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# THE POT
# ---------------------------------------------------------------------------

def render_pot(leaf=None):
    fr = config.faab_rules()
    # Page-level: settlement is what both the burn-down and the ledger read.
    spends = {}
    try:
        spends = pot.spend_from_rosters(LG)
    except Exception:
        spends = {}
    spends = {o: spends.get(o, 0) for o in owner_ids()}
    settlement = pot.settle(spends)
    complete = (lg.get("status") or "") == "complete"

    if leaf in (None, "burn"):
        theme.bar("The pot", "unspent FAAB comes due")
        played = sum(b.spent for b in settlement.bills) > 0

        if FIRST:
            st.markdown(
                '<div class="banner"><b>No pot in year one.</b> It needs a full season of FAAB data '
                'to settle against, so nothing is billed until the %d offseason. The burn-down still '
                'tracks live all season — the gap between your line and the $%d ceiling in week 17 '
                '<em>is</em> the bill, and it is worth watching from week one.</div>' % (
                    SEASON + 1, int(fr["budget"])), unsafe_allow_html=True)

        if complete:
            glance([
                {"pct": 1.0, "color": "var(--bad)", "big": "$%d" % settlement.total,
                 "label": "Comes due", "note": "every unspent dollar, all 8 teams"},
                {"pct": settlement.to_chase / max(1, settlement.cap), "color": "var(--acc)",
                 "big": "$%d" % settlement.to_chase,
                 "label": "To the Chase winner", "note": "capped at $%d" % settlement.cap},
                {"pct": 1.0 if settlement.to_champion else 0.0, "color": "var(--acc2)",
                 "big": "$%d" % settlement.to_champion,
                 "label": "To the champion", "note": "everything above the cap"},
                {"pct": 1.0, "color": "var(--acc2)", "big": "$%d" % int(fr["budget"]),
                 "label": "Budget", "note": "spend it or owe it"},
            ])
        else:
            spent_total = sum(b.spent for b in settlement.bills)
            pool = int(fr["budget"]) * len(settlement.bills)
            glance([
                {"pct": spent_total / max(1, pool), "color": "var(--acc)",
                 "big": "$%d" % spent_total,
                 "label": "Burned so far", "note": "across all 8 teams"},
                {"pct": (pool - spent_total) / max(1, pool), "color": "var(--acc2)",
                 "big": "$%d" % (pool - spent_total),
                 "label": "Still to spend", "note": "every dollar of it is owed if it sits there"},
                {"pct": 1.0, "color": "var(--acc2)", "big": "$%d" % int(fr["budget"]),
                 "label": "Budget", "note": "spend it or owe it"},
                {"pct": 1.0, "color": "var(--dim)", "big": "$%d" % settlement.cap,
                 "label": "Pot cap", "note": "Chase winner first, champion takes the rest"},
            ])
            st.markdown(
                '<div class="tiny" style="margin-top:8px">Nothing has been spent yet, so the "owed" '
                'column below is just the full budget. It only means something once waivers open in '
                'week 2.</div>', unsafe_allow_html=True)

        theme.bar("Burn-down", "week 1 \u2192 %d \u00b7 cumulative of $%d" % (
            WEEKS, int(fr["budget"])))
        try:
            weekly = pot.weekly_spend(LG, list(range(1, WEEKS + 1)))
            curves = pot.burndown(weekly)
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

    if leaf in (None, "settle"):
        theme.bar("Settlement", "who owes what")
        rows = []
        for b in settlement.bills:
            col = "var(--bad)" if b.owed > 50 else ("var(--warn)" if b.owed > 20 else "var(--good)")
            rows.append([
                '<div style="font-weight:650">%s</div><div class="tiny">%s</div>' % (
                    esc(who(b.owner_id)), esc(team_of(b.owner_id))),
                '<span class="mono">$%d</span>' % b.spent,
                '<div class="bar-track"><i style="width:%d%%;background:%s"></i></div>' % (
                    min(100, b.spent), col),
                '<span class="mono" style="color:%s;font-weight:700">$%d</span>' % (col, b.owed),
            ])
        ledger_table(["Owner", "Spent", "Burn", "Owed"], rows)
        st.markdown(
            '<div class="banner" style="margin-top:12px"><b>The cap is a ceiling, not a discount.</b> '
            'Every unspent dollar comes due. The first $%d goes to whoever wins the Chase bracket and '
            'anything above it goes to the champion, which is what keeps the consolation prize from '
            'ever rivalling the title.</div>' % settlement.cap, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# DRAFT
# ---------------------------------------------------------------------------

def render_draft(leaf=None):
    # Page-level: the capital strip needs the same order the board draws in.
    draw = first_draw()
    order = draw.get("veteran") or owner_ids()
    if leaf in (None, "board"):
        theme.bar("Veteran draft", "%d rounds · snake · keeper costs burned in" % config.veteran_rounds())
        if FIRST:
            st.markdown(
                '<div class="banner">Year one: no keepers, so every pick is live. Order is drawn flat '
                'at random on the Lottery tab. <b>%d rounds, not %d</b> — %d vet picks plus %d rookies '
                'is %d players against %d active spots and %d taxi slots, which leaves you the choice '
                'of promoting a rookie or stashing both.</div>' % (
                    config.veteran_rounds(), int(config.drafts()["veteran_rounds"]),
                    config.veteran_rounds(), config.rookie_rounds(),
                    config.veteran_rounds() + config.rookie_rounds(),
                    config.active_roster_size(), int(config.taxi_rules()["slots"])),
                unsafe_allow_html=True)

        if draw.get("veteran"):
            st.markdown('<div class="tiny" style="margin-bottom:8px">Board is showing the selection '
                        'order drawn on the Lottery tab. Once managers actually pick their slots, '
                        'those choices override it.</div>', unsafe_allow_html=True)
        grid = draftboard.grid(order, season=SEASON, keepers={}, league_id=LG)
        head = "<th></th>" + "".join(
            '<th title="%s">%s</th>' % (esc(team_of(o)), esc(who(o).split()[0])) for o in order)
        body = ""
        for row in grid:
            body += '<tr><td class="rd">R%d</td>' % row[0].round
            for cell in row:
                if cell.kind == "traded":
                    inner = '<div class="cell traded"><span class="t">traded</span></div>'
                elif cell.kind in ("keeper", "rookie", "franchise"):
                    inner = '<div class="cell %s"><span class="p">%s</span>' \
                            '<span class="t">%s</span></div>' % (cell.kind, esc(cell.player),
                                                                 esc(cell.note or cell.kind))
                else:
                    inner = '<div class="cell open">%s</div>' % cell.pick_label
                body += "<td>%s</td>" % inner
            body += "</tr>"
        st.markdown('<div class="boardwrap"><table class="board"><thead><tr>%s</tr></thead>'
                    '<tbody>%s</tbody></table></div>' % (head, body), unsafe_allow_html=True)
        st.markdown(
            '<div class="legend">'
            '<span><b style="background:var(--acc-soft);border:1px solid var(--acc)"></b> Keeper</span>'
            '<span><b style="background:var(--acc2-soft);border:1px solid var(--acc2)"></b> Rookie keeper</span>'
            '<span><b style="background:color-mix(in srgb,var(--acc2) 30%,transparent);'
            'border:1px solid var(--acc2)"></b> Franchise</span>'
            '<span><b style="background:color-mix(in srgb,var(--warn) 20%,transparent);'
            'border:1px dashed var(--warn)"></b> Traded</span>'
            '<span><b style="background:var(--card2);border:1px solid var(--line2)"></b> Open</span>'
            '</div>', unsafe_allow_html=True)

        # ------------------------------------------------- what a pick locks you into
    if leaf in (None, "locks"):
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

    if leaf in (None, "capital"):
        theme.bar("Draft capital", "which rounds each team actually holds")
        owned_by = draftboard.owned_rounds(LG, SEASON)
        keep_by = submitted_keepers()
        rounds_n = config.veteran_rounds(SEASON)
        cap_rows = []
        for c in draftboard.capital(order, keep_by, SEASON, LG):
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

def render_lottery(leaf=None):
    lr = config.lottery_rules()
    st.markdown(
        '<div class="banner"><b>Two drums, weighted differently on purpose.</b> The rookie drum '
        'runs on regular-season record; the veteran drum runs on final standing, so a Chase win '
        'costs you veteran balls and weeks 15–17 still decide something. Each drum sets a '
        '<b>selection order</b>, not a draft slot — first choice takes any spot on the board they '
        'want. And nobody wins first choice in both.</div>', unsafe_allow_html=True)

    use_alt = st.toggle("Use the steeper spread (%s)" % ", ".join(
        str(x) for x in config.lottery_weights(alt=True)), value=False, key="alt_weights")
    weights = config.lottery_weights(alt=use_alt)

    if FIRST:
        theme.bar("Season one", "no standings, so both orders are drawn flat")
        c1, c2 = st.columns([1, 2])
        with c1:
            existing = first_draw()
            seed = st.number_input("Draw seed", 0, 10 ** 6,
                                   int(existing.get("seed", 0)), key="seed_first")
            if st.button("Draw both orders"):
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
        draw = first_draw()
        with c2:
            if draw:
                cols = st.columns(2)
                for col, key, label in ((cols[0], "rookie", "Rookie draft"),
                                        (cols[1], "veteran", "Veteran draft")):
                    with col:
                        st.markdown('<div class="eyebrow">%s — selection order</div>' % label,
                                    unsafe_allow_html=True)
                        st.markdown("".join(
                            '<div style="display:flex;justify-content:space-between;padding:3px 0">'
                            '<span class="mono" style="color:var(--dim)">%d</span>'
                            '<span style="font-weight:%d;color:%s">%s</span></div>' % (
                                i + 1, 700 if o == VIEW else 500,
                                "var(--acc)" if o == VIEW else "var(--ink)", esc(who(o)))
                            for i, o in enumerate(draw[key])), unsafe_allow_html=True)
            else:
                st.markdown('<div class="banner">Nothing drawn yet. Pick a seed and hit the '
                            'button — the seed is there so a draw can be reproduced in front of '
                            'everyone rather than taken on trust.</div>', unsafe_allow_html=True)

    # Page-level: the simulator reads the same two drums the diagram draws.
    demo = [
        {"owner_id": o, "wins": w, "final_rank": f, "champion": c}
        for o, w, f, c in zip(owner_ids(),
                              [11, 10, 9, 8, 7, 6, 4, 3],
                              [2, 3, 4, 1, 5, 7, 8, 6],
                              [False, False, False, True, False, False, False, False])
    ]
    # Illustrate the per-drum lock-out: the team that won first choice of last
    # year's ROOKIE drum is barred here, and is untouched in the veteran drum.
    demo_locked_rookie = owner_ids()[0]
    rookie_seats = lottery.build_drum(demo, "record", weights=weights,
                                      locked_out=[demo_locked_rookie])
    vet_seats = lottery.build_drum(demo, "final", weights=weights)

    if leaf in (None, "drums"):
        theme.bar("How the drums will work", "from %d on" % (SEASON + 1))

        def drum_html(seats, basis):
            out = []
            for s in seats:
                t = next(d for d in demo if d["owner_id"] == s.owner_id)
                tag = ("champion, floor" if s.champion else
                       ("locked out of 1st" if s.locked_out else
                        ("finished %s" % ordinal(t["final_rank"]) if basis == "final" else "by record")))
                out.append(
                    '<div class="lotrow"><div class="lotname">%s<small>%d-%d · %s</small></div>'
                    '<div class="lotbars"><i style="width:%d%%;background:%s">%s</i>'
                    '<i style="width:%d%%;background:var(--card2)"></i></div></div>' % (
                        esc(who(s.owner_id)), t["wins"], 14 - t["wins"], tag,
                        s.weight * 3,
                        "var(--dim)" if s.locked_out else (
                            "var(--acc2)" if s.champion else "var(--acc)"),
                        "%d%%" % s.weight if s.weight > 4 else "",
                        100 - s.weight * 3))
            return '<div class="lot">%s</div>' % "".join(out)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="card"><div class="eyebrow">Rookie drum</div>'
                        '<h3 class="k">Weighted by regular-season record</h3>%s'
                        '<div class="tiny" style="margin-top:10px">%s won first choice of this drum '
                        'last year, so he is barred from it again — shown greyed. He can still win '
                        '<b>second</b> choice here, and the veteran drum beside this one does not '
                        'care at all.</div></div>'
                        % (drum_html(rookie_seats, "record"), esc(who(demo_locked_rookie))),
                        unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="card"><div class="eyebrow">Veteran drum</div>'
                        '<h3 class="k">Weighted by final standing</h3>%s'
                        '<div class="tiny" style="margin-top:10px">Same eight teams, different '
                        'order: the team with the worst record won a Chase game here, so it drops '
                        'behind the two that did not.</div></div>' % drum_html(vet_seats, "final"),
                        unsafe_allow_html=True)

        st.markdown('<div class="tiny" style="margin-top:6px">Illustrated with a simulated season so '
                    'the weighting is visible before there is a real one.</div>',
                    unsafe_allow_html=True)

    if leaf in (None, "sim"):
        theme.bar("Simulate", "%s" % " / ".join(str(w) for w in weights))
        n = st.select_slider("Runs", [2000, 5000, 20000], value=5000, key="sim_n")
        res = lottery.simulate(rookie_seats, vet_seats, n=int(n), seed=17)

        def odds_html(seats, table):
            out = []
            for s in seats:
                row = table[s.owner_id]
                p1, p2 = row[0], row[1]
                rest = 100 - p1 - p2
                out.append(
                    '<div class="lotrow"><div class="lotname">%s<small>1st %.1f%% · median %d</small>'
                    '</div><div class="lotbars">%s%s'
                    '<i style="width:%.1f%%;background:var(--card2);color:var(--dim)">%s</i>'
                    '</div></div>' % (
                        esc(who(s.owner_id)), p1, lottery.median_slot(row),
                        '<i style="width:%.1f%%;background:var(--acc)">%s</i>' % (
                            p1, "%.0f%%" % p1 if p1 > 13 else "") if p1 > 0.05 else "",
                        '<i style="width:%.1f%%;background:var(--acc2)">%s</i>' % (
                            p2, "%.0f%%" % p2 if p2 > 13 else "") if p2 > 0.05 else "",
                        rest, "3rd+" if rest > 30 else ""))
            return '<div class="lot">%s</div>' % "".join(out)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="card"><div class="eyebrow">Rookie draft</div>'
                        '<h3 class="k">Selection odds</h3>%s</div>' % odds_html(
                            rookie_seats, res["rookie"]), unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="card"><div class="eyebrow">Veteran draft</div>'
                        '<h3 class="k">Selection odds</h3>%s</div>' % odds_html(
                            vet_seats, res["veteran"]), unsafe_allow_html=True)
        st.markdown('<div class="tiny" style="margin-top:8px">%d runs · <b>%d sweeps</b> — the '
                    'no-sweep guardrail is doing its job.</div>' % (res["n"], res["sweeps"]),
                    unsafe_allow_html=True)

    if leaf in (None, "guards"):
        theme.bar("The guardrails", "in the order they apply")
        cols = st.columns(3)
        for col, (title, body) in zip(cols, [
            ("No sweep", "The rookie drum draws first. Whoever wins first choice there is pulled out "
                         "of contention for first choice in the veteran drum <em>that same year</em> "
                         "— they can still land second. Without it, one team takes both boards in "
                         "about 4% of years."),
            ("No back-to-back, per drum", "Win <b>first choice</b> of a drum and you cannot win first "
                                          "choice of <b>that drum</b> next year. The two are tracked "
                                          "separately: take first of the rookie draft this year and "
                                          "you are still free to take first of the veteran draft next "
                                          "year, and second choice of the rookie drum stays open to "
                                          "you. Landing a pick by trade does not burn your "
                                          "eligibility — only winning it does."),
            ("Champion at the floor", "Whoever wins the title takes the smallest ball weight in both "
                                      "drums no matter what their record was."),
        ]):
            with col:
                st.markdown('<div class="card"><div class="eyebrow">Guardrail</div>'
                            '<h3 class="k">%s</h3><div class="note">%s</div></div>' % (title, body),
                            unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# the bottom bar
# ---------------------------------------------------------------------------

def _popover(section: str, label: str) -> str:
    """A group -> leaf drill-down sheet for one section.

    Two taps to any leaf, and the sheet closes on arrival - which is the point
    of it over jumping to a page root and scrolling past three other sections.
    """
    groups = GROUPS[section]
    root = "".join(
        '<div class="bb-item" data-show="%s-%s"><span>%s</span>'
        '<span class="chev">%d &rsaquo;</span></div>' % (section, gk, glabel, len(leaves))
        for gk, glabel, leaves in groups)
    panels = "".join(
        '<div class="bb-panel%s" data-panel="%s-%s">'
        '<div class="bb-head"><span class="bb-back" data-show="%s-root">&larr; %s</span>'
        '<span class="bb-title">%s</span></div>%s</div>' % (
            " on" if gk == GROUP else "", section, gk, section, label, glabel,
            "".join(
                '<a class="bb-item leaf%s" href="?p=%s&g=%s&t=%s" target="_self">%s</a>' % (
                    " on" if (PAGE == section and GROUP == gk and LEAF == lk) else "",
                    section, gk, lk, llabel)
                for lk, llabel in leaves))
        for gk, glabel, leaves in groups)
    return ('<div class="bb-pop" id="bb-pop-%s">'
            '<div class="bb-panel%s" data-panel="%s-root">'
            '<div class="bb-head"><span class="bb-title">%s</span></div>%s</div>%s</div>' % (
                section, "" if PAGE == section else " on", section, label, root, panels))


def render_bottom_bar() -> None:
    links = []
    for key, label in SECTIONS:
        cls = " active" if PAGE == key else ""
        if key in GROUPS:
            links.append('<div class="bb-link%s" data-toggle="bb-pop-%s">%s</div>' % (
                cls, key, label))
        else:
            links.append('<a class="bb-link%s" href="?p=%s" target="_self">%s</a>' % (
                cls, key, label))
    bar = ('<div class="bb-scrim" id="bb-scrim"></div>'
           + "".join(_popover(k, l) for k, l in SECTIONS if k in GROUPS)
           + '<div class="bb-wrap"><div class="bb">%s</div></div>' % "".join(links))

    # st.markdown strips <script>, so the popover's handlers cannot live there.
    # components.html runs real JS in a same-origin iframe; reaching through to
    # window.parent.document puts the bar in the app's OWN document, which is
    # where theme.inject's stylesheet lives and where position:fixed anchors to
    # the real viewport. window.top would be a level too far out - that one is
    # only for Cloud's own badge, which lives in its wrapper page.
    components.html(
        "<script>(function(){"
        "const doc = window.parent.document;"
        "const topDoc = window.top.document;"
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
        "const scrim = doc.getElementById('bb-scrim');"
        "function closeAll(){doc.querySelectorAll('.bb-pop').forEach(p=>p.classList.remove('on'));"
        "scrim.classList.remove('on');}"
        "doc.querySelectorAll('[data-toggle]').forEach(function(b){"
        "  b.addEventListener('click',function(e){e.stopPropagation();"
        "    const pop=doc.getElementById(b.dataset.toggle);"
        "    const was=pop.classList.contains('on'); closeAll();"
        "    if(!was){pop.classList.add('on');scrim.classList.add('on');}});});"
        "doc.querySelectorAll('[data-show]').forEach(function(el){"
        "  el.addEventListener('click',function(){const pop=el.closest('.bb-pop');"
        "    pop.querySelectorAll('.bb-panel').forEach(p=>p.classList.remove('on'));"
        "    pop.querySelector('[data-panel=\"'+el.dataset.show+'\"]').classList.add('on');});});"
        "scrim.addEventListener('click', closeAll);"
        "})();</script>", height=0)


PAGES = {"home": render_home, "rules": render_rules}
GROUP_PAGES = {"keepers": render_keepers, "draft": render_draft, "young": render_taxi,
               "lottery": render_lottery, "wire": render_keepers, "pot": render_pot}

if PAGE in PAGES:
    PAGES[PAGE]()
else:
    GROUP_PAGES[GROUP](LEAF)

render_bottom_bar()
