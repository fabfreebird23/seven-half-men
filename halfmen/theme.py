"""Floodlight / Acid - one dark theme.

Big Shoulders Display is a condensed industrial cut doing the display work:
mastheads, section heads, nav, and every large number. It is the face Impact was
standing in for in the mockup, which only fell back to Impact because the
artifact CSP blocks font CDNs. Archivo sets the body, IBM Plex Mono carries
anything with digits in it.

Acid lime does all the accent work on a near-black ground; electric blue is the
second voice and marks the things that are special rather than merely good -
franchise tags, champions, the year you are currently in.

There is deliberately no light theme. One ground, tuned properly, beats two
half-tuned ones; a light palette can be added later as a second entry in
PALETTES without touching a component.

Every colour pair that ends up as text is declared in TEXT_PAIRS and asserted
against WCAG AA in tests/test_theme.py, so "is this readable" is a test rather
than a judgement call.
"""
from __future__ import annotations

import itertools
from typing import Dict, List, Tuple

import streamlit as st

PALETTES: Dict[str, dict] = {
    "bloodysunday": {
        "label": "Bloody Sunday",
        # Carried over from the draft-dashboard brand so the two apps read as
        # one family. The whole palette turns on giving crimson exactly two
        # jobs - the brand, and genuine urgency - and moving every other signal
        # off red. A red brand that also means "warning" means nothing.
        #
        # These are the DARK values. The brand's own set is mixed for an
        # off-white ground and cannot be reused here: at their light-ground
        # values plum reads 1.9:1 on a dark card and nothing in the set clears
        # 4.5. Each hue is the brand's, lifted until it clears 4.6:1 on --bg.
        "vars": """
  --bg:#141314; --bg2:#1a1819;
  --card:#1d1b1c; --card2:#262324; --line:#332f31; --line2:#463f42;
  --ink:#f4f1f2; --ink2:#b4aaae; --dim:#938a8e;
  /* Crimson stays the fill; the ink on it is near-black, which clears 4.95
     where white manages only 4.01. The masthead keeps a white wordmark because
     that is display type at 26px+, where 3:1 is the bar. */
  --acc:#fb0849; --acc-ink:#1a0208; --acc-soft:rgba(251,8,73,.14);
  --acc2:#578ed5; --acc2-ink:#02101f; --acc2-soft:rgba(87,142,213,.16);
  /* Positions are CATEGORICAL and take the brand's own badge set - plum, teal,
     blue, amber - lifted for this ground. QB is plum rather than red precisely
     so crimson can keep meaning "act now" and nothing else. */
  /* Lifted against --card2, not --bg: text sits on the lightest surface in the
     stack, and clearing the ground is not the same as clearing the card. */
  --qb:#cb6ab8; --rb:#369d86; --wr:#578ed5; --te:#d77010;
  --warn-soft:rgba(215,112,16,.10);
  --good:#369d86; --warn:#d77010; --bad:#fc4475;
  --shadow:0 10px 30px -18px rgba(0,0,0,.95);
  --grain:.04;
""",
    },
}

DEFAULT = "bloodysunday"

# Foreground / background pairs that actually carry text somewhere in the app.
# tests/test_theme.py walks these for every palette.
TEXT_PAIRS: List[Tuple[str, str]] = [
    ("--ink", "--bg"), ("--ink", "--card"), ("--ink", "--card2"),
    ("--ink2", "--bg"), ("--ink2", "--card"), ("--ink2", "--card2"),
    ("--dim", "--card"), ("--dim", "--card2"), ("--dim", "--bg"),
    ("--acc-ink", "--acc"), ("--acc2-ink", "--acc2"),
    ("--acc", "--card"), ("--acc2", "--card"),
    ("--good", "--card"), ("--warn", "--card"), ("--bad", "--card"),
    ("--good", "--card2"), ("--warn", "--card2"), ("--bad", "--card2"),
]

FONT_URL = ("https://fonts.googleapis.com/css2?"
            "family=Pacifico"
            "&family=Big+Shoulders+Display:wght@400..800"
            "&family=Archivo:wdth,wght@75..125,400..800"
            "&family=IBM+Plex+Mono:wght@400;500;600&display=swap")

