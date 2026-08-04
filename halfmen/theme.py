"""Two palettes, one chassis.

  lights_off   near-black ground, acid lime, magenta
  newsprint    warm paper, deep violet, gold

Unlike the mockup - which ran under an artifact CSP that blocks font CDNs and so
fell back to Impact - this is an ordinary web page and can load a real typeface.
Archivo is a grotesque with a variable width axis: the wide cut does the display
work the condensed 90s faces were standing in for, and the normal cut sets the
body, so the page is one family in two widths rather than two families arguing.
IBM Plex Mono carries anything with digits in it.

Every colour pair that ends up as text is declared in TEXT_PAIRS and asserted
against WCAG AA in tests/test_theme.py, so "is this readable in both palettes"
is a test rather than a judgement call.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import streamlit as st

PALETTES: Dict[str, dict] = {
    "lights_off": {
        "label": "Lights Off",
        "vars": """
  --bg:#0a0a0d; --bg2:#101015;
  --card:#131319; --card2:#1b1b22; --line:#26262f; --line2:#33333e;
  --ink:#f5f6f8; --ink2:#aab2be; --dim:#8b95a3;
  --acc:#c9f24b; --acc-ink:#0c0c0f; --acc-soft:rgba(201,242,75,.13);
  --acc2:#e59cff; --acc2-soft:rgba(229,156,255,.14);
  --gold:#ffce1f; --gold-ink:#1a1405;
  --good:#5ceba0; --warn:#f5c542; --bad:#ff7089;
  --shadow:0 10px 30px -18px rgba(0,0,0,.9);
  --grain:.045;
""",
    },
    "newsprint": {
        "label": "Newsprint",
        "vars": """
  --bg:#f4f1e9; --bg2:#ece7f4;
  --card:#ffffff; --card2:#f5f3fa; --line:#e4dff0; --line2:#d2cbe6;
  --ink:#1c1430; --ink2:#544a75; --dim:#635a85;
  --acc:#4b2d9f; --acc-ink:#ffffff; --acc-soft:rgba(75,45,159,.09);
  --acc2:#a8145a; --acc2-soft:rgba(168,20,90,.10);
  --gold:#8a5d00; --gold-ink:#ffffff;
  --good:#0b6f46; --warn:#7a5200; --bad:#a01048;
  --shadow:0 8px 26px -18px rgba(45,25,90,.4);
  --grain:.03;
""",
    },
}

# Foreground / background pairs that actually carry text somewhere in the app.
# tests/test_theme.py walks these for every palette.
TEXT_PAIRS: List[Tuple[str, str]] = [
    ("--ink", "--bg"), ("--ink", "--card"), ("--ink", "--card2"),
    ("--ink2", "--bg"), ("--ink2", "--card"), ("--ink2", "--card2"),
    ("--dim", "--card"), ("--dim", "--card2"), ("--dim", "--bg"),
    ("--acc-ink", "--acc"), ("--gold-ink", "--gold"),
    ("--acc", "--card"), ("--acc2", "--card"),
    ("--good", "--card"), ("--warn", "--card"), ("--bad", "--card"),
    ("--good", "--card2"), ("--warn", "--card2"), ("--bad", "--card2"),
]

FONT_URL = ("https://fonts.googleapis.com/css2?"
            "family=Archivo:wdth,wght@75..125,400..800"
            "&family=IBM+Plex+Mono:wght@400;500;600&display=swap")

_FONTS = """
  --f-display:'Archivo',system-ui,-apple-system,'Segoe UI',sans-serif;
  --f-body:'Archivo',system-ui,-apple-system,'Segoe UI',sans-serif;
  --f-data:'IBM Plex Mono',ui-monospace,'SF Mono',Menlo,monospace;
  --r:12px; --r-sm:8px;
