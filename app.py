"""7 1/2 Men - keeper dashboard.

Six sections: Home, Keepers, Taxi Bay, The Pot, Draft, Lottery.

The league starts in 2026 with empty rosters and no keepers, so most screens
have two modes: a "season one" state that shows the rule and what it will do,
and the live state once there is data behind it. The engine underneath is the
full ruleset either way - nothing here is stubbed for year one.
"""
from __future__ import annotations

import html
import math
from collections import Counter
from typing import Dict, List, Optional

import streamlit as st

from halfmen import (adp_board, config, draftboard, engine, history, lottery,
                     pot, rulebook, sleeper, storage, taxi, theme)

st.set_page_config(page_title="7½ Men", page_icon="🏈", layout="wide")

LG = config.league_id()
SEASON = config.season()
ME = config.me()
FIRST = config.is_first_season()


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
theme.masthead("%d \u00b7 %s" % (SEASON, "season one" if FIRST else "offseason"))

TABS = ["Home", "Rules", "Keepers", "Taxi Bay", "The Pot", "Draft", "Lottery"]
tab_home, tab_rules, tab_keep, tab_taxi, tab_pot, tab_draft, tab_lot = st.tabs(TABS)


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
    st.markdown('<div style="overflow-x:auto"><table class="ledger"><thead><tr>%s</tr></thead>'
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

with tab_home:
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
        {"pct": (filled / max(1, len(rosters))), "color": "var(--bad)",
         "big": str(filled),
         "label": "Rosters", "note": "0 of 8 \u2014 they fill at the draft"},
        {"pct": min(1.0, adp_board.size() / 300.0), "color": "var(--gold)",
         "big": str(adp_board.size()),
         "label": "ADP board", "note": "players on the consensus board, refreshed daily"},
        {"pct": 1.0, "color": "var(--acc2)", "big": str(config.veteran_rounds()),
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
                 me_row=owner_ids().index(ME) if ME in owner_ids() else None)



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


with tab_rules:
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


with tab_keep:
    kr = config.keeper_rules()
    if FIRST:
        st.markdown(
            '<div class="banner"><b>Nothing to keep yet.</b> Your first slip is due after this '
            'season. What matters right now is the draft: where you take a player decides what he '
            'costs you to hold for the next three years, and the gap between that price and what '
            'he turns out to be worth is the only thing that ever makes a keeper worth a '
            'slot.</div>', unsafe_allow_html=True)

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
    theme.bar("Your slip", "%d regular · %d rookie · %d franchise" % (
        int(kr["regular"]), int(kr["rookie"]), int(config.franchise_rules()["slots"])))
    my_roster = next((r for r in (state["rosters"] or [])
                      if str(r.get("owner_id")) == ME), None)
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
        owned = owned_map().get(ME, Counter())
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


# ---------------------------------------------------------------------------
# TAXI BAY
# ---------------------------------------------------------------------------

with tab_taxi:
    tr = config.taxi_rules()
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
                 me_row=owner_ids().index(ME) if ME in owner_ids() else None)

    # Sleeper's taxi_allow_vets only blocks veterans - it will let someone stash
    # a rookie they took in the VETERAN draft, which our rules do not allow.
    # Nothing prevents it at the source, so we police it here.
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

with tab_pot:
    fr = config.faab_rules()
    theme.bar("The pot", "unspent FAAB comes due")
    spends = {}
    try:
        spends = pot.spend_from_rosters(LG)
    except Exception:
        spends = {}
    spends = {o: spends.get(o, 0) for o in owner_ids()}
    settlement = pot.settle(spends)

    complete = (lg.get("status") or "") == "complete"
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
            {"pct": 1.0, "color": "var(--gold)", "big": "$%d" % int(fr["budget"]),
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
            {"pct": 1.0, "color": "var(--gold)", "big": "$%d" % int(fr["budget"]),
             "label": "Budget", "note": "spend it or owe it"},
            {"pct": 1.0, "color": "var(--dim)", "big": "$%d" % settlement.cap,
             "label": "Pot cap", "note": "Chase winner first, champion takes the rest"},
        ])
        st.markdown(
            '<div class="tiny" style="margin-top:8px">Nothing has been spent yet, so the "owed" '
            'column below is just the full budget. It only means something once waivers open in '
            'week 2.</div>', unsafe_allow_html=True)

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

with tab_draft:
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

    draw = st.session_state.get("first_draw") or {}
    order = draw.get("veteran") or owner_ids()
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
        '<span><b style="background:var(--gold-soft);'
        'border:1px solid var(--gold)"></b> Franchise</span>'
        '<span><b style="background:color-mix(in srgb,var(--warn) 20%,transparent);'
        'border:1px dashed var(--warn)"></b> Traded</span>'
        '<span><b style="background:var(--card2);border:1px solid var(--line2)"></b> Open</span>'
        '</div>', unsafe_allow_html=True)

    theme.bar("Draft capital", "what each team actually has left")
    cap_rows = []
    for c in draftboard.capital(order, {}, SEASON, LG):
        cap_rows.append([
            '<div style="font-weight:650">%s</div><div class="tiny">%s</div>' % (
                esc(who(c["owner_id"])), esc(team_of(c["owner_id"]))),
            '<span class="mono">%d</span>' % c["rounds"],
            '<span class="mono" style="color:var(--acc)">-%d</span>' % c["eaten"],
            '<span class="mono" style="font-weight:700">%d</span>' % c["live"],
            '<span class="mono">%d</span>' % c["rookie_picks"],
        ])
    ledger_table(["Owner", "Vet picks", "Eaten by keepers", "Live", "Rookie picks"], cap_rows)


# ---------------------------------------------------------------------------
# LOTTERY
# ---------------------------------------------------------------------------

with tab_lot:
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
            seed = st.number_input("Draw seed", 0, 10 ** 6, 0, key="seed_first")
            if st.button("Draw both orders"):
                st.session_state["first_draw"] = {
                    "rookie": lottery.first_season_order(owner_ids(), seed=int(seed)),
                    "veteran": lottery.first_season_order(owner_ids(), seed=int(seed) + 1),
                }
        draw = st.session_state.get("first_draw")
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
                                i + 1, 700 if o == ME else 500,
                                "var(--acc)" if o == ME else "var(--ink)", esc(who(o)))
                            for i, o in enumerate(draw[key])), unsafe_allow_html=True)
            else:
                st.markdown('<div class="banner">Nothing drawn yet. Pick a seed and hit the '
                            'button — the seed is there so a draw can be reproduced in front of '
                            'everyone rather than taken on trust.</div>', unsafe_allow_html=True)

    theme.bar("How the drums will work", "from %d on" % (SEASON + 1))
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