_FONTS = """
  --f-display:'Big Shoulders Display','Archivo Narrow',system-ui,sans-serif;
  --f-body:'Archivo',system-ui,-apple-system,'Segoe UI',sans-serif;
  --f-data:'IBM Plex Mono',ui-monospace,'SF Mono',Menlo,monospace;
  --f-script:'Pacifico','Snell Roundhand','Brush Script MT',cursive;
  --r:9px; --r-sm:7px;
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
/* A crimson band, the way the brand does it - the mark sits ON the colour
   rather than beside it. White wordmark here is display type at 26px and up,
   where 3:1 is the bar; every small label on the band is at 4.5 or better. */
/* Streamlit's block container carries a large top padding, so a band that only
   bleeds sideways leaves a dead strip above it. Pull it up the full padding and
   put that space back inside the band. */
.mast{ display:flex; align-items:baseline; gap:9px; line-height:1;
       background:var(--acc); color:#fff;
       margin:-96px -1.2rem 18px; padding:22px 1.2rem 16px;
       border-radius:0 0 14px 14px; flex-wrap:wrap; }
@media (max-width:640px){ .mast{ margin-top:-72px; padding-top:16px; } }
.mast .the{ font-family:var(--f-script); font-size:24px; color:rgba(255,255,255,.94);
            transform:translateY(3px); line-height:1; }
.mast .name{
  font-family:var(--f-display); font-weight:800; font-size:42px;
  letter-spacing:.005em; text-transform:uppercase; line-height:.9; color:#fff;
}
.mast .name .half{ color:#fff; opacity:.85; }
.mast .yr{
  font-family:var(--f-data); font-size:10.5px; letter-spacing:.14em;
  color:rgba(255,255,255,.85); text-transform:uppercase; font-weight:500;
  align-self:center; margin-left:auto;
}

/* ---- section heading ------------------------------------------------ */
/* A rule and a heading, not a saturated slab. The slab put near-black type on
   full-strength accent - the loudest thing on the page and the worst contrast
   on it at the same time. */
.bar{
  display:flex; align-items:center; gap:14px;
  font-family:var(--f-display); font-weight:800; font-size:29px;
  letter-spacing:.02em; text-transform:uppercase; color:var(--ink);
  background:none; padding:0; margin:28px 0 14px;
}
.bar::after{ content:""; flex:1; height:1px; background:var(--line2); order:2; }
.bar .n{
  order:3; font-family:var(--f-data); font-size:10px; font-weight:500;
  letter-spacing:.14em; text-transform:uppercase; color:var(--dim); white-space:nowrap;
}
.eyebrow{
  font-family:var(--f-data); font-size:10px; letter-spacing:.15em; font-weight:500;
  text-transform:uppercase; color:var(--dim); margin:0 0 7px;
}
h3.k{
  font-family:var(--f-display); font-weight:700; font-size:21px;
  letter-spacing:.02em; text-transform:uppercase; margin:0 0 9px; color:var(--ink);
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
.chip.mag{ color:var(--acc2); border-color:color-mix(in srgb,var(--acc2) 45%,transparent);
           background:var(--acc2-soft); }
.chip.solid{ background:var(--acc2); color:var(--acc2-ink); border-color:var(--acc2); font-weight:600; }

/* ---- the draft board ------------------------------------------------- */
.dboard{ overflow-x:auto; margin-top:10px; }
table.dboard{ border-collapse:separate; border-spacing:0; width:100%; min-width:940px;
              table-layout:fixed; }
/* One explicit column width and fixed layout: percentage widths across eight
   columns plus a row header left the last one visibly short of the rest. */
table.dboard col.rh{ width:44px; }
table.dboard th{ font-family:var(--f-display); font-size:15px; text-transform:uppercase;
                 color:var(--ink2); font-weight:700; padding:6px 5px; text-align:center;
                 border-bottom:1px solid var(--line2); white-space:nowrap; }
table.dboard th.rh{ font-family:var(--f-data); font-size:9.5px; color:var(--dim); }
table.dboard td{ border:1px solid var(--line); padding:0; height:46px;
                 background:var(--card); vertical-align:top; }
table.dboard td.rh{ background:transparent; border:none; font-family:var(--f-data);
                    font-size:10px; color:var(--dim); text-align:center;
                    vertical-align:middle; }
.dcell{ height:100%; padding:5px 7px; display:flex; flex-direction:column;
        justify-content:center; gap:1px; }
.dcell .l{ font-family:var(--f-data); font-size:8.5px; color:var(--dim); }
.dcell .n{ font-weight:650; font-size:12px; line-height:1.15; }
.dcell .p{ font-family:var(--f-data); font-size:9px; color:var(--dim); }
td.dnow{ background:var(--acc-soft); border-color:var(--acc); }
td.dnow .l{ color:var(--acc); }
td.dmine{ box-shadow:inset 3px 0 0 var(--acc2); }
td.dhas{ border-left-width:3px; }
td.dhas.p-QB{ border-left-color:var(--qb); }
td.dhas.p-RB{ border-left-color:var(--rb); }
td.dhas.p-WR{ border-left-color:var(--wr); }
td.dhas.p-TE{ border-left-color:var(--te); }
.pos-QB{ color:var(--qb); } .pos-RB{ color:var(--rb); }
.pos-WR{ color:var(--wr); } .pos-TE{ color:var(--te); }
.poskey{ display:flex; gap:13px; flex-wrap:wrap; margin:8px 0 2px; }
.poskey span{ font-family:var(--f-data); font-size:9.5px; letter-spacing:.13em;
              color:var(--dim); display:inline-flex; align-items:center; gap:5px; }
.poskey i{ width:8px; height:8px; border-radius:2px; display:block; }
.heardline{ border:1px solid var(--line2); border-radius:10px; background:var(--card);
            padding:10px 14px; margin:8px 0; font-size:14px; }
.heardline.bad{ border-color:var(--bad); color:var(--bad); }
.heardline .k{ font-family:var(--f-data); font-size:9.5px; letter-spacing:.14em;
               text-transform:uppercase; color:var(--dim); margin-right:10px; }

/* ---- on the clock ---------------------------------------------------- */
/* A day-long pick timer means this is the only thing most people open the page
   for. It gets to be the loudest object on it. */
.clockcard{ display:grid; grid-template-columns:1fr auto; gap:16px; align-items:center;
            border:1px solid var(--acc); border-radius:12px; padding:15px 18px;
            background:linear-gradient(100deg,var(--acc-soft),transparent 65%); }
.clockcard.late{ border-color:var(--bad);
                 background:linear-gradient(100deg,rgba(255,107,125,.12),transparent 65%); }
.clockcard .k{ font-family:var(--f-data); font-size:9.5px; letter-spacing:.15em;
               text-transform:uppercase; color:var(--dim); }
.clockcard .w{ font-family:var(--f-display); font-size:34px; line-height:1; margin-top:5px;
               text-transform:uppercase; color:var(--acc); }
.clockcard.late .w{ color:var(--bad); }
.clockcard .v{ font-family:var(--f-display); font-size:34px; line-height:1; margin-top:5px;
               font-variant-numeric:tabular-nums; }
.clockcard .tm{ font-size:12px; color:var(--dim); margin-top:5px; }
.clockcard .r{ text-align:right; }

@media(max-width:640px){
  .clockcard{ grid-template-columns:1fr; gap:11px; }
  .clockcard .r{ text-align:left; }
  .clockcard .w,.clockcard .v{ font-size:28px; }
}

/* ---- minutes --------------------------------------------------------- */
/* Set in the data face rather than the body face: these are typed notes, not
   prose, and they should not look like the rulebook they sit under. Hanging
   dashes and real indentation, because an outline that loses its levels stops
   being funny. */
.mins{ border:1px solid var(--line2); border-radius:12px; background:var(--card);
       overflow:hidden; margin:2px 0 8px; }
.mins .head{ padding:14px 18px; border-bottom:1px solid var(--line);
             background:linear-gradient(90deg,var(--card2),transparent 70%);
             display:flex; align-items:baseline; justify-content:space-between;
             gap:14px; flex-wrap:wrap; }
.mins .head .t{ font-family:var(--f-display); font-size:21px; text-transform:uppercase;
                line-height:1; }
.mins .head .t small{ display:block; font-family:var(--f-data); font-size:9.5px;
                      letter-spacing:.16em; color:var(--dim); margin-bottom:5px; }
.mins .head .by{ font-family:var(--f-data); font-size:10px; letter-spacing:.12em;
                 text-transform:uppercase; color:var(--acc); white-space:nowrap; }
.mins .note{ padding:12px 18px 0; font-size:12.5px; color:var(--dim); }
.mins ul{ list-style:none; margin:0; padding:14px 18px 18px; font-family:var(--f-data);
          font-size:13px; line-height:1.65; }
.mins ul ul{ padding:2px 0 2px 20px; font-size:12.5px; }
.mins ul ul ul{ font-size:12px; }
.mins li{ position:relative; padding-left:17px; margin:3px 0; color:var(--ink);
          font-family:var(--f-data); font-size:inherit; line-height:1.65; }
.mins li::before{ content:"–"; position:absolute; left:0; color:var(--line2); }
.mins ul ul > li{ color:var(--ink2); }
.mins ul ul > li::before{ content:"○"; font-size:9px; top:.25em; }
.mins ul ul ul > li{ color:var(--dim); }
.mins ul ul ul > li::before{ content:"▪"; font-size:9px; top:.15em; }

@media(max-width:640px){
  .mins ul{ font-size:12.5px; padding:12px 14px 15px; }
  .mins ul ul{ padding-left:15px; }
}

/* ---- the agenda ------------------------------------------------------ */
/* Year one is nothing but rule questions, and the answers were living in a
   group chat where they scroll away. Front page, with the real options beside
   each one so a vote does not open by re-explaining the choice. */
.agenda{ border:1px solid var(--line2); border-radius:12px; overflow:hidden;
         background:var(--card); margin:2px 0 8px; }
.agenda .it{ padding:15px 18px 16px; border-top:1px solid var(--line); }
.agenda .it:first-child{ border-top:none; }
.agenda .it .h{ display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; }
.agenda .it .n{ font-family:var(--f-data); font-size:10px; letter-spacing:.14em;
                color:var(--dim); }
.agenda .it .t{ font-family:var(--f-display); font-size:21px; text-transform:uppercase;
                line-height:1; }
.agenda .it .why{ font-size:12.5px; color:var(--ink2); line-height:1.55; margin:7px 0 0;
                  max-width:74ch; }
.agenda .opts{ display:grid; gap:7px; margin-top:11px; }
/* An option row is label, reasoning, and where the room has landed. The tally
   is a bar rather than a bare count so a split reads at a glance from across a
   table, which is the only place anyone will be looking at this tonight. */
.agenda .o{ display:grid; grid-template-columns:minmax(0,auto) 1fr 84px; gap:11px;
            align-items:center; background:var(--card2); border:1px solid var(--line);
            border-radius:8px; padding:9px 12px; }
.agenda .o.lead{ border-color:color-mix(in srgb,var(--acc) 40%,transparent); }
.agenda .o .lab{ font-weight:650; font-size:13px; }
.agenda .o .d{ font-size:11.5px; color:var(--dim); line-height:1.45; }
.agenda .o .you{ font-family:var(--f-data); font-size:9px; letter-spacing:.12em;
                 text-transform:uppercase; color:var(--acc); margin-left:6px; }
.agenda .tally{ display:flex; align-items:center; gap:8px; justify-content:flex-end; }
.agenda .tally .bar{ flex:1; height:6px; border-radius:99px; background:var(--card);
                     border:1px solid var(--line); overflow:hidden; }
.agenda .tally .bar i{ display:block; height:100%; background:var(--acc); }
.agenda .tally .c{ font-family:var(--f-data); font-size:12px; color:var(--ink);
                   font-variant-numeric:tabular-nums; min-width:1ch; text-align:right; }
.agenda .waiting{ font-family:var(--f-data); font-size:10px; letter-spacing:.12em;
                  text-transform:uppercase; color:var(--dim); margin-top:9px; }
.agenda .it .foot{ font-size:11.5px; color:var(--warn); margin-top:9px; }
.agenda .done{ display:grid; grid-template-columns:auto 1fr; gap:11px; align-items:baseline;
               padding:11px 18px; border-top:1px solid var(--line); }
.agenda .done .t{ font-weight:650; font-size:13px; }
.agenda .done .d{ font-size:11.5px; color:var(--dim); line-height:1.45; }
.agenda .done .tick{ color:var(--good); font-family:var(--f-data); font-size:11px; }

@media(max-width:640px){
  .agenda .o{ grid-template-columns:1fr auto; gap:3px 10px; }
  .agenda .o .d{ grid-column:1/-1; }
  .agenda .tally{ grid-row:1; grid-column:2; width:72px; }
  .agenda .done{ grid-template-columns:1fr; gap:3px; }
}

/* ---- your-team card -------------------------------------------------- */
/* One object, not a strip of tiles plus a loose table underneath. A header, a
   band carrying the two numbers that mean the most, three meters, then the
   contracts in the footer. Deliberately NOT another row of liquid bowls - Home
   already carries four of those for the league, and eight identical circles
   stacked on a phone stop reading as information. */
.tcard{ border:1px solid var(--line2); border-radius:12px; overflow:hidden;
        background:var(--card); margin:2px 0 8px; }
.tcard .head{ display:flex; align-items:center; justify-content:space-between; gap:14px;
              padding:13px 18px; border-bottom:1px solid var(--line);
              background:linear-gradient(90deg,var(--acc-soft),transparent 68%); }
.tcard .head.quiet{ background:linear-gradient(90deg,var(--card2),transparent 68%); }
.tcard .head .nm{ font-family:var(--f-display); font-size:22px; text-transform:uppercase;
                  line-height:1; }
.tcard .head .nm small{ display:block; font-family:var(--f-data); font-size:9.5px;
                        letter-spacing:.16em; color:var(--dim); text-transform:uppercase;
                        margin-bottom:5px; }
.tcard .head .st{ font-family:var(--f-data); font-size:10.5px; letter-spacing:.1em;
                  color:var(--acc); text-transform:uppercase; white-space:nowrap; }
.tcard .head .st.off{ color:var(--dim); }

/* the band: two numbers, because one number leaves dead air beside it and a
   single dash in an empty band reads as broken rather than as "not yet". */
.tcard .band{ padding:17px 18px 0; border-bottom:1px solid var(--line);
              background:linear-gradient(120deg,var(--card2),transparent 58%); }
/* stretch, not end-align: the two notes wrap to different depths, and bottom
   alignment made the two labels and the two numbers sit at different heights.
   Labels and numbers pin to the top, the notes fall to the bottom. */
.tcard .band .row{ display:grid; grid-template-columns:1fr 1px 1fr; gap:22px;
                   align-items:stretch; }
.tcard .band .half{ display:flex; flex-direction:column; }
.tcard .band .half .n{ margin-top:auto; padding-top:7px; }
.tcard .band .div{ background:var(--line); align-self:stretch; margin:2px 0 8px; }
.tcard .band .k{ font-family:var(--f-data); font-size:9.5px; letter-spacing:.15em;
                 text-transform:uppercase; color:var(--dim); }
.tcard .band .v{ font-family:var(--f-display); font-size:60px; line-height:.86; color:var(--acc);
                 font-variant-numeric:tabular-nums; letter-spacing:.004em; }
.tcard .band .half.mut .v{ color:var(--ink); opacity:.62; }
.tcard .band .v.off{ color:var(--ink); opacity:.22; }
.tcard .band .n{ font-size:12.5px; color:var(--ink2); line-height:1.45; }
.tcard .band .n b{ color:var(--ink); }
/* the season rule closes the band edge to edge, so the progress is the frame
   rather than another bar competing with the meters below */
/* line-height and font-size are zeroed because Streamlit's own markdown styles
   give a bare div a text line box, which turned a 3px rule into a 34px gap. */
.tcard .band .season{ margin:15px -18px 0; height:3px; min-height:0; background:var(--card);
                    border-top:1px solid var(--line); position:relative;
                    line-height:0; font-size:0; }
.tcard .band .season i{ position:absolute; left:0; top:-1px; bottom:0; background:var(--acc);
                      opacity:.85; }
.tcard .band .cap{ display:flex; justify-content:space-between; gap:14px;
                   font-family:var(--f-data); font-size:9px; letter-spacing:.13em;
                   text-transform:uppercase; color:var(--dim); padding:6px 0 9px; }

/* the meters: every one of these is a fraction of something, so draw the
   fraction instead of asking for it to be done in the head */
.tcard .meters{ display:grid; grid-template-columns:repeat(3,1fr); }
.tcard .meters .m{ padding:14px 18px 15px; border-left:1px solid var(--line); }
.tcard .meters .m:first-child{ border-left:none; }
.tcard .meters .m .t{ display:flex; align-items:baseline; justify-content:space-between; gap:10px; }
.tcard .meters .m .k{ font-family:var(--f-data); font-size:9.5px; letter-spacing:.14em;
                      text-transform:uppercase; color:var(--dim); }
.tcard .meters .m .val{ font-family:var(--f-display); font-size:29px; line-height:1;
                        font-variant-numeric:tabular-nums; white-space:nowrap; }
.tcard .meters .m .val.off{ color:var(--dim); opacity:.42; }
.tcard .meters .m .val small{ font-family:var(--f-body); font-size:10.5px; color:var(--dim);
                              margin-left:4px; }
.tcard .meters .m .n{ font-size:11.5px; color:var(--dim); line-height:1.4; margin-top:1px; }
.tcard .meters .m .track{ height:8px; border-radius:99px; background:var(--card2);
                          overflow:hidden; border:1px solid var(--line); margin-top:10px; }
.tcard .meters .m .fill{ height:100%; border-radius:99px; }
.tcard .meters .m .pips{ display:flex; gap:5px; margin-top:10px; }
.tcard .meters .m .pip{ width:100%; height:8px; border-radius:3px; background:var(--card2);
                        border:1px solid var(--line); }

.tcard .foot{ border-top:1px solid var(--line); padding:11px 18px; display:flex; gap:11px;
              align-items:center; flex-wrap:wrap; background:var(--bg2); font-size:12.5px;
              color:var(--ink2); }
.tcard .foot b{ color:var(--ink); }
.tcard .foot.warn{ background:var(--warn-soft); color:var(--warn); }
.tcard .foot.warn b{ color:var(--warn); }

/* ---- glance rings --------------------------------------------------- */
.glance{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:18px; margin:2px 0 6px; }
.gl{ display:flex; flex-direction:column; align-items:center; gap:11px; }
.gl svg.liq{ width:100%; max-width:168px; height:auto; display:block; }
.gl .s{ font-size:13px; color:var(--ink2); line-height:1.4; text-align:center; max-width:22ch; }

/* The surface: two travelling waves at different speeds and directions, plus a
   slow bob. Three periods that do not divide into each other, so the loop is
   long enough that the eye never catches it repeating. */
svg.liq .wv{ will-change:transform; }
svg.liq .bob{ transform:translateY(var(--sy,0px)); }
svg.liq .front{ animation:liq-front 7s linear infinite; }
svg.liq .back{ animation:liq-back 11s linear infinite; }
svg.liq .bob{ animation:liq-bob 5.5s ease-in-out infinite; }
@keyframes liq-front{ from{transform:translateX(0)} to{transform:translateX(-200px)} }
@keyframes liq-back{ from{transform:translateX(0)} to{transform:translateX(200px)} }
@keyframes liq-bob{ 0%,100%{transform:translateY(var(--sy,0px))}
                    50%{transform:translateY(calc(var(--sy,0px) + 2.5px))} }

/* ---- contract cards ------------------------------------------------- */
.contract{ background:var(--card); border:1px solid var(--line); border-radius:var(--r);
           padding:14px 15px 14px 18px; display:flex; gap:12px; align-items:flex-start;
           position:relative; overflow:hidden; margin-bottom:10px; }
/* The rail encodes state - at the wall, franchised, carrying real surplus - so
   it is information rather than decoration, and it is 3px rather than a field. */
.contract::before{ content:""; position:absolute; left:0; top:0; bottom:0; width:3px;
                   background:transparent; }
.contract.pick::before{ background:var(--acc); }
.contract.wall::before{ background:var(--bad); }
.contract.fr::before{ background:var(--acc2); }
.contract .who{ flex:1; min-width:0; }
.contract .nm{ font-weight:650; font-size:15px; letter-spacing:-.015em; }
.contract .meta{ font-family:var(--f-data); font-size:11px; color:var(--dim);
                 letter-spacing:.02em; margin-top:3px; }
.contract .tags2{ display:flex; gap:5px; flex-wrap:wrap; margin-top:8px; }
.contract .price{ text-align:right; flex:none; }
.contract .price .rd{ font-family:var(--f-display); font-weight:800;
                      font-size:34px; line-height:.9; letter-spacing:.01em; }
.contract .price .sub{ font-family:var(--f-data); font-size:10px; color:var(--dim);
                       letter-spacing:.1em; text-transform:uppercase; margin-top:4px; }
.contract.wall .price .rd{ color:var(--bad); }
.contract.fr .price .rd{ color:var(--acc2); }
.surplus{ font-family:var(--f-data); font-size:12px; font-weight:600; }
.surplus.p{ color:var(--good); } .surplus.n{ color:var(--bad); } .surplus.z{ color:var(--dim); }

/* year pips - the three-year wall, made visible */
.pips{ display:flex; gap:3px; align-items:center; }
.pips i{ width:16px; height:4px; border-radius:2px; background:var(--line2); display:block; }
.pips i.on{ background:var(--acc); } .pips i.now{ background:var(--acc2); }
.pips i.fr{ background:var(--acc2); opacity:.5; }
.pips .wallmark{ width:2px; height:11px; background:var(--bad); border-radius:1px; margin:0 3px; }

/* ---- tables --------------------------------------------------------- */
table.ledger{ width:100%; border-collapse:collapse; font-size:13.5px; color:var(--ink);
              margin-top:4px; }
table.ledger th{ font-family:var(--f-data); font-size:10px; letter-spacing:.12em; font-weight:500;
                 text-transform:uppercase; color:var(--dim); text-align:left;
                 padding:6px 10px 9px; white-space:nowrap; }
table.ledger td{ padding:9px 10px; border-top:1px solid var(--line); vertical-align:middle; }
table.ledger tr.me td{ background:var(--acc-soft); }
/* Horizontal scroll with shadows at the edges that fade out when you reach
   them - a wide table on a phone otherwise just looks cut off, and nobody
   swipes something they do not know is scrollable. */
.scroller{
  overflow-x:auto; -webkit-overflow-scrolling:touch;
  background:
    linear-gradient(to right, var(--bg) 40%, transparent) left / 26px 100% no-repeat local,
    linear-gradient(to left, var(--bg) 40%, transparent) right / 26px 100% no-repeat local,
    radial-gradient(farthest-side at 0 50%, rgba(0,0,0,.6), transparent) left / 11px 100% no-repeat scroll,
    radial-gradient(farthest-side at 100% 50%, rgba(0,0,0,.6), transparent) right / 11px 100% no-repeat scroll;
}
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
.worked .wr .v{ font-family:var(--f-display); font-weight:800; font-size:24px;
                letter-spacing:.01em; color:var(--acc); line-height:1; }
.worked .wr .d{ font-size:13px; color:var(--ink2); line-height:1.55; }
.toc{ display:flex; flex-wrap:wrap; gap:6px; margin-bottom:18px; }
.toc a{ font-family:var(--f-data); font-size:10.5px; letter-spacing:.08em; text-transform:uppercase;
        padding:6px 12px; border-radius:99px; background:var(--card); border:1px solid var(--line);
        color:var(--ink2); text-decoration:none; font-weight:500; }
.toc a:hover{ color:var(--ink); border-color:var(--acc); }

/* ---- draft board ---------------------------------------------------- */
.boardwrap{ overflow-x:auto; border:1px solid var(--line); border-radius:var(--r); background:var(--card); }
table.board{ min-width:900px; width:100%; font-size:11.5px; border-collapse:collapse; color:var(--ink); }
table.board th{ background:var(--card2); font-family:var(--f-display); font-weight:700;
                font-size:15px; letter-spacing:.03em; text-transform:uppercase; padding:10px 6px;
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
.cell.franchise{ background:var(--card2); box-shadow:inset 0 0 0 1px var(--acc2); }
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

/* ---- draft capital strip ------------------------------------------- */
/* One block per round. Which rounds a team is missing matters more than how
   many, and a column of counts cannot show it. */
.capstrip{ display:flex; gap:3px; align-items:center; }
.capstrip i{ flex:1; height:16px; border-radius:3px; display:block; min-width:6px; }
.capstrip i.live{ background:var(--line2); }
.capstrip i.eaten{ background:var(--acc); }
.capstrip i.traded{ background:transparent; box-shadow:inset 0 0 0 1px var(--warn); }
.capstrip i.extra{ background:var(--acc2); }

/* ---- taxi pods ------------------------------------------------------ */
.bay{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
.pod{ background:var(--card); border:1px solid var(--line); border-radius:var(--r);
      padding:15px 16px; }
.pod.expiring{ border-color:var(--bad); }
.podtop{ display:flex; justify-content:space-between; align-items:baseline; gap:10px;
         margin-bottom:9px; }
.pod .slotno{ font-family:var(--f-data); font-size:9.5px; letter-spacing:.14em;
              text-transform:uppercase; color:var(--dim); }
.podname{ font-family:var(--f-display); font-weight:800; font-size:22px; letter-spacing:.02em;
          text-transform:uppercase; line-height:1; }
.podmeta{ font-family:var(--f-data); font-size:10.5px; color:var(--dim); margin-top:5px; }
.podclock{ display:flex; gap:4px; margin-top:12px; }
.podclock i{ flex:1; height:5px; border-radius:3px; background:var(--line2); display:block; }
.podclock i.on{ background:var(--acc); }
.pod.expiring .podclock i.on:last-of-type{ background:var(--bad); }
.podtags{ display:flex; gap:5px; flex-wrap:wrap; margin-top:12px; }

.chart{ width:100%; height:auto; display:block; }

/* ---- the live draw --------------------------------------------------- */
.draw{ display:flex; flex-direction:column-reverse; gap:7px; }
.slot{ display:flex; align-items:center; gap:14px; padding:12px 15px; border-radius:10px;
       background:var(--card); border:1px solid var(--line); min-height:56px; }
.slot .pk{ font-family:var(--f-display); font-weight:800; font-size:22px; color:var(--dim);
           min-width:30px; }
.slot .nm{ font-family:var(--f-display); font-weight:800; font-size:22px;
           letter-spacing:.02em; text-transform:uppercase; line-height:1; }
.slot .nm.q{ color:var(--line2); }
.slot .tm{ font-family:var(--f-data); font-size:10.5px; color:var(--dim); margin-top:4px; }
.slot.on{ border-color:var(--line2); }
.slot.fresh{ border-color:var(--acc); box-shadow:0 0 0 1px var(--acc), 0 0 34px -6px var(--acc);
             animation:slam .5s cubic-bezier(.2,1.4,.4,1); }
.slot.fresh .pk{ color:var(--acc); }
.slot.final.on{ background:var(--acc-soft); border-color:var(--acc); }
.slot.final.on .nm{ font-size:28px; color:var(--acc); }
.slot.final.on .pk{ color:var(--acc); }
@keyframes slam{ 0%{ transform:scale(1.13); opacity:0 } 60%{ opacity:1 } 100%{ transform:scale(1) } }
.hat{ display:flex; gap:6px; flex-wrap:wrap; margin:10px 0 4px; }
.hat span{ font-family:var(--f-data); font-size:10.5px; letter-spacing:.06em;
           text-transform:uppercase; padding:4px 10px; border-radius:99px;
           border:1px solid var(--line2); color:var(--ink2); }
.hat span.out{ opacity:.25; text-decoration:line-through; }

/* ---- the bottom bar --------------------------------------------------
   The only navigation. A floating pill rather than a full-width bar so it
   reads as an object over the page rather than a browser chrome, and so the
   content behind it stays visible. */
.bb-wrap{ position:fixed; left:0; right:0; display:flex;
          /* Clear of the iPhone home indicator - at 18px flat the pill sits in
             the swipe zone, and this whole league will be on phones. */
          bottom:max(18px, calc(env(safe-area-inset-bottom) + 8px));
          justify-content:center; z-index:1000; pointer-events:none; }
.bb{ pointer-events:auto; display:flex; gap:2px; background:rgba(16,18,24,.94);
     backdrop-filter:blur(16px); border:1px solid var(--line2); border-radius:999px;
     padding:7px; box-shadow:0 12px 36px rgba(0,0,0,.6); }
.bb-link, [data-testid="stMarkdownContainer"] a.bb-link{
  font-family:var(--f-display); font-weight:700; font-size:15px; letter-spacing:.04em;
  text-transform:uppercase; color:var(--ink) !important; text-decoration:none !important;
  border:none !important; border-radius:999px !important; white-space:nowrap; opacity:.55;
  padding:10px 20px !important; cursor:pointer; transition:opacity .2s, background .25s; }
.bb-link:hover{ opacity:.85; }
.bb-link.active{ opacity:1; background:var(--acc) !important; color:var(--acc-ink) !important; }

.bb-scrim{ position:fixed; inset:0; background:rgba(0,0,0,0); pointer-events:none;
           transition:background .25s; z-index:998; }
.bb-scrim.on{ background:rgba(0,0,0,.5); pointer-events:auto; }
.bb-pop{ position:fixed; left:50%;
         bottom:max(84px, calc(env(safe-area-inset-bottom) + 74px)); transform:translate(-50%,10px) scale(.96);
         width:min(340px, calc(100% - 32px)); background:var(--card2);
         border:1px solid var(--line2); border-radius:16px; padding:8px;
         box-shadow:0 16px 44px rgba(0,0,0,.6); opacity:0; pointer-events:none;
         transition:opacity .2s ease, transform .2s ease; z-index:999; }
.bb-pop.on{ opacity:1; pointer-events:auto; transform:translate(-50%,0) scale(1); }
/* One flat sheet, no drill-down: the middle tap only ever existed because the
   sheet could not hold every leaf, and it can. The sheet can outgrow a short
   phone, so it scrolls rather than running off the top. */
.bb-pop{ max-height:min(70vh, calc(100vh - 150px)); overflow-y:auto;
         -webkit-overflow-scrolling:touch; overscroll-behavior:contain; }
.bb-head{ display:flex; align-items:center; gap:9px; padding:8px 10px 10px;
          position:sticky; top:-8px; background:var(--card2); z-index:1; }
.bb-title{ font-family:var(--f-display); font-weight:700; font-size:15px;
           text-transform:uppercase; letter-spacing:.05em; color:var(--dim); }
/* group headings, not tappable rows - the leaves under them are the targets.
   A group may carry an empty label, which renders no heading at all: two
   destinations do not need sorting into categories. */
.bb-group{ font-family:var(--f-data); font-size:9.5px; letter-spacing:.16em;
           text-transform:uppercase; color:var(--acc); padding:11px 12px 5px; }
.bb-group:first-of-type{ padding-top:2px; }
.bb-item, [data-testid="stMarkdownContainer"] a.bb-item{
  display:flex; align-items:center; justify-content:space-between; padding:12px;
  border-radius:10px; font-size:13.5px; font-weight:600; color:var(--ink) !important;
  text-decoration:none !important; cursor:pointer; transition:background .15s; }
.bb-item:hover{ background:rgba(255,255,255,.05); }
.bb-item.leaf{ font-weight:500; font-size:13px; }
.bb-item.leaf.on{ background:var(--acc-soft); color:var(--acc) !important; }

/* the bar floats over the page, so the page needs room to scroll clear of it */
[data-testid="stAppViewContainer"] .main .block-container{
  padding-bottom:calc(120px + env(safe-area-inset-bottom)); }

/* ---- streamlit chrome ----------------------------------------------- */
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"],
#MainMenu, footer{ display:none !important; }
[data-testid="stHeader"]{ height:0; min-height:0; background:transparent; }

.stTabs [data-baseweb="tab-list"]{ gap:6px; border-bottom:none; background:transparent;
  padding:0; margin-bottom:10px; flex-wrap:wrap; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"]{ display:none; }
.stTabs [data-baseweb="tab"]{
  background:var(--card); border:1px solid var(--line); border-radius:99px;
  padding:6px 16px 4px; color:var(--ink2); height:auto; min-height:0;
  transition:background .16s, color .16s, border-color .16s;
}
.stTabs [data-baseweb="tab"] p{
  font-family:var(--f-display); font-weight:700; font-size:17px; letter-spacing:.03em;
  text-transform:uppercase; color:inherit; margin:0; line-height:1.25;
}
.stTabs [data-baseweb="tab"]:hover{ color:var(--ink); border-color:var(--line2); }
.stTabs [aria-selected="true"]{ background:var(--acc) !important; border-color:var(--acc) !important; }
.stTabs [aria-selected="true"] p{ color:var(--acc-ink) !important; }

/* team selector - a quiet control, right-aligned under the masthead */
[data-testid="stSelectbox"]{ max-width:280px; margin-left:auto; }
[data-testid="stSelectbox"] [data-baseweb="select"] > div{
  background:var(--card) !important; border:1px solid var(--line) !important;
  border-radius:99px !important; min-height:0; }
[data-testid="stSelectbox"] [data-baseweb="select"] div[value],
[data-testid="stSelectbox"] [data-baseweb="select"] span{
  font-size:12.5px !important; font-weight:600; }

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

.stButton>button{ background:var(--acc); color:var(--acc-ink); border:none; border-radius:99px;
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
  .bay{ grid-template-columns:1fr; }
  .mast .name{ font-size:29px; }
}

@media (max-width:640px){
  /* The section heading is a flex row of title + rule + eyebrow, and the
     eyebrow is nowrap, so on a phone it shoved the whole row past the viewport.
     Drop the eyebrow to its own line instead. */
  .bar{ flex-wrap:wrap; font-size:24px; gap:10px; }
  .bar::after{ order:2; }
  .bar .n{ order:3; flex-basis:100%; margin-left:0; white-space:normal;
           line-height:1.4; letter-spacing:.1em; }

  .mast{ gap:7px; flex-wrap:wrap; }
  .mast .name{ font-size:26px; }
  .mast .the{ font-size:19px; }
  .mast .yr{ font-size:9.5px; letter-spacing:.1em; }

  [data-testid="stSelectbox"]{ max-width:none; margin:6px 0 0; }
  .glance{ gap:14px; }
  /* The card goes single-column: two numbers side by side survive a phone,
     three meters in a row do not. */
  .tcard .meters{ grid-template-columns:1fr; }
  .tcard .meters .m{ border-left:none; border-top:1px solid var(--line); }
  .tcard .meters .m:first-child{ border-top:none; }
  .tcard .band .row{ grid-template-columns:1fr 1fr; gap:16px; }
  .tcard .band .div{ display:none; }
  .tcard .band .v{ font-size:46px; }
  .tcard .band .n{ font-size:12px; }
  .gl svg.liq{ max-width:132px; }
  .gl .s{ font-size:12px; max-width:24ch; }

  /* No tab row any more - navigation is the floating bottom bar. */
  .lotname{ font-size:12px; }
  .lotname small{ font-size:9px; }
  .rule{ padding:16px 15px; }
  .rule p, .rule li{ font-size:14px; }
  .card{ padding:15px 14px; }
  .worked .wr{ padding:10px 13px; }
  .worked .wr .v{ font-size:20px; }

  /* The rulebook's first column is nowrap so labels stay on one line on a
     desktop. On a phone "Taken in the veteran draft, still an NFL rookie" then
     forces the table wider than the screen. Let it wrap here. */
  .rule table td:first-child{ white-space:normal; width:auto; }
  .rule table{ font-size:13px; table-layout:fixed; }
  .rule table td, .rule table th{ padding:9px 8px; }
  .rule table th:first-child{ width:44%; }

  /* Same trick, same reason, on the section eyebrow and the ledger headers. */
  table.ledger th{ white-space:normal; line-height:1.3; }
  .toc a{ font-size:10px; padding:5px 9px; }
}

}
@media (prefers-reduced-motion:reduce){
  *{ transition:none !important; }
  svg.liq .wv, svg.liq .bob{ animation:none !important; }
}
</style>
"""