"""

SLEEPER_IMG = "https://sleepercdn.com/content/nfl/players/thumb/{pid}.jpg"
SLEEPER_DEFAULT = "https://sleepercdn.com/images/v2/icons/player_default.webp"


# --------------------------------------------------------------------------
# contrast, so the palettes can be tested rather than eyeballed
# --------------------------------------------------------------------------

def palette_vars(name: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for line in PALETTES[name]["vars"].splitlines():
        for decl in line.split(";"):
            if ":" not in decl:
                continue
            k, v = decl.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def _rgb(hexstr: str):
    h = hexstr.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _luminance(hexstr: str) -> float:
    def chan(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (chan(c) for c in _rgb(hexstr))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg_hex: str, bg_hex: str) -> float:
    a, b = _luminance(fg_hex), _luminance(bg_hex)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


# --------------------------------------------------------------------------
# the stylesheet
# --------------------------------------------------------------------------

_TEMPLATE = """
<style>
@import url('__FONTURL__');

:root{__FONTS____VARS__}

.stApp{ background:var(--bg); color:var(--ink); }
.stApp::before{
  content:""; position:fixed; inset:0; pointer-events:none; z-index:0; opacity:var(--grain);
  background-image:
    radial-gradient(55% 38% at 10% 0%, var(--acc) 0%, transparent 58%),
    radial-gradient(46% 34% at 100% 92%, var(--acc2) 0%, transparent 58%);
}
[data-testid="stAppViewContainer"] .main .block-container{
  padding-top:1.4rem; padding-bottom:4rem; max-width:1160px;
}
html, body, [class*="css"], .stMarkdown, p, li, span, label{
  font-family:var(--f-body); color:var(--ink);
  -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility;
}
.mono, .num{ font-family:var(--f-data); font-variant-numeric:tabular-nums; letter-spacing:-.01em; }

/* ---- masthead ------------------------------------------------------- */
.mast{ display:flex; align-items:baseline; gap:13px; line-height:1; margin:0 0 2px; }
.mast .name{
  font-family:var(--f-display); font-weight:800; font-stretch:118%;
  font-size:31px; letter-spacing:-.025em; color:var(--ink);
}
.mast .name .half{ color:var(--acc); }
.mast .yr{
  font-family:var(--f-data); font-size:10.5px; letter-spacing:.14em; color:var(--dim);
  text-transform:uppercase; font-weight:500; align-self:center;
}

/* ---- section heading ------------------------------------------------ */
/* A rule and a heading, not a saturated slab. The slab put near-black type on
   full-strength accent - the loudest thing on the page and the worst contrast
   on it at the same time. */
.bar{
  display:flex; align-items:baseline; gap:12px; flex-wrap:wrap;
  font-family:var(--f-display); font-weight:800; font-stretch:112%;
  font-size:21px; letter-spacing:-.02em; color:var(--ink);
  background:none; border-bottom:1px solid var(--line2);
  padding:0 0 9px; margin:30px 0 15px;
}
.bar .n{
  margin-left:auto; font-family:var(--f-data); font-size:10.5px; font-weight:500;
  letter-spacing:.1em; text-transform:uppercase; color:var(--dim);
}
.eyebrow{
  font-family:var(--f-data); font-size:10px; letter-spacing:.15em; font-weight:500;
  text-transform:uppercase; color:var(--dim); margin:0 0 7px;
}
h3.k{
  font-family:var(--f-display); font-weight:700; font-size:15.5px;
  letter-spacing:-.01em; margin:0 0 10px; color:var(--ink);
}

/* ---- cards ---------------------------------------------------------- */
.card{ background:var(--card); border:1px solid var(--line); border-radius:var(--r);
       padding:17px 18px; box-shadow:var(--shadow); }
.tiny{ font-size:12px; color:var(--dim); line-height:1.55; }
.note{ color:var(--ink2); font-size:13.5px; line-height:1.6; }
.banner{ border:1px solid var(--line2); border-radius:var(--r-sm); padding:12px 15px;
         background:var(--card2); font-size:13px; color:var(--ink2); line-height:1.6;
         margin:0 0 10px; }
.banner b{ color:var(--ink); font-weight:650; }

.chip{ display:inline-flex; align-items:center; gap:5px; padding:2.5px 9px; border-radius:6px;
       font-family:var(--f-data); font-size:10px; letter-spacing:.06em; text-transform:uppercase;
       font-weight:500; border:1px solid var(--line2); color:var(--ink2); white-space:nowrap; }