def css(palette: str = DEFAULT) -> str:
    """Built by substitution rather than %-formatting. The stylesheet is full of
    literal percent signs and every one of them was an escaping bug waiting."""
    pal = PALETTES.get(palette, PALETTES[DEFAULT])
    return (_TEMPLATE
            .replace("__FONTURL__", FONT_URL)
            .replace("__FONTS__", _FONTS)
            .replace("__VARS__", pal["vars"]))


def fingerprint(palette: str = None) -> str:
    """Six characters that change whenever the stylesheet does.

    Streamlit Cloud can re-run app.py while keeping an already-imported module
    in memory, so a deploy can land with the OLD css still being injected and
    nothing on the page says so. This makes "am I looking at the new code" a
    glance instead of a guess: if the page still looks wrong and this has not
    moved, the process needs a reboot rather than another commit.
    """
    import hashlib
    return hashlib.sha1(css(palette or DEFAULT).encode()).hexdigest()[:6]


def inject(palette: str = None) -> str:
    """One theme for now. The signature keeps a palette argument so a second
    ground can be added as another PALETTES entry without touching callers."""
    palette = palette if palette in PALETTES else DEFAULT
    st.markdown(css(palette), unsafe_allow_html=True)
    return palette


def masthead(subtitle: str) -> None:
    subtitle = "%s &middot; build %s" % (subtitle, fingerprint())
    st.markdown(
        '<div class="mast"><span class="the">the</span>'
        '<span class="name">7<span class="half">&frac12;</span> Men</span>'
        '<span class="yr">%s</span></div>' % subtitle, unsafe_allow_html=True)