.chip.good{ color:var(--good); border-color:transparent; background:var(--card2); }
.chip.warn{ color:var(--warn); border-color:transparent; background:var(--card2); }
.chip.bad{ color:var(--bad); border-color:transparent; background:var(--card2); }
.chip.acc{ color:var(--acc); border-color:transparent; background:var(--acc-soft); }
.chip.solid{ background:var(--gold); color:var(--gold-ink); border-color:var(--gold); font-weight:600; }

/* ---- glance rings --------------------------------------------------- */
.glance{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }
.gl{ background:var(--card); border:1px solid var(--line); border-radius:var(--r);
     padding:15px; display:flex; gap:14px; align-items:center; box-shadow:var(--shadow); }
.gl .k{ font-family:var(--f-data); font-size:10px; letter-spacing:.13em; font-weight:500;
        text-transform:uppercase; color:var(--dim); }
.gl .s{ font-size:12.5px; color:var(--ink2); margin-top:4px; line-height:1.4; }

/* ---- contract cards ------------------------------------------------- */
.contract{ background:var(--card); border:1px solid var(--line); border-radius:var(--r);
           padding:14px 15px; display:flex; gap:12px; align-items:flex-start;
           position:relative; overflow:hidden; margin-bottom:10px; }
.contract .who{ flex:1; min-width:0; }
.contract .nm{ font-weight:650; font-size:15px; letter-spacing:-.015em; }
.contract .meta{ font-family:var(--f-data); font-size:11px; color:var(--dim);
                 letter-spacing:.02em; margin-top:3px; }
.contract .tags2{ display:flex; gap:5px; flex-wrap:wrap; margin-top:8px; }
.contract .price{ text-align:right; flex:none; }
.contract .price .rd{ font-family:var(--f-display); font-weight:800; font-stretch:112%;
                      font-size:24px; line-height:1; letter-spacing:-.03em; }
.contract .price .sub{ font-family:var(--f-data); font-size:10px; color:var(--dim);
                       letter-spacing:.1em; text-transform:uppercase; margin-top:4px; }
.contract.wall .price .rd{ color:var(--bad); }
.contract.fr .price .rd{ color:var(--gold); }
.surplus{ font-family:var(--f-data); font-size:12px; font-weight:600; }
.surplus.p{ color:var(--good); } .surplus.n{ color:var(--bad); } .surplus.z{ color:var(--dim); }

/* year pips - the three-year wall, made visible */
.pips{ display:flex; gap:3px; align-items:center; }
.pips i{ width:16px; height:4px; border-radius:2px; background:var(--line2); display:block; }
.pips i.on{ background:var(--acc); } .pips i.now{ background:var(--gold); }
.pips i.fr{ background:var(--gold); opacity:.5; }
.pips .wallmark{ width:2px; height:11px; background:var(--bad); border-radius:1px; margin:0 3px; }

/* ---- tables --------------------------------------------------------- */
table.ledger{ width:100%; border-collapse:collapse; font-size:13.5px; color:var(--ink);
              margin-top:4px; }
table.ledger th{ font-family:var(--f-data); font-size:10px; letter-spacing:.12em; font-weight:500;
                 text-transform:uppercase; color:var(--dim); text-align:left;
                 padding:6px 10px 9px; white-space:nowrap; }
table.ledger td{ padding:9px 10px; border-top:1px solid var(--line); vertical-align:middle; }
table.ledger tr.me td{ background:var(--acc-soft); }
.bar-track{ height:7px; border-radius:99px; background:var(--line); overflow:hidden; min-width:70px; }
.bar-track i{ display:block; height:100%; border-radius:99px; }

/* ---- rulebook ------------------------------------------------------- */
.rule{ background:var(--card); border:1px solid var(--line); border-radius:var(--r);
       padding:20px 24px; box-shadow:var(--shadow); margin-bottom:14px; }
.rule .stand{ color:var(--ink2); font-size:14.5px; line-height:1.6; margin:-2px 0 16px; max-width:66ch; }
.rule p{ font-size:14.5px; line-height:1.7; color:var(--ink); margin:0 0 13px; max-width:72ch; }
.rule ul{ margin:0 0 13px; padding-left:19px; }
.rule li{ font-size:14.5px; line-height:1.65; color:var(--ink); margin-bottom:8px; max-width:70ch; }
.rule table{ width:100%; border-collapse:collapse; margin:0 0 15px; font-size:14px; color:var(--ink); }
.rule table th{ font-family:var(--f-data); font-size:10px; letter-spacing:.12em; font-weight:500;
                text-transform:uppercase; color:var(--dim); text-align:left; padding:0 12px 9px; }
.rule table td{ padding:10px 12px; border-top:1px solid var(--line); vertical-align:top; }
.rule table td:first-child{ font-weight:650; white-space:nowrap; width:1%; }
.worked{ border:1px solid var(--line2); border-radius:var(--r-sm); overflow:hidden; margin:0 0 15px; }
.worked .wh{ background:var(--card2); padding:9px 15px; font-family:var(--f-data); font-size:10px;
             letter-spacing:.13em; text-transform:uppercase; color:var(--dim); font-weight:500; }
.worked .wr{ display:grid; grid-template-columns:170px 100px 1fr; gap:14px; padding:11px 15px;
             border-top:1px solid var(--line); align-items:baseline; }
.worked .wr .l{ font-size:13.5px; color:var(--ink2); }
.worked .wr .v{ font-family:var(--f-display); font-weight:800; font-stretch:112%; font-size:18px;
                letter-spacing:-.02em; color:var(--acc); }
.worked .wr .d{ font-size:13px; color:var(--ink2); line-height:1.55; }
.toc{ display:flex; flex-wrap:wrap; gap:6px; margin-bottom:18px; }
.toc a{ font-family:var(--f-data); font-size:10.5px; letter-spacing:.08em; text-transform:uppercase;
        padding:6px 11px; border-radius:6px; background:var(--card); border:1px solid var(--line);
        color:var(--ink2); text-decoration:none; font-weight:500; }
.toc a:hover{ color:var(--ink); border-color:var(--acc); }

/* ---- draft board ---------------------------------------------------- */
.boardwrap{ overflow-x:auto; border:1px solid var(--line); border-radius:var(--r); background:var(--card); }
table.board{ min-width:900px; width:100%; font-size:11.5px; border-collapse:collapse; color:var(--ink); }
table.board th{ background:var(--card2); font-family:var(--f-display); font-weight:700;
                font-size:12px; padding:11px 6px;
                border-bottom:1px solid var(--line2); text-align:center; color:var(--ink2); }
table.board td{ padding:3px; border-bottom:1px solid var(--line);
                border-right:1px solid var(--line); text-align:center; }
table.board td.rd{ background:var(--card2); font-family:var(--f-data); font-size:10.5px;
                   color:var(--dim); }
.cell{ border-radius:6px; padding:6px 4px; min-height:34px; display:flex;
       flex-direction:column; justify-content:center; gap:2px; }
.cell .p{ font-weight:650; font-size:11.5px; line-height:1.2; }
.cell .t{ font-family:var(--f-data); font-size:9px; letter-spacing:.04em; color:var(--dim); }
.cell.keeper{ background:var(--acc-soft); }
.cell.rookie{ background:var(--acc2-soft); }
.cell.franchise{ background:var(--card2); box-shadow:inset 0 0 0 1px var(--gold); }
.cell.traded{ background:var(--card2); color:var(--warn); }
.cell.open{ color:var(--dim); font-family:var(--f-data); font-size:10px; }
.legend{ display:flex; gap:16px; flex-wrap:wrap; margin-top:11px; }
.legend span{ display:flex; align-items:center; gap:7px; font-size:12.5px; color:var(--ink2); }
.legend b{ width:11px; height:11px; border-radius:3px; display:block; }

/* ---- lottery -------------------------------------------------------- */
.lot{ display:flex; flex-direction:column; gap:8px; }
.lotrow{ display:grid; grid-template-columns:150px 1fr; gap:12px; align-items:center; }
.lotname{ font-size:13px; font-weight:600; text-align:right; line-height:1.25; letter-spacing:-.01em; }
.lotname small{ display:block; font-family:var(--f-data); font-size:10px;
                color:var(--dim); font-weight:400; margin-top:2px; }