def bar(title: str, note: str = "") -> None:
    st.markdown('<div class="bar">%s<span class="n">%s</span></div>' % (title, note),
                unsafe_allow_html=True)


def _wave_d(amp: float, phase: float, second: float = 0.45) -> str:
    """One seamless wave surface as an SVG path, in local coords where y=0 is
    the still surface and +y is down into the liquid.

    Two sine components at 200 and 100 units. Both divide the 200-unit loop
    distance exactly, so translating the path by -200 lands it back on itself
    and the CSS animation never shows a seam.
    """
    import math
    pts = []
    x = -200.0
    while x <= 400.0:
        y = (amp * math.sin(2 * math.pi * x / 200.0 + phase)
             + amp * second * math.sin(2 * math.pi * x / 100.0 - phase * 1.7))
        pts.append("%.1f,%.2f" % (x, y))
        x += 8.0
    return "M " + " L ".join(pts) + " L 400,420 L -200,420 Z"


_WAVE_FRONT = _wave_d(6.5, 0.0)
_WAVE_BACK = _wave_d(4.8, 2.1, second=0.3)

# Streamlit renders every tab panel into the same document, so a per-call index
# is not unique enough - two glance rows both numbering from zero would collide
# and the second row would pick up the first row's gradients. This counter is
# per script run, which is exactly the scope that matters.
_UID = itertools.count()


def liquid(pct: float, color: str, big: str, label: str = "", idx: int = None) -> str:
    """A bowl of liquid that fills to a value and keeps moving.

    The whoop app this borrows from runs a spring-damped surface sim per frame,
    but Streamlit does not execute script tags in markdown, so this is the same
    idea done entirely in CSS: two travelling waves at different speeds and
    directions, plus a slow vertical bob. The beat between the three periods is
    long enough that the surface never visibly repeats.
    """
    # The level is clamped short of full on purpose. A bowl filled to the brim
    # has no surface, so it reads as a solid disc and the liquid is lost - and
    # several of these metrics are 1.0 by construction. The number printed in
    # the middle is the truth; the liquid is texture.
    p = float(pct)
    p = 0.0 if p <= 0.001 else max(0.10, min(0.93, p))
    surface = 200.0 - 200.0 * p
    uid = "lq%d" % (next(_UID) if idx is None else idx)
    return (
      '<svg class="liq" viewBox="0 0 200 200" role="img" aria-label="%(label)s %(big)s">'
      '<defs>'
        '<clipPath id="c%(uid)s"><circle cx="100" cy="100" r="96"/></clipPath>'
        '<linearGradient id="g%(uid)s" x1="0" y1="0" x2="0.3" y2="1">'
          '<stop offset="0" stop-color="%(c)s" stop-opacity=".92"/>'
          '<stop offset="1" stop-color="%(c)s" stop-opacity=".42"/>'
        '</linearGradient>'
      '</defs>'
      '<circle cx="100" cy="100" r="96" fill="var(--card)"/>'
      '<g clip-path="url(#c%(uid)s)">'
        '<g class="bob" style="--sy:%(sy).1fpx">'
          '<path class="wv back" d="%(back)s" fill="%(c)s" opacity=".30"/>'
          '<path class="wv front" d="%(front)s" fill="url(#g%(uid)s)"/>'
        '</g>'
      '</g>'
      '<circle cx="100" cy="100" r="96" fill="none" stroke="%(c)s" stroke-opacity=".45" '
        'stroke-width="2"/>'
      '%(lbl)s'
      '<text x="100" y="%(by)d" text-anchor="middle" font-family="var(--f-display)" '
        'font-weight="800" font-size="50" letter-spacing="0.5" fill="var(--ink)">%(big)s</text>'
      '</svg>'
    ) % {
      "uid": uid, "c": color, "sy": surface, "back": _WAVE_BACK, "front": _WAVE_FRONT,
      "big": big, "label": label, "by": 132 if label else 120,
      "lbl": ('<text x="100" y="76" text-anchor="middle" font-family="var(--f-data)" '
              'font-size="15" font-weight="500" letter-spacing="2.2" fill="var(--ink)" '
              'opacity=".92">%s</text>' % label.upper()) if label else "",
    }


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