.lotbars{ display:flex; height:24px; border-radius:6px; overflow:hidden; background:var(--card2); }
.lotbars i{ display:flex; align-items:center; justify-content:center; font-family:var(--f-data);
            font-size:10px; font-weight:600; color:var(--acc-ink); min-width:0; overflow:hidden; }

/* ---- streamlit chrome ----------------------------------------------- */
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"],
#MainMenu, footer{ display:none !important; }
[data-testid="stHeader"]{ height:0; min-height:0; background:transparent; }

.stTabs [data-baseweb="tab-list"]{ gap:6px; border-bottom:none; background:transparent;
  padding:0; margin-bottom:4px; flex-wrap:wrap; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"]{ display:none; }
.stTabs [data-baseweb="tab"]{
  background:var(--card); border:1px solid var(--line); border-radius:8px;
  padding:7px 14px; color:var(--ink2); height:auto; min-height:0;
  transition:background .16s, color .16s, border-color .16s;
}
.stTabs [data-baseweb="tab"] p{
  font-family:var(--f-body); font-weight:600; font-size:12.5px; letter-spacing:.03em;
  text-transform:uppercase; color:inherit; margin:0;
}
.stTabs [data-baseweb="tab"]:hover{ color:var(--ink); border-color:var(--line2); }
.stTabs [aria-selected="true"]{ background:var(--acc) !important; border-color:var(--acc) !important; }
.stTabs [aria-selected="true"] p{ color:var(--acc-ink) !important; }

[data-testid="stRadio"] > div{ justify-content:flex-end; }
[data-testid="stRadio"] [role="radiogroup"]{
  flex-direction:row; gap:3px; background:var(--card); border:1px solid var(--line);
  border-radius:9px; padding:3px; display:inline-flex; align-items:center; }
[data-testid="stRadio"] [role="radiogroup"] label{
  margin:0 !important; padding:5px 13px; border-radius:7px; cursor:pointer;
  transition:background .16s, color .16s; display:flex; align-items:center; }
[data-testid="stRadio"] [role="radiogroup"] label > div:first-child{ display:none !important; }
[data-testid="stRadio"] [role="radiogroup"] label p{
  font-size:12px; font-weight:600; color:var(--ink2); margin:0; white-space:nowrap; }
[data-testid="stRadio"] [role="radiogroup"] label:hover p{ color:var(--ink); }
[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked){ background:var(--acc); }
[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) p{ color:var(--acc-ink); }

.stButton>button{ background:var(--acc); color:var(--acc-ink); border:none; border-radius:8px;
  font-family:var(--f-body); font-weight:650; font-size:13px; padding:.5rem 1.1rem;
  transition:filter .16s; }
.stButton>button:hover{ filter:brightness(1.06); color:var(--acc-ink); }
.stButton>button:focus{ color:var(--acc-ink); box-shadow:none; }
.stButton>button p, .stButton>button div{ color:var(--acc-ink) !important; font-weight:650; }

[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="base-input"]{
  background:var(--card) !important; border-color:var(--line2) !important; border-radius:8px; }
[data-baseweb="input"] input, [data-baseweb="select"] *{ color:var(--ink) !important; }
[data-testid="stWidgetLabel"] p{ font-family:var(--f-data); font-size:10px; letter-spacing:.13em;
  text-transform:uppercase; color:var(--dim); font-weight:500; }
/* ...but a checkbox/toggle label is a sentence, not a field name. */
[data-testid="stCheckbox"] [data-testid="stWidgetLabel"] p,
[data-testid="stToggle"] [data-testid="stWidgetLabel"] p{
  font-family:var(--f-body); font-size:13px; letter-spacing:0; text-transform:none;
  color:var(--ink2); font-weight:400; }
[data-baseweb="tag"]{ background:var(--acc-soft) !important; border:none !important; }
[data-baseweb="tag"] span{ color:var(--acc) !important; }
[data-testid="stNumberInputStepUp"], [data-testid="stNumberInputStepDown"]{
  background:var(--card2); color:var(--ink2); }
[data-baseweb="popover"] li{ background:var(--card) !important; color:var(--ink) !important; }
[data-baseweb="popover"] li:hover{ background:var(--card2) !important; }
[data-testid="stSlider"] [role="slider"]{ background:var(--acc) !important; }
[data-testid="stCheckbox"] p, [data-testid="stToggle"] p{ color:var(--ink2); font-size:13px; }

[data-testid="stVerticalBlock"]{ gap:.6rem; }
[data-testid="stHorizontalBlock"]{ gap:.9rem; }

@media (max-width:820px){
  .glance{ grid-template-columns:repeat(2,minmax(0,1fr)); }
  .lotrow{ grid-template-columns:118px 1fr; }
  .worked .wr{ grid-template-columns:1fr; gap:4px; }
  .mast .name{ font-size:25px; }
}
@media (prefers-reduced-motion:reduce){ *{ transition:none !important; } }
</style>
"""


def css(palette: str = "lights_off") -> str:
    """Built by substitution rather than %-formatting. The stylesheet is full of
    literal percent signs and every one of them was an escaping bug waiting."""
    pal = PALETTES.get(palette, PALETTES["lights_off"])
    return (_TEMPLATE
            .replace("__FONTURL__", FONT_URL)
            .replace("__FONTS__", _FONTS)
            .replace("__VARS__", pal["vars"]))


def inject(palette: str = None) -> str:
    from . import config
    palette = palette or st.session_state.get("palette") or config.palette()
    st.markdown(css(palette), unsafe_allow_html=True)
    return palette


def masthead(subtitle: str) -> None:
    st.markdown(
        '<div class="mast"><span class="name">7<span class="half">&frac12;</span> Men</span>'
        '<span class="yr">%s</span></div>' % subtitle, unsafe_allow_html=True)


def bar(title: str, note: str = "") -> None:
    st.markdown('<div class="bar">%s<span class="n">%s</span></div>' % (title, note),
                unsafe_allow_html=True)


def ring(pct: float, color: str, big: str, small: str = "") -> str:
    import math
    r = 30.0
    circ = 2 * math.pi * r
    off = circ * (1 - max(0.0, min(1.0, pct)))
    return (
        '<svg width="72" height="72" viewBox="0 0 74 74" aria-hidden="true">'
        '<circle cx="37" cy="37" r="30" fill="none" stroke="var(--line)" stroke-width="6"/>'
        '<circle cx="37" cy="37" r="30" fill="none" stroke="%s" stroke-width="6" '
        'stroke-linecap="round" stroke-dasharray="%.1f" stroke-dashoffset="%.1f" '
        'transform="rotate(-90 37 37)"/>'
        '<text x="37" y="%d" text-anchor="middle" font-family="var(--f-display)" '
        'font-weight="800" font-size="20" fill="var(--ink)">%s</text>%s</svg>'
    ) % (color, circ, off, 35 if small else 43, big,
         ('<text x="37" y="49" text-anchor="middle" font-family="var(--f-data)" '
          'font-size="8.5" letter-spacing="0.6" fill="var(--dim)">%s</text>' % small) if small else "")


def pips(year: int, franchise: bool = False, rookie: bool = False) -> str:
    if rookie:
        return ('<span class="pips">' + '<i class="on"></i>' * 5 +
                '<span class="tiny" style="margin-left:7px">no clock</span></span>')
    out = ['<span class="pips">']
    for i in range(1, 4):
        cls = "on" if i < year else ("now" if i == year else "")
        out.append('<i class="%s"></i>' % cls)
    out.append('<span class="wallmark"></span>')
    for _ in range(2):
        out.append('<i class="%s"></i>' % ("fr" if franchise else ""))
    out.append('</span>')
    return "".join(out)


def surplus_class(n) -> str:
    if n is None:
        return "z"
    return "p" if n > 0 else ("n" if n < 0 else "z")


def signed(n) -> str:
    if n is None:
        return "-"
    return ("+%d" % n) if n > 0 else str(n)