def burndown(series: list, budget: int, weeks: int = 17) -> str:
    """Cumulative FAAB spend, one line per team, against the budget ceiling.

    The argument the chart makes is the gap: a dashed bracket runs from each
    highlighted line's endpoint up to the ceiling, because that distance IS the
    bill. Stating "you owe $89" in a table is a fact; drawing it as the empty space
    above a flat line is the same fact with the shape of quitting attached.

    `series` is [{"name", "values", "colour", "key"}] - `key` lines are drawn
    full strength with a bracket, everyone else recedes.
    """
    W, H, PL, PR, PT, PB = 880, 300, 46, 200, 18, 34
    if not series:
        return ""
    n = max(2, weeks)
    x = lambda i: PL + i * (W - PL - PR) / float(n - 1)
    y = lambda v: PT + (1 - min(1.0, v / float(budget))) * (H - PT - PB)

    grid = "".join(
        '<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="var(--line)" stroke-width="1"/>'
        '<text x="%d" y="%.1f" text-anchor="end" font-family="var(--f-data)" font-size="10" '
        'fill="var(--dim)">$%d</text>' % (PL, y(v), W - PR, y(v), PL - 9, y(v) + 3, v)
        for v in range(0, budget + 1, max(1, budget // 4)))

    ceiling = (
        '<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="var(--acc2)" stroke-width="1.5" '
        'stroke-dasharray="5 4"/><text x="%d" y="%.1f" font-family="var(--f-data)" '
        'font-size="10" fill="var(--acc2)">$%d ceiling &#8212; anything under it is owed</text>'
        % (PL, y(budget), W - PR, y(budget), PL + 5, y(budget) - 7, budget))

    lines, marks = "", []
    for srs in series:
        vals = list(srs["values"])[:n] or [0]
        vals += [vals[-1]] * (n - len(vals))
        pts = " ".join("%.1f,%.1f" % (x(i), y(v)) for i, v in enumerate(vals))
        key, col = bool(srs.get("key")), srs.get("colour", "var(--dim)")
        lines += ('<polyline points="%s" fill="none" stroke="%s" stroke-width="%s" '
                  'opacity="%s" stroke-linejoin="round" stroke-linecap="round"/>'
                  % (pts, col, "2.6" if key else "1.3", "1" if key else ".55"))
        ey = y(vals[-1])
        if key:
            lines += ('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                      'stroke-width="1" stroke-dasharray="3 3" opacity=".85"/>'
                      '<circle cx="%.1f" cy="%.1f" r="3.5" fill="%s"/>'
                      % (x(n - 1), ey, x(n - 1), y(budget), col, x(n - 1), ey, col))
        marks.append({"y": ey, "col": col, "key": key,
                      "label": "%s  $%d" % (srs["name"][:16], budget - vals[-1])})

    # Converging lines stack their labels on top of each other; push them apart.
    marks.sort(key=lambda m: m["y"])
    for i in range(1, len(marks)):
        if marks[i]["y"] - marks[i - 1]["y"] < 15:
            marks[i]["y"] = marks[i - 1]["y"] + 15
    overflow = marks[-1]["y"] - (H - PB)
    if overflow > 0:
        for m in marks:
            m["y"] -= overflow
    labels = "".join(
        '<text x="%d" y="%.1f" font-family="var(--f-data)" font-size="10.5" fill="%s" '
        'opacity="%s" font-weight="%s">%s</text>'
        % (W - PR + 11, m["y"] + 3.5, m["col"], "1" if m["key"] else ".7",
           "600" if m["key"] else "400", m["label"])
        for m in marks)

    ticks = "".join(
        '<text x="%.1f" y="%d" text-anchor="middle" font-family="var(--f-data)" font-size="10" '
        'fill="var(--dim)">wk %d</text>' % (x(w - 1), H - 9, w)
        for w in range(1, n + 1, max(1, (n - 1) // 4)))

    return ('<svg viewBox="0 0 %d %d" class="chart" role="img" aria-label="Cumulative FAAB '
            'spend by team">%s%s%s%s%s</svg>' % (W, H, grid, ticks, ceiling, lines, labels))


def capital_strip(states: list) -> str:
    """One block per round: what a team actually holds going into the draft.

    A count of live picks tells you how many. This tells you WHICH - a team
    missing rounds 1 and 2 is in a completely different position from one
    missing 13 and 14, and the table of numbers could not say so.
    """
    cls = {"live": "live", "eaten": "eaten", "traded": "traded", "extra": "extra"}
    return '<div class="capstrip">%s</div>' % "".join(
        '<i class="%s" title="R%d &#183; %s"></i>' % (cls.get(st, "live"), i + 1, st)
        for i, st in enumerate(states))


def taxi_pod(name: str, position: str, source: str, year: int, years: int,
             note: str = "") -> str:
    """A stashed rookie and how much runway he has left.

    The clock is the point: on the last segment he is out of road and has to be
    promoted or released, which is the decision the squeeze is built around.
    """
    expiring = year >= years
    segs = "".join('<i class="%s"></i>' % ("on" if i < year else "")
                   for i in range(years))
    return (
      '<div class="pod %s">'
        '<div class="podtop"><span class="slotno">%s</span>'
        '<span class="chip %s">Year %d of %d</span></div>'
        '<div class="podname">%s</div>'
        '<div class="podmeta">%s &#183; %s</div>'
        '<div class="podclock">%s</div>'
        '%s'
        '<div class="podtags"><span class="chip">Cannot start</span>'
        '<span class="chip">Free of bench</span><span class="chip">No keeper slot</span></div>'
      '</div>'
    ) % ("expiring" if expiring else "", source, "bad" if expiring else "warn",
         year, years, name, position, source, segs,
         ('<p class="tiny" style="margin:9px 0 0">%s</p>' % note) if note else "")


def draw_slot(pick: int, name: str, team: str, revealed: bool,
              fresh: bool = False, final: bool = False) -> str:
    """One envelope in the live draw.

    Unrevealed slots stay in place rather than appearing as they are drawn, so
    the room can see how much is still to come - the empty slots above are the
    tension. The freshly-read one lands with a slam; the last envelope, which is
    first choice, gets the loudest treatment because it is the only one anybody
    will remember.
    """
    cls = " ".join(x for x in (
        "slot", "on" if revealed else "", "fresh" if fresh else "",
        "final" if final else "") if x)
    body = ('<div class="who"><div class="nm">%s</div><div class="tm">%s</div></div>'
            % (name, team)) if revealed else '<div class="who"><div class="nm q">?</div></div>'
    return '<div class="%s"><span class="pk">%d</span>%s</div>' % (cls, pick, body)


def surplus_class(n) -> str:
    if n is None:
        return "z"
    return "p" if n > 0 else ("n" if n < 0 else "z")


def signed(n) -> str:
    if n is None:
        return "-"
    return ("+%d" % n) if n > 0 else str(n)
