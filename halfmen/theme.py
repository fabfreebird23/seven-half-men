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
            "&family=Big+Shoulders+Display:wght@900"
            "&family=Playfair+Display:ital,wght@0,700;1,700&display=swap")

_FONTS = """
  --f-display:'Big Shoulders Display','Archivo Narrow',system-ui,sans-serif;
  --f-body:'Archivo',system-ui,-apple-system,'Segoe UI',sans-serif;
  /* numbers in Archivo with aligned (tabular) figures, not a typewriter
     mono: they still line up in columns, without looking typed */
  --f-data:'Archivo',system-ui,-apple-system,'Segoe UI',sans-serif;
  --f-script:'Pacifico','Snell Roundhand','Brush Script MT',cursive;
  --r:9px; --r-sm:7px;

  /* Kreeper-hub component names, mapped onto this palette so the ported
     weekly screens (Live, Matchup, the Command Center) speak Bloody Sunday:
     crimson where Kreeper uses royal, blue where it uses gold. */
  --panel:var(--card); --panel2:var(--card2); --muted:var(--ink2);
  --teal:var(--good); --red:var(--bad); --amber:var(--warn); --royal:var(--acc); --g1:var(--acc);
  --grad:linear-gradient(var(--acc), var(--acc)); --hl:linear-gradient(var(--acc2), var(--acc2));
  --font-display:var(--f-display); --font-body:var(--f-body); --display-wt:800; --mono:var(--f-data);
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
  font-family:var(--f-body); color:var(--ink); font-variant-numeric:tabular-nums;
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
       margin:-96px calc(50% - 50vw) 18px; padding:22px max(1.2rem, calc(50vw - 50%)) 16px;
       border-radius:0 0 14px 14px; flex-wrap:wrap; }
@media (max-width:640px){ .mast{ margin-top:-72px; padding-top:16px; } }
/* full-bleed: pull out to the viewport edges, then pad back in to the
   content column so the wordmark still lines up with everything below. */
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
/* a talking point: what it is, what to say, and what comes back at you */
.agenda .pitch{ border-top:1px solid var(--line); padding:13px 0 2px; }
.agenda .pitch:first-of-type{ border-top:none; }
.agenda .pitch .lab{ font-family:var(--f-display); font-size:19px; text-transform:uppercase;
                     line-height:1.05; }
.agenda .pitch .say{ font-size:14.5px; color:var(--ink); line-height:1.6; margin-top:6px;
                     max-width:70ch; border-left:2px solid var(--acc); padding-left:12px; }
.agenda .pitch .back{ font-size:12.5px; color:var(--dim); line-height:1.55; margin-top:9px;
                      max-width:70ch; }
.agenda .pitch .back b{ color:var(--warn); font-weight:600; }
.agenda .foot a{ color:var(--acc); text-decoration:none; font-weight:650;
                 font-size:13px; }
.agenda .foot a:hover{ text-decoration:underline; }
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
/* Power-ranking meter. Scaled against the leader rather than against 100, so
   the bar shows the GAP to the top of the league - which is the thing being
   read - instead of a score out of an arbitrary maximum. */
.pwr{height:5px;background:var(--card2);border-radius:1px;overflow:hidden;min-width:70px}
.pwr span{display:block;height:100%;background:var(--acc2)}
tr.me .pwr span{background:var(--acc)}
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

/* ---- whose phone it is: the team chip on the masthead + its dropdown ---- */
.mast .mechip{ display:inline-flex; align-items:center; gap:7px; align-self:center; cursor:pointer;
  user-select:none; background:rgba(0,0,0,.22); border:1px solid rgba(255,255,255,.35);
  border-radius:999px; padding:3px 12px 3px 3px; font-family:var(--f-body); font-size:12px;
  font-weight:600; color:#fff; white-space:nowrap; text-transform:none; letter-spacing:0; }
.mast .mechip i{ font-style:normal; opacity:.75; }
.mast .mechip .av{ width:22px; height:22px; border-radius:50%; background:#fff; color:var(--acc);
  display:inline-flex; align-items:center; justify-content:center; font-family:var(--f-display);
  font-weight:800; font-size:10px; }
.bb-pop.bb-pop-me{ top:70px; bottom:auto; left:auto; right:16px; transform:translateY(-8px) scale(.98);
  width:min(300px, calc(100% - 32px)); }
.bb-pop.bb-pop-me.on{ transform:none; }
.bb-item .sub{ font-size:11px; font-weight:500; color:var(--dim); margin-left:10px; white-space:nowrap; float:right; }
@media (max-width:640px){ .mast .mechip{ margin-left:auto; } .mast .yr{ display:none; } }

/* ---- weekly screens ported from the Kreeper hub (see the aliases in :root) ---- */
/* ================= This Week: Draft Room layout, Kreeper skin =================
   Hero matchup card, action cards, panel tables, the slate, matchup cards and
   slot-by-slot rows. Ported from the approved remock. */
.mechip{ display:inline-flex; align-items:center; gap:8px; background:rgba(0,0,0,.26);
  border:1px solid rgba(255,255,255,.28); border-radius:999px; padding:4px 12px 4px 4px;
  font-size:12px; font-weight:600; color:#fff !important; text-decoration:none !important; white-space:nowrap; }
.mechip i{ font-style:normal; opacity:.7; }
/* the site-wide link rule ([data-testid=stMarkdownContainer] a, !important)
   would paint the chip, its initials and the picker cards accent-purple */
[data-testid="stMarkdownContainer"] a.mechip{ color:#fff !important; }
[data-testid="stMarkdownContainer"] a.tp{ color:var(--ink) !important; }
[data-testid="stMarkdownContainer"] span.wav.wav{ color:#111 !important; }   /* .wav.wav: beats the span reset below */
.mh-right{ display:flex; align-items:center; gap:14px; }
.wav{ width:46px; height:46px; border-radius:10px; background:#fff; color:#111; display:inline-flex;
  align-items:center; justify-content:center; font-family:var(--font-display); font-size:17px;
  font-weight:700; flex:0 0 auto; }
.wav.sm{ width:24px; height:24px; border-radius:50%; font-size:10px; }
.wav.dim{ background:#d8d8de; }
.weyebrow{ font-size:10px; font-weight:600; letter-spacing:1.6px; text-transform:uppercase;
  color:var(--muted); margin:0 0 8px; }
.weyebrow.pad{ margin:16px 0 8px; }

.hero{ position:relative; border:1px solid var(--line); border-radius:14px; overflow:hidden; padding:18px 18px 0;
  background:var(--panel); border-top:3px solid var(--royal); }
.hrow{ display:flex; align-items:center; justify-content:space-between; gap:12px; }
.wwho{ display:flex; align-items:center; gap:12px; min-width:0; }
.wwho.r{ text-align:right; }
.wwho b{ display:block; font-family:var(--font-display); font-size:21px; font-weight:600; line-height:1.1; }
.wwho em{ font-style:normal; font-size:10px; font-weight:600; letter-spacing:1.2px; text-transform:uppercase; color:var(--muted); }
.wkpill{ font-size:10.5px; font-weight:600; letter-spacing:1.4px; color:#fff; border:1px solid rgba(255,255,255,.22);
  background:rgba(251,8,73,.22); border-radius:999px; padding:4px 12px; white-space:nowrap; }
.hnum{ display:flex; align-items:baseline; justify-content:space-between; margin:10px 0 8px; }
.hnum .big{ font-family:var(--font-display); font-size:58px; font-weight:600; line-height:1; }
.big.dim{ color:var(--dim); }
.hk{ font-size:10px; font-weight:600; letter-spacing:1.8px; color:var(--muted); text-transform:uppercase; }
.wpbar{ height:10px; border-radius:6px; background:rgba(255,255,255,.08); overflow:hidden; }
.wpbar.sm{ height:6px; margin:10px 0 6px; }
.wpbar i{ display:block; height:100%; background:var(--hl); border-radius:6px; }
.hrow.lab{ margin:8px 0 14px; font-size:11px; color:var(--muted); }
.hrow.lab b{ color:var(--teal); font-size:15px; }
.hcells{ display:grid; grid-template-columns:repeat(4,1fr); margin:0 -18px; border-top:1px solid var(--line); }
.hc{ padding:12px 18px 14px; border-left:1px solid var(--line); }
.hc:first-child{ border-left:none; }
.hc i{ display:block; font-style:normal; font-size:9.5px; font-weight:600; letter-spacing:1.5px; color:var(--muted); text-transform:uppercase; }
.hc b{ display:block; font-family:var(--font-display); font-size:24px; font-weight:600; margin:3px 0 1px; }
.hc b.good{ color:var(--teal); } .hc b.amber{ color:var(--amber); } .hc b.bad{ color:var(--red); }
.hc span{ font-size:11.5px; color:var(--muted); }
.lockline{ font-size:10.5px; font-weight:600; letter-spacing:1.4px; color:var(--muted); margin:14px 0 16px; text-transform:uppercase; }
.lockline b{ color:var(--g1); }

.todo{ --c:var(--amber); display:flex; gap:14px; align-items:center; background:var(--panel);
  border:1px solid var(--line); border-radius:10px; padding:13px 14px; margin-bottom:8px; box-shadow:inset 3px 0 0 var(--c); }
.todo.bad{ --c:var(--red); } .todo.good{ --c:var(--teal); }
.todo .ic{ width:30px; height:30px; border-radius:8px; border:1px solid var(--c); color:var(--c);
  display:flex; align-items:center; justify-content:center; flex:0 0 auto; }
.todo b{ display:block; font-size:14px; font-weight:600; }
.todo span{ font-size:12px; color:var(--muted); }
.todo span b{ display:inline; color:var(--ink); }
.todo .tv{ margin-left:auto; text-align:right; }
.todo .tv b{ font-family:var(--font-display); font-size:22px; color:var(--c); }
.todo .tv i{ font-style:normal; font-size:9px; font-weight:600; letter-spacing:1.4px; color:var(--muted); }
.todo-foot{ font-size:12px; color:var(--muted); background:var(--panel); border:1px solid var(--line);
  border-radius:10px; padding:11px 14px; }
.todo-foot b{ color:var(--ink); }

table.dt{ width:100%; border-collapse:collapse; background:var(--panel); border:1px solid var(--line);
  border-radius:10px; overflow:hidden; font-size:13.5px; }
table.dt td{ padding:8px 12px; border-top:1px solid var(--line); vertical-align:middle; }
table.dt tr:first-child td{ border-top:none; }
table.dt td.two b{ display:block; font-weight:600; font-size:13.5px; }
table.dt td.two span{ display:block; font-size:10.5px; color:var(--muted); margin-top:2px; }
table.dt td.two.w b{ color:var(--teal); }
table.dt td.two b .pos{ display:inline !important; font-size:10px; color:var(--muted); font-weight:500; margin-left:4px; }
table.dt td.rk{ font-family:var(--font-display); font-weight:600; color:var(--muted); font-size:16px; width:30px; text-align:center; }
table.dt td.num{ text-align:right; white-space:nowrap; font-weight:500; }
table.dt td.mut{ color:var(--muted); }
table.dt tr.swap td{ background:rgba(215,112,16,.08); }
.wslot{ display:inline-block; min-width:42px; text-align:center; font-size:10px; font-weight:700;
  border:1px solid; border-radius:6px; padding:3px 6px; }
td.barc{ width:30%; }
.wbar{ height:6px; border-radius:4px; background:rgba(255,255,255,.07); overflow:hidden; }
.wbar i{ display:block; height:100%; background:var(--hl); border-radius:4px; }

.wstrip{ display:grid; grid-template-columns:repeat(auto-fill,minmax(118px,1fr)); gap:6px; margin-bottom:6px; }
.gm{ display:grid; grid-template-columns:1fr auto; gap:1px 8px; background:var(--panel); border:1px solid var(--line);
  border-radius:8px; padding:8px 10px; font-size:12px; }
.gm b{ text-align:right; } .gm em{ grid-column:1/-1; font-style:normal; font-size:9.5px; font-weight:600;
  letter-spacing:1.2px; color:var(--muted); margin-top:3px; }
.gm.in{ border-color:rgba(54,157,134,.6); } .gm.in em{ color:var(--teal); }
.gm.pre{ border-color:rgba(87,142,213,.55); } .gm.pre em{ color:var(--g1); }
.gm.post{ opacity:.55; padding:6px 9px; font-size:11px; }

.lcard{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:12px 14px; }
.lcard.mine{ border-color:rgba(251,8,73,.5); box-shadow:0 0 0 1px rgba(251,8,73,.2) inset; margin-bottom:12px; padding-bottom:4px; }
.lhead{ display:grid; grid-template-columns:1fr auto 1fr; align-items:center; gap:10px; }
.lhead .two b{ font-family:var(--font-display); font-size:17px; font-weight:600; display:block; }
.lhead .two span{ font-size:10.5px; color:var(--muted); display:block; }
.lhead .two:last-child{ text-align:right; }
.lhead .two.w b{ color:var(--teal); }
.ls{ font-family:var(--font-display); font-size:30px; font-weight:600; display:flex; gap:8px; align-items:baseline; }
.ls span{ color:var(--muted); font-size:18px; } .ls .dim{ color:var(--dim); }
.lfoot{ display:flex; justify-content:space-between; font-size:10.5px; color:var(--muted); gap:8px; }
.lfoot b{ color:var(--ink); }
.lgrid{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }
.lgrid .lhead{ grid-template-columns:1fr; gap:4px; }
.lgrid .lhead .two:last-child{ text-align:left; }
.lgrid .ls{ font-size:24px; } .lgrid .lfoot .mid{ display:none; }
.forow{ display:grid; grid-template-columns:1fr 64px 1fr; align-items:center; border-top:1px solid var(--line);
  margin:0 -14px; padding:0 14px; }
.fo{ display:flex; align-items:center; justify-content:space-between; gap:10px; padding:8px 0; }
.fo.r{ flex-direction:row-reverse; text-align:right; }
.fn b{ display:block; font-size:13.5px; font-weight:600; }
.fn em{ font-style:normal; font-size:10px; color:var(--muted); }
.fp{ font-family:var(--font-display); font-size:20px; font-weight:600; }
.fo.live .fn em{ color:var(--g1); } .fo.inplay .fn em{ color:var(--teal); }
.fp .proj{ color:var(--muted); font-size:15px; }
.fp .proj::before{ content:"proj "; font-family:var(--font-body); font-size:9px; }
.fm{ display:flex; flex-direction:column; align-items:center; gap:3px; }
.fm i{ font-style:normal; font-size:10px; color:var(--muted); }
.fm i.pos{ color:var(--teal); } .fm i.neg{ color:var(--red); }
.gs{ display:none; }

.picker h3{ font-family:var(--font-display) !important; font-weight:600 !important; font-size:26px !important;
  text-transform:uppercase; margin:2px 0 6px !important; padding:0 !important; }
.picker p{ margin:0 0 14px; font-size:13px; line-height:1.55; color:var(--muted); }
.tpgrid{ display:grid; grid-template-columns:1fr 1fr; gap:8px; }
a.tp{ display:block; border:1px solid var(--line); border-radius:10px; padding:10px 12px; background:var(--panel2);
  text-decoration:none !important; color:var(--ink) !important; }
a.tp b{ display:block; font-size:13.5px; } a.tp em{ font-style:normal; font-size:11px; color:var(--muted); }
a.tp:hover, a.tp.on{ background:linear-gradient(var(--panel2),var(--panel2)) padding-box, var(--hl) border-box;
  border:1px solid transparent; }
.wk-cols{ display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1.15fr); gap:20px; align-items:start; }

/* The theme forces every markdown <span> to --ink (!important) so Streamlit's
   own greys never leak in. These components colour their spans on purpose,
   so they reset to inherit and re-assert their own colours at a higher
   specificity. Slot chips carry their colour in --c because an inline
   `color` would lose to the !important too. */
[data-testid="stMarkdownContainer"] :is(.hero, .todo, .todo-foot, table.dt, .lcard, .wstrip, .picker, .mh-right, .lockline, .ktray, .kgrid) span{ color:inherit !important; }
[data-testid="stMarkdownContainer"] .hero .big.dim, [data-testid="stMarkdownContainer"] .ls .dim{ color:var(--dim) !important; }
[data-testid="stMarkdownContainer"] :is(.hk, .hc span, .todo div > span, table.dt td.two span, .lhead .two span, .ls span, .fp .proj, .kt span, .kc-top .pos, .ka){ color:var(--muted) !important; }
[data-testid="stMarkdownContainer"] .kgrid span.wchip.amber.amber{ color:var(--amber) !important; border-color:rgba(215,112,16,.4); }
[data-testid="stMarkdownContainer"] span.wchip.good.good{ color:var(--teal) !important; }
[data-testid="stMarkdownContainer"] span.wchip.bad.bad{ color:var(--red) !important; }
/* .wslot.wslot: out-ranks the inherit reset above, which carries a table.dt */
[data-testid="stMarkdownContainer"] span.wslot.wslot{ color:var(--c, var(--muted)) !important; border-color:color-mix(in srgb, var(--c, #8a8a95) 35%, transparent);
  background:color-mix(in srgb, var(--c, #8a8a95) 8%, transparent); }

/* keeper outlook: the five-slot tray, then one card per player with his ladder */
.hero.kh{ padding:0; } .hero.kh .hcells{ margin:0; border-top:none; }
.ktray{ display:grid; grid-template-columns:repeat(5,1fr); gap:8px; }
.kt{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:12px 10px; text-align:center; }
.kt i{ display:block; font-style:normal; font-size:9.5px; font-weight:600; letter-spacing:1.4px; text-transform:uppercase; color:var(--muted); margin-bottom:8px; }
.kt .kh-img{ width:52px; height:52px; border-radius:50%; object-fit:cover; background:var(--panel2); display:block; margin:0 auto 8px; }
.kt b{ display:block; font-size:13px; font-weight:600; line-height:1.2; }
.kt span{ display:block; font-size:11px; margin-top:3px; }
.kt em{ font-style:normal; font-weight:600; } .kt em.good{ color:var(--teal); } .kt em.bad{ color:var(--red); }
.kt.empty{ border-style:dashed; opacity:.6; } .kt.empty b{ font-family:var(--font-display); font-size:20px; margin:18px 0 4px; }
.kgrid{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.kcard2{ display:flex; align-items:center; gap:12px; background:var(--panel); border:1px solid var(--line);
  border-radius:12px; padding:12px 14px; }
.kcard2.keep{ box-shadow:inset 3px 0 0 var(--teal); } .kcard2.next{ box-shadow:inset 3px 0 0 var(--amber); }
.kcard2.blocked{ opacity:.7; } .kcard2.cut{ opacity:.82; }
.kcard2 .kh-img{ width:44px; height:44px; border-radius:50%; object-fit:cover; background:var(--panel2); flex:0 0 auto; }
.kc-main{ flex:1; min-width:0; }
.kc-top{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.kc-top b{ font-size:14px; font-weight:600; } .kc-top .pos{ font-size:11px; }
.kc-top .wchip{ margin-left:auto; }
.kladder{ display:flex; align-items:center; gap:6px; margin:8px 0 6px; flex-wrap:wrap; }
.ks{ display:inline-flex; flex-direction:column; align-items:center; background:var(--panel2); border:1px solid var(--line);
  border-radius:8px; padding:3px 9px; min-width:54px; }
.ks i{ font-style:normal; font-size:9px; font-weight:600; letter-spacing:1px; color:var(--muted); }
.ks b{ font-family:var(--font-display); font-size:15px; font-weight:600; }
.ks.now{ border-color:rgba(251,8,73,.55); background:rgba(251,8,73,.12); }
.ka{ font-size:12px; } .kb{ font-size:12px; color:var(--red) !important; font-weight:600; }
.kc-how{ font-size:11px; color:var(--muted); }
.kv{ text-align:right; flex:0 0 auto; }
.kv b{ display:block; font-family:var(--font-display); font-size:24px; font-weight:600; line-height:1; }
.kv i{ font-style:normal; font-size:9px; font-weight:600; letter-spacing:1.2px; color:var(--muted); text-transform:uppercase; }
.kv.good b{ color:var(--teal); } .kv.bad b{ color:var(--red); }

@media (max-width: 760px){
  .wk-cols{ grid-template-columns:minmax(0,1fr); }
  .hero .wkpill, .mh-right .mh-meta{ display:none; }
  .wwho{ flex:1 1 0; gap:8px; } .wwho.r{ justify-content:flex-end; }
  .wwho b{ font-size:15px; } .wwho em{ font-size:8.5px; letter-spacing:.8px; }
  .wav{ width:34px; height:34px; font-size:13px; border-radius:8px; }
  .hnum .big{ font-size:42px; }
  .hcells{ grid-template-columns:1fr 1fr; } .hc:nth-child(3){ border-left:none; }
  .hc:nth-child(n+3){ border-top:1px solid var(--line); } .hc b{ font-size:20px; }
  .lgrid{ grid-template-columns:1fr; }
  .lhead .two b{ font-size:14px; } .ls{ font-size:22px; }
  .gl{ display:none; } .gs{ display:inline; } .fp{ font-size:17px; } .fn b{ font-size:12px; line-height:1.25; }
  .forow{ grid-template-columns:1fr 46px 1fr; } .fo{ gap:6px; } .wslot{ min-width:36px; padding:2px 4px; font-size:9px; }
  .tpgrid{ grid-template-columns:1fr; }
  table.lb .pf{ display:none; } .pbar{ min-width:36px; }
  table.lb td.two b{ font-size:12.5px; line-height:1.25; } .wchip{ padding:2px 6px; letter-spacing:.4px; }
  .ktray{ grid-template-columns:repeat(3,1fr); } .kgrid{ grid-template-columns:1fr; }
  .kt .kh-img{ width:40px; height:40px; } .kt b{ font-size:12px; }
  td.barc{ width:22%; }
}

/* injury-risk badge in lineup rows: grey when it's the usual in-game risk,
   amber worth watching, coral high, solid coral out. Doubled classes beat
   the markdown-span colour reset. */
table.dt td.risk{ width:1%; white-space:nowrap; text-align:right; padding-left:4px; padding-right:4px; }
[data-testid="stMarkdownContainer"] :is(td.risk, .xl-r) span.rkp.rkp{ display:inline-block; font-size:10.5px; font-weight:600;
  padding:2px 7px; border-radius:999px; border:1px solid var(--line); color:var(--muted) !important; }
[data-testid="stMarkdownContainer"] :is(td.risk, .xl-r) span.rkp.rkp.watch{ color:var(--amber) !important;
  border-color:color-mix(in srgb, var(--amber) 45%, transparent); }
[data-testid="stMarkdownContainer"] :is(td.risk, .xl-r) span.rkp.rkp.high{ color:var(--red) !important;
  border-color:color-mix(in srgb, var(--red) 50%, transparent); }
[data-testid="stMarkdownContainer"] :is(td.risk, .xl-r) span.rkp.rkp.out{ color:#fff !important; background:var(--red); border-color:var(--red); }

.wbar .g{ color:var(--acc); }

/* Big Shoulders is this brand's display face at 800; the ported screens set
   600, which reads thin in it */
.hnum .big, .hc b, .wwho b, .ls, .fp, .todo .tv b, .kv b, .ks b, .kt.empty b{ font-weight:800; }
/* ==== The editorial look (from the Draft Room), in Bloody Sunday crimson / blue / black ====
   Royal does the Draft Room's red job (the page wants you to act), black with
   a gold edge its status job; gold where it had cream. Everything sits under
   .kx so the theme's "every markdown span is --ink" rule can be reset once. */
[data-testid="stMarkdownContainer"] .kx span{ color:inherit !important; }
.kx{ --kr:#c8063b; --kr2:#fb0849; --kg:#578ed5; --kink:#101011; --kl:#332f31; }
/* heroes */
.kx.bh{ position:relative; display:grid; grid-template-columns:1fr; align-items:end; border-radius:12px; overflow:hidden;
  min-height:200px; margin:0 0 14px; }
.kx.bh.has-grid{ grid-template-columns:1fr auto; }
.kx.bh.royal{ background:var(--kr); } .kx.bh.ink{ background:var(--kink); box-shadow:inset 0 0 0 1px var(--kl); }
.kx.bh.ink::after{ content:""; position:absolute; left:0; top:0; bottom:0; width:5px; background:var(--kg); z-index:3; }
.kx.bh.ink::before{ content:""; position:absolute; right:0; top:0; bottom:0; width:42%; z-index:0;
  background:radial-gradient(ellipse 60% 75% at 72% 100%,rgba(251,8,73,.6),transparent 70%); }
.kx.bh.ink.has-grid::before{ display:none; }
.kx .bh-l{ position:relative; z-index:2; padding:16px 22px 18px; }
[data-testid="stMarkdownContainer"] .kx .bh-k{ display:block; font-size:10.5px; letter-spacing:.18em; font-weight:700; color:var(--kg) !important; text-transform:uppercase; }
[data-testid="stMarkdownContainer"] .kx.royal .bh-k{ color:#ffd0dc !important; }
.kx .bh-n{ display:block; font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:120px; line-height:.92; color:var(--ink); margin-top:20px; }
.kx.ink .bh-n{ color:var(--kg); }
.kx .bh-l em{ display:block; font-family:'Playfair Display',serif; font-style:italic; font-weight:700; font-size:22px; color:var(--ink);
  margin-top:6px; max-width:46ch; line-height:1.25; }
.kx .bh-l em b{ font-style:normal; text-decoration:underline; text-decoration-color:var(--kg); text-underline-offset:4px; }
.kx .bh-grid{ position:relative; z-index:2; display:grid; grid-template-columns:repeat(2,minmax(140px,1fr)); align-self:stretch;
  border-left:1px solid rgba(87,142,213,.25); }
.kx .bh-grid div{ padding:11px 15px; border-bottom:1px solid rgba(87,142,213,.18); border-right:1px solid rgba(87,142,213,.18); }
[data-testid="stMarkdownContainer"] .kx .bh-grid span{ display:block; font-size:10px; letter-spacing:.14em; color:var(--kg) !important; text-transform:uppercase; }
.kx .bh-grid b{ display:block; font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:34px; color:var(--ink); }
.kx .bh-grid i{ font-style:normal; font-size:11.5px; color:var(--muted); }
.kx .bh-duo{ position:absolute; right:3%; bottom:0; height:112%; max-height:260px; object-fit:cover !important; object-position:center bottom !important; z-index:1; }
.kx.royal .bh-duo{ filter:grayscale(1) contrast(1.15); mix-blend-mode:multiply; opacity:.95; }
.kx.ink .bh-duo{ filter:grayscale(1) contrast(1.2); opacity:.8;
  -webkit-mask-image:radial-gradient(ellipse 56% 92% at 50% 100%,#000 62%,transparent 100%); mask-image:radial-gradient(ellipse 56% 92% at 50% 100%,#000 62%,transparent 100%); }
/* scoreboard */
.kx.xb{ display:grid; grid-template-columns:1fr 280px 1fr; border-radius:12px 12px 0 0; overflow:hidden; min-height:176px; }
.kx .xb-s{ display:flex; align-items:flex-end; gap:14px; padding:14px 20px; overflow:hidden; min-width:0; }
.kx .xb-s.me{ background:var(--kr); justify-content:flex-end; } .kx .xb-s.op{ background:var(--kink); box-shadow:inset 0 0 0 1px var(--kl); }
.kx .xb-ph{ height:190px; width:auto; max-width:none; aspect-ratio:350 / 254; object-fit:cover !important; object-position:center bottom !important;
  filter:grayscale(1) contrast(1.2); margin-bottom:-24px; flex:none; }
.kx .xb-s.me .xb-ph{ mix-blend-mode:multiply; }
/* manager duotones on the cover, fight-poster style (ported from Kreeper):
   each photo is a square the full height of its band at the outer edge, sized
   by height so a wide screen never zooms into a slice of the face; the two
   face each other (theirs mirrored) and fade out before the score; VS sits
   on the seam */
.kx .xb-s.fight{ position:relative; }
.kx .xb-s .xb-ph.xb-mg{ position:absolute; top:0; bottom:0; height:100%; width:auto; max-width:62%; aspect-ratio:1 / 1; margin:0;
  object-fit:cover !important; object-position:center 20% !important; filter:none; mix-blend-mode:normal; opacity:1; z-index:0;
  -webkit-mask-image:linear-gradient(to right,#000 72%,transparent 100%); mask-image:linear-gradient(to right,#000 72%,transparent 100%); }
.kx .xb-s.me .xb-ph.xb-mg{ left:0; }
.kx .xb-s.op .xb-ph.xb-mg{ right:0; left:auto; transform:scaleX(-1); opacity:.92;
  -webkit-mask-image:linear-gradient(to right,#000 72%,transparent 100%); mask-image:linear-gradient(to right,#000 72%,transparent 100%); }
.kx .xb-s.fight .xb-t{ position:relative; z-index:1; }
.kx .xb-vs{ display:inline-block; font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-style:italic; font-size:20px; line-height:1;
  color:#06101c; background:var(--kg); padding:4px 10px; border-radius:4px; transform:skewX(-8deg); margin-bottom:8px;
  box-shadow:0 6px 18px rgba(0,0,0,.45); }
@media (max-width:760px){
  /* the halves touch on a phone: VS moves onto their seam, photos dim under the score */
  .kx.xb{ position:relative; }
  .kx .xb-vs{ position:absolute; left:50%; top:59px; translate:-50% -50%; transform:skewX(-8deg); z-index:3; font-size:15px; margin:0; }
  .kx .xb-s .xb-ph.xb-mg{ max-width:78%; opacity:.55; }
  .kx .xb-s.op .xb-ph.xb-mg{ opacity:.5; }
  .kx .xb-s.me.fight{ padding-right:24px; } .kx .xb-s.op.fight{ padding-left:24px; }
}
.kx .xb-s.op .xb-ph{ opacity:.6; -webkit-mask-image:radial-gradient(ellipse 56% 92% at 50% 100%,#000 62%,transparent 100%);
  mask-image:radial-gradient(ellipse 56% 92% at 50% 100%,#000 62%,transparent 100%); }
.kx .xb-t{ min-width:0; } .kx .xb-t b{ white-space:nowrap; } .kx .xb-t i{ display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
[data-testid="stMarkdownContainer"] .kx .xb-t span{ display:block; font-size:10.5px; letter-spacing:.16em; font-weight:700; color:#ffd0dc !important;
  text-transform:uppercase; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
[data-testid="stMarkdownContainer"] .kx .xb-s.op .xb-t span{ color:var(--kg) !important; }
.kx .xb-t b{ display:block; font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:76px; line-height:.98; color:var(--ink); }
.kx .xb-s.op .xb-t b{ color:#b9b9c2; }
.kx .xb-t i{ font-style:normal; font-size:12px; color:#ffd0dc; } .kx .xb-s.op .xb-t i{ color:var(--muted); }
.kx .xb-m{ background:#08080a; box-shadow:inset 0 1px 0 var(--kl), inset 0 -1px 0 var(--kl); display:flex; flex-direction:column;
  align-items:center; justify-content:center; padding:10px; }
[data-testid="stMarkdownContainer"] .kx .xb-k{ font-family:'Archivo',sans-serif; font-size:10px; letter-spacing:.14em; color:var(--kg) !important; text-transform:uppercase; }
.kx .xb-m b{ font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:84px; line-height:1; color:var(--kg); }
.kx .xb-m sup{ font-size:30px; }
.kx .xb-m em{ font-family:'Playfair Display',serif; font-style:italic; font-size:16px; color:var(--muted); }
.kx .xb-bar{ width:80%; height:6px; background:var(--kl); border-radius:99px; margin-top:10px; overflow:hidden; }
.kx .xb-bar i{ display:block; height:100%; background:linear-gradient(90deg,var(--kr2),var(--kg)); }
.kx.xb-tiles{ display:grid; grid-template-columns:repeat(4,1fr); gap:1px; background:var(--kl); border:1px solid var(--kl); border-top:0;
  border-radius:0 0 12px 12px; overflow:hidden; margin-bottom:12px; }
.kx.xb-tiles div{ background:var(--kink); padding:10px 14px; min-width:0; }
[data-testid="stMarkdownContainer"] .kx.xb-tiles span{ display:block; font-size:10px; letter-spacing:.14em; color:var(--dim) !important; text-transform:uppercase; }
.kx.xb-tiles b{ display:block; font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:28px; color:var(--ink); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.kx.xb-tiles b.amber{ color:var(--kg); }
.kx.xb-tiles i{ font-style:normal; font-size:11.5px; color:var(--muted); }
/* ---- ported from the Kreeper League: Game of the Week, your rooting card,
   the week in review. Same markup, Bloody Sunday type and palette. ---- */
/* Game of the Week (app._render_gotw): both managers in gold, facing off, the
   stakes as the cover number; then the tale of the tape and who it moves.
   Spans need the stMarkdownContainer prefix + !important to beat the ink reset. */
.kx.gw{ display:grid; grid-template-columns:1fr 280px 1fr; min-height:200px; border-radius:12px 12px 0 0; overflow:hidden;
  background:radial-gradient(70% 120% at 50% 100%,rgba(87,142,213,.16),transparent 70%),#0a0a0c;
  box-shadow:inset 0 0 0 1px var(--kl); border-bottom:3px solid var(--kg); }
.kx .gw-s{ position:relative; overflow:hidden; display:flex; align-items:center; padding:0 22px; min-width:0; }
.kx .gw-s.l{ justify-content:flex-end; text-align:right; }
.kx .gw-ph{ position:absolute; top:0; bottom:0; height:100%; width:auto; max-width:62%; aspect-ratio:1 / 1; object-fit:cover !important;
  object-position:center 20% !important; z-index:0; -webkit-mask-image:linear-gradient(to right,#000 72%,transparent);
  mask-image:linear-gradient(to right,#000 72%,transparent); }
.kx .gw-s.l .gw-ph{ left:0; } .kx .gw-s.r .gw-ph{ right:0; transform:scaleX(-1); }
.kx .gw-t{ position:relative; z-index:1; min-width:0; }
[data-testid="stMarkdownContainer"] .kx .gw-t span{ display:block; font-size:10.5px; letter-spacing:.16em; font-weight:700; text-transform:uppercase; color:var(--kg) !important;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.kx .gw-t b{ display:block; font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:64px; line-height:1; text-transform:uppercase; color:var(--ink); }
.kx .gw-t i{ display:block; font-style:normal; font-size:12.5px; color:#cfcfd6; }
.kx .gw-t em{ font-style:normal; font-weight:700; } .kx .gw-t em.up{ color:var(--teal); } .kx .gw-t em.dn{ color:#ff8fa3; }
.kx .gw-m{ display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:12px; }
[data-testid="stMarkdownContainer"] .kx .gw-k{ font-family:'Archivo',sans-serif; font-size:10px; letter-spacing:.14em; text-transform:uppercase; color:var(--kg) !important; }
[data-testid="stMarkdownContainer"] .kx .gw-vs{ font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-style:italic; font-size:18px; line-height:1; color:#06101c !important;
  background:var(--kg); padding:4px 10px; border-radius:4px; transform:skewX(-8deg); margin:8px 0 2px; }
.kx .gw-m b{ font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:76px; line-height:1; color:var(--kg); }
.kx .gw-m em{ font-family:'Playfair Display',serif; font-style:italic; font-size:15px; color:#d8d8de; }
[data-testid="stMarkdownContainer"] .kx .gw-sub{ font-size:11px; color:var(--muted) !important; margin-top:4px; }
.kx.gw-tiles .amber{ color:var(--kg); }
.gw-cols{ margin-top:14px; }
/* tale of the tape */
.kx.gw-tape, .kx.gw-ride{ background:var(--kink); border:1px solid var(--kl); border-radius:12px; padding:12px 14px; }
.kx .gw-th{ display:grid; grid-template-columns:auto 1fr 1fr auto; gap:10px; align-items:center; margin-bottom:6px; }
.kx .gw-th b{ display:block; font-family:'Archivo',sans-serif; font-weight:600; font-size:15px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
[data-testid="stMarkdownContainer"] .kx .gw-th span{ font-size:11px; color:var(--muted) !important; } .kx .gw-th .r{ text-align:right; } .kx .gw-th > div{ min-width:0; }
.kx .gw-tp{ display:grid; grid-template-columns:minmax(0,1fr) 52px 120px 52px minmax(0,1fr); gap:8px; align-items:center; padding:8px 0; border-top:1px solid var(--kl); }
.kx .gw-n{ font-size:13.5px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; } .kx .gw-n.r{ text-align:right; }
[data-testid="stMarkdownContainer"] .kx .gw-n span{ margin-left:5px; font-size:10px; font-weight:500; color:var(--muted) !important; }
.kx .gw-p{ font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:22px; text-align:center; color:#9d9da6; }
.kx .gw-p.w{ color:var(--ink); } .kx .gw-p.pj{ font-style:italic; }
.kx .gw-key{ margin-top:6px; font-size:10.5px; color:var(--muted); } .kx .gw-key i{ font-style:italic; color:var(--ink); }
.kx .gw-e{ display:grid; grid-template-columns:1fr 36px 1fr; align-items:center; }
[data-testid="stMarkdownContainer"] .kx .gw-e span{ text-align:center; font-family:'Archivo',sans-serif; font-size:9.5px; letter-spacing:.1em; color:var(--kg) !important; }
.kx .gw-h{ height:6px; background:rgba(255,255,255,.06); border-radius:4px; overflow:hidden; display:flex; } .kx .gw-h.l{ justify-content:flex-end; }
.kx .gw-h i{ display:block; height:100%; background:var(--kg); }
.kx .gw-note{ margin-top:10px; background:rgba(87,142,213,.08); border:1px solid rgba(87,142,213,.3); border-radius:10px; padding:9px 12px;
  font-size:12.5px; line-height:1.5; color:#e8e2d0; } .kx .gw-note b{ color:var(--kg); }
i.mf.gw-f{ width:40px; height:40px; border-color:var(--kg); }
/* what's riding on it */
.kx .gw-leg{ display:flex; gap:16px; flex-wrap:wrap; margin-bottom:6px; }
[data-testid="stMarkdownContainer"] .kx .gw-leg span{ font-size:11.5px; color:var(--muted) !important; } [data-testid="stMarkdownContainer"] .kx .gw-leg span.dim{ opacity:.7; }
.kx .gw-leg .gw-dot{ position:static; display:inline-block; transform:none; margin-right:6px; vertical-align:-2px; }
.kx .gw-rd{ display:grid; grid-template-columns:34px 70px 1fr 84px; gap:10px; align-items:center; padding:6px 0; border-top:1px solid var(--kl); }
.kx .gw-rd b{ font-family:'Archivo',sans-serif; font-weight:600; font-size:14.5px; }
.kx .gw-tr{ position:relative; height:10px; border-radius:6px; background:rgba(255,255,255,.06); }
.kx .gw-tr::after{ content:""; position:absolute; left:50%; top:-4px; bottom:-4px; width:1px; background:rgba(255,255,255,.16); }
.kx .gw-band{ position:absolute; top:0; bottom:0; background:rgba(87,142,213,.25); border-radius:6px; }
.kx .gw-dot{ position:absolute; top:50%; width:14px; height:14px; border-radius:50%; transform:translate(-50%,-50%); border:2px solid #0c0c0e; }
.kx .gw-dot.a{ background:#5b86c9; } .kx .gw-dot.b{ background:var(--kg); }
[data-testid="stMarkdownContainer"] .kx .gw-nums{ font-size:12px; text-align:right; } .kx .gw-nums em{ font-style:normal; font-weight:700; }
.kx .gw-nums em.a{ color:#8fb0e6; } .kx .gw-nums em.b{ color:var(--kg); }
/* your rooting card (Home) */
.kx.rc{ background:var(--kink); border:1px solid var(--kl); border-radius:12px; padding:12px 14px; margin:14px 0 4px; }
.kx .rc-h{ display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; margin-bottom:10px; }
[data-testid="stMarkdownContainer"] .kx .rc-h span{ font-size:10.5px; font-weight:700; letter-spacing:.16em; text-transform:uppercase; color:var(--kg) !important; }
.kx .rc-h b{ font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:28px; line-height:1; color:var(--kg); }
.kx .rc-h em{ font-style:normal; font-size:12px; color:var(--muted); }
.kx .rc-row{ display:grid; grid-template-columns:repeat(auto-fill,minmax(170px,1fr)); gap:8px; }
.kx .rc-c{ display:flex; align-items:center; gap:10px; background:rgba(255,255,255,.03); border:1px solid var(--kl); border-radius:10px; padding:8px 10px; min-width:0; }
.kx .rc-c > div{ min-width:0; } .kx .rc-c b{ display:block; font-family:'Archivo',sans-serif; font-weight:600; font-size:15px; }
.kx .rc-c b i{ font-style:normal; color:var(--kg); }
[data-testid="stMarkdownContainer"] .kx .rc-c span{ display:block; font-size:11px; color:var(--muted) !important; }
.kx .rc-c em{ font-style:normal; font-size:11px; font-weight:700; } .kx .rc-c em.up{ color:var(--teal); } .kx .rc-c em.dn{ color:#ff8fa3; }
/* week in review (Home) */
.kx.wr{ grid-template-columns:repeat(var(--wr-cols,4),1fr); border-radius:12px; border-top:1px solid var(--kl); overflow:hidden; }
.kx.wr b{ font-size:22px; }
.kx.wr-bench{ margin-top:12px; background:var(--kink); border:1px solid var(--kl); border-radius:12px; padding:12px 14px; }
.kx .wr-b{ display:grid; grid-template-columns:34px 80px 1fr 52px; gap:10px; align-items:center; padding:5px 0; }
.kx .wr-b b{ font-family:'Archivo',sans-serif; font-weight:600; font-size:14px; }
.kx .wr-bar{ height:7px; background:rgba(255,255,255,.06); border-radius:4px; overflow:hidden; }
.kx .wr-bar i{ display:block; height:100%; background:linear-gradient(90deg,var(--kr2),var(--kg)); }
/* manager faces + the Around-the-League ladder (ported with Game of the Week) */
i.mf.mf{ width:34px; height:34px; border-radius:50%; overflow:hidden; flex:none; display:inline-flex; align-items:center;
  justify-content:center; background:var(--panel2); border:2px solid var(--kr); font-style:normal; opacity:1;
  font-family:var(--font-display); font-weight:700; font-size:12px; color:var(--muted); line-height:1; }
i.mf.mf img{ width:100%; height:100%; object-fit:cover; display:block; }
i.mf.mchip{ padding:0;  width:24px; height:24px; border:none; font-size:9px; color:#111; background:#fff; }
i.mf.mm-mf{ width:52px; height:52px; }
i.mf.lead{ border-color:var(--kg); box-shadow:0 0 0 2px rgba(87,142,213,.28); }
i.mf.last{ border-color:rgba(255,143,163,.55); }
.kx .mm.me .mm-s.a i.mf{ border-color:var(--kg); }
td.two .tw{ display:flex; align-items:center; gap:10px; min-width:0; } td.two .tw > div{ min-width:0; }
.kx.gw-ladder{ display:flex; flex-direction:column; gap:8px; }
.kx .gw-lr{ display:grid; grid-template-columns:minmax(0,1fr) 220px minmax(0,1fr) 150px; gap:14px; align-items:center;
  background:var(--kink); border:1px solid var(--kl); border-radius:12px; padding:10px 14px; }
.kx .gw-lr.hot{ border-color:var(--kg); box-shadow:0 0 0 1px var(--kg) inset, 0 8px 30px rgba(87,142,213,.12);
  background:linear-gradient(90deg,rgba(87,142,213,.1),transparent 40%,transparent 60%,rgba(87,142,213,.1)),var(--kink); }
.kx .gw-lt{ display:flex; align-items:center; gap:10px; min-width:0; } .kx .gw-lt.r{ justify-content:flex-end; text-align:right; }
.kx .gw-lt > div{ min-width:0; } .kx .gw-lt b{ display:block; font-size:13.5px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.kx .gw-lt b.w{ color:var(--teal); }
[data-testid="stMarkdownContainer"] .kx .gw-lt span{ display:block; font-size:11px; color:var(--muted) !important; }
.kx .gw-mid{ text-align:center; min-width:0; }
.kx .gw-sc{ display:flex; justify-content:center; align-items:baseline; gap:8px; }
.kx .gw-sc b{ font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:22px; } .kx .gw-sc i{ font-style:normal; color:var(--muted); }
[data-testid="stMarkdownContainer"] .kx .gw-mid > span{ display:block; font-size:10.5px; color:var(--muted) !important; margin-top:2px; }
.kx .gw-meter{ height:6px; border-radius:5px; background:rgba(255,255,255,.08); overflow:hidden; margin-top:6px; }
.kx .gw-meter i{ display:block; height:100%; background:linear-gradient(90deg,var(--kr2),var(--kg)); }
.kx .gw-tag{ display:inline-block; margin-top:4px; font-style:normal; font-size:9px; font-weight:700; letter-spacing:.12em; text-transform:uppercase;
  background:var(--kg); color:#06101c; padding:2px 7px; border-radius:999px; }
[data-testid="stMarkdownContainer"] .kx .gw-root{ font-size:12px; color:var(--muted) !important; text-align:right; } .kx .gw-root b{ color:var(--kg); }
[data-testid="stMarkdownContainer"] .kx .gw-root.you{ color:var(--teal) !important; }
@media (max-width:760px){
  /* Game of the Week on a phone (ported from Kreeper): the two halves sit
     side by side with the stakes number on its own row underneath, rather
     than squeezing a 280px middle column between two 40px halves */
  .kx.gw{ grid-template-columns:1fr 1fr; min-height:0; }
  .kx .gw-m{ grid-column:1 / -1; grid-row:2; padding:10px 0 14px; } .kx .gw-m b{ font-size:56px; }
  /* a phone half is ~170px: the old poster look (face from the outer edge),
     but the face only fills the top of the half and fades out, and the name
     and odds sit below it, so no text lands on a face */
  .kx .gw-s{ min-height:196px; align-items:flex-end; padding:0 10px 10px; }
  .kx .gw-s .gw-ph{ top:0; bottom:auto; height:118px; max-width:none; opacity:.9;
    -webkit-mask-image:linear-gradient(to top,transparent 0,#000 35%); mask-image:linear-gradient(to top,transparent 0,#000 35%); }
  .kx .gw-t b{ font-size:34px; } .kx .gw-t i{ font-size:11px; line-height:1.35; }
  [data-testid="stMarkdownContainer"] .kx .gw-t span{ font-size:9px; letter-spacing:.1em; white-space:normal; }
  .kx .gw-tp{ grid-template-columns:minmax(0,1fr) 44px 44px minmax(0,1fr); row-gap:6px; } .kx .gw-e{ grid-column:1 / -1; order:5; }
  .kx .gw-n{ white-space:normal; } [data-testid="stMarkdownContainer"] .kx .gw-n span{ display:block; margin:0; }
  .kx .gw-rd{ grid-template-columns:34px 1fr 80px; } .kx .gw-tr{ grid-column:1 / -1; order:5; }
  .kx .gw-lr{ grid-template-columns:minmax(0,1fr) minmax(0,1fr); row-gap:8px; } .kx .gw-mid{ grid-column:1 / -1; grid-row:2; }
  [data-testid="stMarkdownContainer"] .kx .gw-root{ grid-column:1 / -1; text-align:center; }
}
/* Superlatives (app.render_superlatives): the award, the face, the line */
.kx.sups{ display:grid; grid-template-columns:repeat(auto-fill,minmax(270px,1fr)); gap:10px; }
.kx .sup{ display:flex; align-items:center; gap:12px; background:var(--kink); border:1px solid var(--kl);
  border-left:4px solid var(--kg); border-radius:12px; padding:11px 14px; min-width:0; }
.kx .sup.bad{ border-left-color:var(--bad); }
.kx .sup > div{ min-width:0; }
[data-testid="stMarkdownContainer"] .kx .sup span{ display:block; font-family:'Archivo',sans-serif; font-size:9.5px;
  letter-spacing:.14em; text-transform:uppercase; color:var(--kg) !important; }
.kx .sup.bad span{ color:var(--bad) !important; }
.kx .sup > div b{ display:block; font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:23px;
  line-height:1.05; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.kx .sup > div i{ display:block; font-style:normal; font-size:12px; color:var(--muted);
  overflow:hidden; text-overflow:ellipsis; }
@media (max-width:760px){ .kx.sups{ grid-template-columns:1fr; } }
/* Managers (trading cards), the champions strip, and trade cards -
   ported with the Kreeper League's League pages. */
.kx.mcards{ display:grid; grid-template-columns:repeat(auto-fill,minmax(190px,1fr)); gap:16px; }
.kx .mcard{ perspective:900px; height:326px; cursor:pointer; outline:none; }
.kx .mcard:focus-visible .mc-f, .kx .mcard:focus-visible .mc-b{ box-shadow:0 0 0 2px var(--kg); }
.kx .mc-in{ position:relative; width:100%; height:100%; transform-style:preserve-3d; transition:transform .75s cubic-bezier(.3,1.3,.4,1); }
.kx .mcard.on .mc-in{ transform:rotateY(180deg); }
@media (hover:hover){ .kx .mcard:hover:not(.on) .mc-in{ transform:rotateY(-12deg) rotateX(6deg); } }
.kx .mc-f, .kx .mc-b{ position:absolute; inset:0; border-radius:14px; overflow:hidden; backface-visibility:hidden; -webkit-backface-visibility:hidden;
  border:1px solid rgba(87,142,213,.45); background:var(--kink); }
.kx .mcard.me .mc-f, .kx .mcard.me .mc-b{ border-color:var(--kg); box-shadow:0 0 0 1px var(--kg); }
.kx .mc-f img{ display:block; width:100%; height:72%; object-fit:cover !important; }
.kx .mc-ini{ display:flex; align-items:center; justify-content:center; height:72%; font-family:'Archivo',sans-serif; font-style:normal; font-weight:700;
  font-size:56px; color:rgba(255,255,255,.75); background:linear-gradient(160deg,#1f4e9c,#0c1a33); }
.kx .mc-rk{ position:absolute; top:8px; left:8px; font-family:'Archivo',sans-serif; font-style:normal; font-weight:700; font-size:13px;
  color:#14110a; background:var(--kg); padding:2px 8px; border-radius:6px; }
.kx .mc-ft{ padding:10px 12px; border-top:3px solid var(--kg); }
.kx .mc-ft b{ display:block; font-family:'Archivo',sans-serif; font-weight:600; font-size:16px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.kx .mc-ft small{ font-size:11px; color:var(--muted); }
.kx .mc-b{ transform:rotateY(180deg); padding:13px; overflow:hidden; display:flex; flex-direction:column; gap:7px; background:linear-gradient(160deg,#2a0a14,#120307); }
.kx .mc-h, .kx .mc-row{ flex:none; }
.kx .mc-h{ font-family:'Archivo',sans-serif; font-weight:600; font-size:17px; text-transform:uppercase; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.kx .mc-row{ display:flex; justify-content:space-between; align-items:baseline; gap:8px; border-bottom:1px solid rgba(255,255,255,.12); padding-bottom:5px; }
.kx .mc-row small{ font-size:12px; color:#f0d7de; } .kx .mc-row b{ font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:16px; color:var(--kg); text-align:right; }
.kx .mc-note{ margin-top:auto; font-size:11px; color:#e0bcc6; }
@media (max-width:760px){ .kx.mcards{ grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; } .kx .mcard{ height:250px; }
  .kx .mc-row b{ font-size:14px; } .kx .mc-row small{ font-size:11px; } }
.kx .tc{ background:var(--panel); border:1px solid var(--line2); border-left:4px solid var(--kg); border-radius:12px; padding:12px 14px; margin-bottom:10px; }
.kx .tc-h{ display:flex; align-items:baseline; gap:8px; flex-wrap:wrap; } .kx .tc-h b{ font-family:'Archivo',sans-serif; font-weight:500; font-size:16px; }
[data-testid="stMarkdownContainer"] .kx .tc-h span{ font-size:11px; color:var(--dim) !important; }
.kx .tc-h em{ margin-left:auto; font-style:normal; font-family:'Archivo',sans-serif; font-size:10.5px; color:var(--dim); }
.kx .tc-c{ display:grid; grid-template-columns:1fr 40px 1fr; gap:10px; align-items:start; margin-top:10px; }
.kx .tc-x{ text-align:center; font-size:20px; color:var(--kg); padding-top:22px; }
[data-testid="stMarkdownContainer"] .kx .tl{ display:block; font-family:'Archivo',sans-serif; font-size:9.5px; letter-spacing:.12em; color:var(--dim) !important; margin-bottom:6px; text-transform:uppercase; }
[data-testid="stMarkdownContainer"] .kx .ktp{ display:inline-flex; align-items:center; gap:7px; background:var(--bg2); border:1px solid var(--line2); border-radius:999px;
  padding:3px 10px 3px 3px; margin:0 6px 6px 0; font-size:12.5px; font-weight:600; color:var(--ink) !important; }
.kx .ktp-f{ width:28px; height:28px; border-radius:50%; object-fit:cover !important; object-position:top !important; filter:grayscale(1); background:var(--panel2); }
[data-testid="stMarkdownContainer"] .kx .ktp.pk{ padding:5px 12px; color:var(--kg) !important; border-color:rgba(87,142,213,.45); font-family:'Archivo',sans-serif; font-size:11.5px; }
.kx .mk{ display:grid; grid-template-columns:34px minmax(0,1.3fr) 1fr 50px; gap:10px; align-items:center; padding:7px 0; border-bottom:1px solid #1d1d22; }
.kx.chs{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:10px; margin:0 0 16px; }
.kx .ch{ background:var(--bg2); border:1px solid var(--line2); border-radius:12px; padding:12px 14px; }
.kx .ch em{ display:block; font-style:normal; font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:40px; color:var(--kg); line-height:1; }
.kx .ch b{ display:block; font-family:'Playfair Display',serif; font-style:italic; font-size:19px; margin-top:4px; }
[data-testid="stMarkdownContainer"] .kx .ch span{ font-size:11.5px; color:var(--muted) !important; }
  .kx .tc-c{ grid-template-columns:1fr; } .kx .tc-x{ padding:0; }
  .kx .sp{ grid-template-columns:80px 1fr 40px; } .kx .sp span{ display:none; }
/* =====================================================================
   3D MOTION. Eleven pieces, mocked in design/anim3d.html and built here.
   1-4 are the Kreeper League's, ported; the rest exist because of rules
   only this league has. Every one of them stands still under
   prefers-reduced-motion (the block at the end).
   ===================================================================== */
/* 1. fight-night entrance - app._intro adds .in once per page load, so it
      plays when you arrive and never on Live's 30-second refresh */
.kx.gw.in .gw-s.l, .kx.xb.in .xb-s.me{ animation:kx-inL .9s cubic-bezier(.2,.9,.2,1) both; }
.kx.gw.in .gw-s.r, .kx.xb.in .xb-s.op{ animation:kx-inR .9s cubic-bezier(.2,.9,.2,1) both; }
[data-testid="stMarkdownContainer"] .kx.gw.in .gw-vs, [data-testid="stMarkdownContainer"] .kx.xb.in .xb-vs{
  animation:kx-vs 1s .5s cubic-bezier(.3,1.6,.4,1) backwards; }
.kx.gw.in .gw-m b, .kx.gw.in .gw-m em, .kx.xb.in .xb-m b, .kx.xb.in .xb-m em{ animation:kx-up .6s .9s ease-out both; }
.kx.gw.in, .kx.xb.in{ animation:kx-shake .35s 1s ease-out; }
@keyframes kx-inL{ from{ transform:perspective(900px) translateX(-55%) translateZ(-260px) rotateY(32deg); opacity:0; } to{ transform:none; opacity:1; } }
@keyframes kx-inR{ from{ transform:perspective(900px) translateX(55%) translateZ(-260px) rotateY(-32deg); opacity:0; } to{ transform:none; opacity:1; } }
@keyframes kx-vs{ 0%{ transform:perspective(400px) scale(3) rotateY(540deg) skewX(-8deg); opacity:0; } 70%{ opacity:1; }
  100%{ transform:perspective(400px) scale(1) rotateY(0) skewX(-8deg); } }
@keyframes kx-up{ from{ transform:translateY(14px); opacity:0; } to{ transform:none; opacity:1; } }
@keyframes kx-shake{ 0%,100%{ translate:0; } 25%{ translate:-5px 0; } 50%{ translate:4px 0; } 75%{ translate:-2px 0; } }

/* 2. tilt + shine - the covers and the award cards lean toward the pointer
      and a blue glint follows it (pointer handler in app._NAV_JS) */
.kx.gw, .kx.xb, .kx .sup{ position:relative; transition:transform .15s ease-out; }
.kx.gw::after, .kx.xb::after, .kx .sup::after{ content:""; position:absolute; inset:0; z-index:4; pointer-events:none; mix-blend-mode:screen;
  border-radius:inherit; background:linear-gradient(105deg,transparent 35%,rgba(160,200,255,.2) 48%,transparent 60%); background-size:250% 100%;
  background-position:var(--sx,130%) 0; transition:background-position .15s ease-out; }

/* 3. split-flap scores on Live (app._flap): only the digits that changed flip */
[data-testid="stMarkdownContainer"] .kx .fl{ display:inline-flex !important; gap:.05em; vertical-align:top; font-size:inherit !important; letter-spacing:0 !important;
  color:inherit !important; text-transform:none !important; overflow:visible !important; }
[data-testid="stMarkdownContainer"] .kx .fl span{ display:block !important; font-size:inherit !important; letter-spacing:0 !important; color:inherit !important;
  text-transform:none !important; white-space:nowrap; }
[data-testid="stMarkdownContainer"] .kx .fl span.fd{ position:relative; display:inline-block !important; width:.6em; height:1.08em; line-height:1.08em; text-align:center;
  overflow:visible !important; perspective:3em; }
[data-testid="stMarkdownContainer"] .kx .fl span.fd.pt{ width:.26em; }
.kx .fd.s{ background:#1c1a1b linear-gradient(transparent calc(50% - .5px),#000 calc(50% - .5px),#000 calc(50% + .5px),transparent calc(50% + .5px)); border-radius:.08em; }
.kx .fd.pt.s{ background:none; }
[data-testid="stMarkdownContainer"] .kx .fd > span{ position:absolute !important; left:0; right:0; height:50%; overflow:hidden !important; background:#1c1a1b; }
[data-testid="stMarkdownContainer"] .kx .fd > span > span{ position:absolute; left:0; right:0; height:1.08em; }
[data-testid="stMarkdownContainer"] .kx .fd .t, [data-testid="stMarkdownContainer"] .kx .fd .ft{ top:0; border-radius:.08em .08em 0 0; }
[data-testid="stMarkdownContainer"] .kx .fd .t > span, [data-testid="stMarkdownContainer"] .kx .fd .ft > span{ top:0; }
[data-testid="stMarkdownContainer"] .kx .fd .b, [data-testid="stMarkdownContainer"] .kx .fd .fb{ bottom:0; border-radius:0 0 .08em .08em; }
[data-testid="stMarkdownContainer"] .kx .fd .b > span, [data-testid="stMarkdownContainer"] .kx .fd .fb > span{ bottom:0; }
[data-testid="stMarkdownContainer"] .kx .fd .t{ border-bottom:1px solid #000; }
[data-testid="stMarkdownContainer"] .kx .fd .ft{ z-index:2; transform-origin:bottom; backface-visibility:hidden; animation:kx-ft .3s ease-in forwards; }
[data-testid="stMarkdownContainer"] .kx .fd .fb{ z-index:2; transform-origin:top; transform:rotateX(90deg); animation:kx-fb .3s .3s ease-out forwards; }
@keyframes kx-ft{ to{ transform:rotateX(-90deg); } } @keyframes kx-fb{ to{ transform:rotateX(0); } }
.kx .mm.me .mm-s.a .fd.s, [data-testid="stMarkdownContainer"] .kx .mm.me .mm-s.a .fd > span{ background-color:#7a0424; }
.kx .fl-d{ display:inline-block; vertical-align:top; margin-left:6px; font-family:'Archivo',sans-serif; font-style:normal; font-size:12px; font-weight:700;
  color:var(--teal); animation:kx-gain 2.4s ease-out both; }
@keyframes kx-gain{ 0%{ opacity:0; transform:translateY(6px); } 15%,70%{ opacity:1; transform:none; } 100%{ opacity:0; } }

/* 4. contract flip - Home's best contracts: the price on the front, the
      three-year ladder on the back. Hover leans it, tap turns it. */
.kx.kflips{ display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:12px; }
.kx .kflip{ perspective:1000px; height:178px; cursor:pointer; outline:none; }
.kx .kf-in{ position:relative; width:100%; height:100%; transform-style:preserve-3d; transition:transform .72s cubic-bezier(.3,1.3,.4,1); }
.kx .kflip.on .kf-in{ transform:rotateY(180deg); }
@media (hover:hover){ .kx .kflip:hover:not(.on) .kf-in{ transform:rotateY(-13deg) rotateX(7deg); } }
.kx .kflip:focus-visible .kf-f, .kx .kflip:focus-visible .kf-b{ box-shadow:0 0 0 2px var(--kg); }
.kx .kf-f, .kx .kf-b{ position:absolute; inset:0; backface-visibility:hidden; -webkit-backface-visibility:hidden; border-radius:12px;
  border:1px solid var(--kl); padding:12px 13px; display:flex; flex-direction:column; overflow:hidden; }
.kx .kf-f{ background:var(--kink); }
.kx .kflip.me .kf-f, .kx .kflip.me .kf-b{ border-color:var(--kg); }
.kx .kf-b{ transform:rotateY(180deg); background:linear-gradient(160deg,#2a0a14,#120307); gap:4px; }
.kx .kf-top{ display:flex; gap:10px; align-items:center; min-width:0; }
.kx .kf-top img{ width:42px; height:42px; border-radius:50%; object-fit:cover !important; object-position:top !important; background:var(--panel2); flex:none; }
.kx .kf-top > div{ min-width:0; }
.kx .kf-top b{ display:block; font-family:'Big Shoulders Display',sans-serif; font-weight:800; font-size:18px; line-height:1.05; text-transform:uppercase;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
[data-testid="stMarkdownContainer"] .kx .kf-top span{ display:block; font-size:11px; color:var(--muted) !important; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.kx .kf-own{ display:flex; align-items:center; gap:6px; margin-top:auto; font-size:11px; color:var(--muted); }
.kx .kf-own i.mf.mf{ width:20px; height:20px; border-width:1px; font-size:8px; }
.kx .kf-px{ display:flex; align-items:baseline; gap:10px; margin-top:8px; }
.kx .kf-px b{ font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:42px; line-height:1; color:var(--kr2); }
.kx .kf-px em{ font-style:normal; font-size:12px; color:var(--muted); }
.kx .kf-px em.p{ color:var(--teal); } .kx .kf-px em.n{ color:var(--bad); }
[data-testid="stMarkdownContainer"] .kx .kf-b > span{ font-size:9.5px; letter-spacing:.14em; text-transform:uppercase; color:#f0d7de !important; }
.kx .kf-st{ display:flex; justify-content:space-between; gap:8px; font-size:12px; color:#f0d7de; border-bottom:1px solid rgba(255,255,255,.1); padding:3px 0; }
.kx .kf-st b{ font-family:'Big Shoulders Display',sans-serif; font-weight:800; font-size:15px; color:var(--kg); }
.kx .kf-st.wall, .kx .kf-st.wall b{ color:var(--bad); }

/* 5. the skyline - last week's eight scores as solids, each manager on top
      of his own tower (Week in Review) */
.kx.sky{ display:flex; align-items:flex-end; justify-content:space-between; gap:8px; height:230px; padding:62px 10px 26px;
  perspective:900px; background:var(--kink); border:1px solid var(--kl); border-radius:12px; margin:0 0 12px; overflow:hidden; }
.kx .sky-t{ position:relative; flex:1; max-width:70px; transform-style:preserve-3d; transform:rotateX(12deg) rotateY(-16deg); }
.kx .sky-s{ position:relative; width:100%; height:0; border-radius:3px 3px 0 0;
  background:linear-gradient(180deg,var(--c),color-mix(in srgb,var(--c) 52%,black));
  box-shadow:12px 0 0 -2px color-mix(in srgb,var(--c) 38%,black); animation:kx-grow 1.3s cubic-bezier(.2,.9,.3,1) var(--dl,0s) forwards; }
.kx .sky-t i.mf.mf{ position:absolute; left:50%; top:-60px; margin-left:-17px; border-color:var(--c); }
.kx .sky-t b{ position:absolute; top:-24px; left:-10px; right:-10px; text-align:center; font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:17px; }
[data-testid="stMarkdownContainer"] .kx .sky-t span{ position:absolute; bottom:-22px; left:-10px; right:-10px; text-align:center; font-size:10.5px; color:var(--muted) !important; }
@keyframes kx-grow{ to{ height:var(--h); } }

/* 6. the two drums - a glass globe on a stand per drum. The balls are the
      managers' faces, sized by their weight, at real 3D positions; the
      cluster turns while each ball counter-turns to keep its face out, and
      the cage turns the other way. */
.kx.drums{ display:flex; gap:28px; justify-content:center; flex-wrap:wrap; margin:6px 0 4px; }
.kx .drum{ position:relative; width:200px; height:244px; }
.kx .drum .glb{ position:absolute; left:0; top:0; width:200px; height:200px; perspective:560px; }
.kx .drum .glass{ position:absolute; inset:0; border-radius:50%; z-index:3; pointer-events:none;
  background:radial-gradient(circle at 31% 24%,rgba(255,255,255,.34),rgba(255,255,255,.06) 18%,transparent 32%),
             radial-gradient(circle at 70% 82%,rgba(255,255,255,.08),transparent 26%),
             radial-gradient(circle at 50% 50%,transparent 58%,rgba(0,0,0,.5) 100%);
  box-shadow:inset 0 0 0 2px rgba(255,255,255,.12), inset 0 0 28px var(--tint,rgba(87,142,213,.2)); }
.kx .drum .back{ position:absolute; inset:0; border-radius:50%; z-index:0; background:radial-gradient(circle at 50% 62%,var(--tint,rgba(87,142,213,.2)) 0,rgba(10,9,10,.92) 66%); }
.kx .drum .cage{ position:absolute; inset:0; z-index:2; transform-style:preserve-3d; animation:kx-cage 14s linear infinite reverse; }
.kx .drum .cage i{ position:absolute; inset:0; border-radius:50%; border:1px solid rgba(255,255,255,.16); }
.kx .drum .cage i:nth-child(2){ transform:rotateY(60deg); } .kx .drum .cage i:nth-child(3){ transform:rotateY(120deg); }
.kx .drum .cage i:nth-child(4){ transform:rotateX(90deg); border-color:rgba(255,255,255,.22); }
.kx .drum .spin{ position:absolute; left:50%; top:50%; z-index:1; transform-style:preserve-3d; animation:kx-turn 9s linear infinite; }
.kx .drum .ball{ position:absolute; transform-style:preserve-3d; }
.kx .drum .fc3{ width:var(--d,32px); height:var(--d,32px); margin:calc(var(--d,32px) / -2) 0 0 calc(var(--d,32px) / -2); animation:kx-face 9s linear infinite; }
.kx .drum .bob{ width:100%; height:100%; animation:kx-bob var(--bt,1.6s) ease-in-out var(--bd,0s) infinite alternate; }
.kx .drum .orb{ position:relative; width:100%; height:100%; border-radius:50%; overflow:hidden;
  box-shadow:0 0 0 2px var(--bc,var(--kg)), 0 6px 10px -4px rgba(0,0,0,.7); background:var(--panel2); }
.kx .drum .orb.out{ filter:grayscale(1) brightness(.55); }
.kx .drum .orb img{ width:100%; height:100%; object-fit:cover !important; object-position:center 30% !important; display:block; }
.kx .drum .orb em{ position:absolute; inset:0; display:flex; align-items:center; justify-content:center; font-style:normal;
  font-family:'Big Shoulders Display',sans-serif; font-weight:800; font-size:calc(var(--d,32px) * .42); color:var(--muted); }
.kx .drum .orb::after{ content:""; position:absolute; inset:0; border-radius:50%;
  background:radial-gradient(circle at 34% 28%,rgba(255,255,255,.55),rgba(255,255,255,.1) 22%,transparent 40%),
             radial-gradient(circle at 50% 50%,transparent 52%,rgba(0,0,0,.62) 100%); }
.kx .drum .axle{ position:absolute; left:50%; top:50%; width:12px; height:12px; margin:-6px; border-radius:50%; z-index:4;
  background:radial-gradient(circle at 35% 30%,#fff,#8a8486 55%,#2b2729); box-shadow:0 0 0 2px rgba(0,0,0,.4); }
.kx .drum .stand{ position:absolute; left:50%; top:190px; width:80px; height:36px; margin-left:-40px;
  background:linear-gradient(180deg,#3a3537,#1b1819); clip-path:polygon(32% 0,68% 0,100% 100%,0 100%); }
.kx .drum .floor{ position:absolute; left:50%; top:222px; width:150px; height:18px; margin-left:-75px; border-radius:50%;
  background:radial-gradient(ellipse at center,rgba(0,0,0,.65),transparent 70%); }
[data-testid="stMarkdownContainer"] .kx .drum-l{ display:block; text-align:center; font-size:10.5px; letter-spacing:.12em; text-transform:uppercase; color:var(--muted) !important; }
@keyframes kx-turn{ from{ transform:rotateX(-14deg) rotateY(0); } to{ transform:rotateX(-14deg) rotateY(360deg); } }
@keyframes kx-face{ from{ transform:rotateY(0) rotateX(14deg); } to{ transform:rotateY(-360deg) rotateX(14deg); } }
@keyframes kx-cage{ from{ transform:rotateX(-14deg) rotateY(0); } to{ transform:rotateX(-14deg) rotateY(360deg); } }
@keyframes kx-bob{ from{ transform:translateY(-5px); } to{ transform:translateY(5px); } }

/* 7. the pot as a vessel - every spender's coin drops in, biggest first;
      it fills to the Chase cap and anything over runs off the side */
.kx.vbox{ display:flex; align-items:center; justify-content:center; gap:28px; background:var(--kink); border:1px solid var(--kl);
  border-radius:12px; padding:22px 16px; margin:0 0 14px; flex-wrap:wrap; }
.kx .coins{ display:flex; flex-direction:column-reverse; gap:5px; min-width:120px; }
.kx .coin{ display:flex; align-items:center; gap:8px; font-size:12px; color:var(--muted); opacity:0; animation:kx-coin .45s var(--dl,0s) forwards; }
.kx .coin b{ font-family:'Big Shoulders Display',sans-serif; font-weight:800; font-size:16px; color:var(--ink); }
.kx .coin i.mf.mf{ width:26px; height:26px; border-color:var(--kr2); }
@keyframes kx-coin{ from{ opacity:0; transform:translateX(-14px) rotateY(80deg); } to{ opacity:1; transform:none; } }
.kx .vessel{ position:relative; width:130px; height:190px; perspective:640px; flex:none; }
.kx .vs-in{ position:absolute; inset:0; transform:rotateX(9deg); transform-style:preserve-3d; }
.kx .glassv{ position:absolute; inset:0; border:2px solid var(--line2); border-radius:9px 9px 30px 30px; overflow:hidden;
  background:linear-gradient(100deg,rgba(255,255,255,.06),transparent 42%); }
.kx .fillv{ position:absolute; left:0; right:0; bottom:0; height:0; background:linear-gradient(180deg,var(--kr2),#8a0427);
  animation:kx-fill 2.4s cubic-bezier(.3,.8,.4,1) forwards; }
.kx .fillv::before{ content:""; position:absolute; top:-7px; left:-50%; width:200%; height:14px; border-radius:50%; background:var(--kr2);
  opacity:.85; animation:kx-slosh 3.1s ease-in-out infinite; }
@keyframes kx-fill{ to{ height:var(--lvl,0%); } }
@keyframes kx-slosh{ 0%,100%{ transform:translateX(-6px) rotate(-1.2deg); } 50%{ transform:translateX(6px) rotate(1.2deg); } }
.kx .capv{ position:absolute; left:-8px; right:-8px; border-top:2px dashed var(--teal); z-index:3; }
[data-testid="stMarkdownContainer"] .kx .capv span{ position:absolute; left:calc(100% + 6px); top:-9px; font-size:10.5px; letter-spacing:.06em;
  color:var(--teal) !important; white-space:nowrap; }
.kx .spill{ position:absolute; top:-2px; right:-15px; width:13px; height:0; background:var(--kg); border-radius:0 0 6px 6px; opacity:.9;
  animation:kx-spill 1.3s 2.2s ease-in forwards; }
@keyframes kx-spill{ to{ height:var(--sp,0px); } }
.kx .vnote{ max-width:240px; font-size:12.5px; color:var(--muted); line-height:1.5; }
.kx .vnote b{ display:block; font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:40px; line-height:1; color:var(--ink); }

/* 8. the taxi carousel - your two slots on a turntable; tap to turn it */
.kx.txc{ display:flex; align-items:center; gap:18px; flex-wrap:wrap; margin:0 0 6px; }
.kx .txc-stage{ perspective:1000px; width:280px; height:170px; cursor:pointer; outline:none; }
.kx .txc-in{ position:relative; width:100%; height:100%; transform-style:preserve-3d; transform:translateZ(-140px) rotateY(calc(var(--turn,0) * -180deg));
  transition:transform .7s cubic-bezier(.3,1.2,.4,1); }
.kx .txc-p{ position:absolute; inset:0; border-radius:12px; border:1px solid var(--kl); background:var(--kink); padding:14px; display:flex; flex-direction:column; gap:4px;
  backface-visibility:hidden; -webkit-backface-visibility:hidden; }
.kx .txc-p:nth-child(1){ transform:rotateY(0) translateZ(140px); } .kx .txc-p:nth-child(2){ transform:rotateY(180deg) translateZ(140px); }
.kx .txc-p.last{ border-color:var(--amber); }
.kx .txc-p.empty{ border-style:dashed; }
.kx .txc-p img{ position:absolute; right:12px; top:12px; width:52px; height:52px; border-radius:50%; object-fit:cover !important; object-position:top !important;
  background:var(--panel2); }
[data-testid="stMarkdownContainer"] .kx .txc-p i{ font-style:normal; font-size:10px; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); }
.kx .txc-p b{ font-family:'Big Shoulders Display',sans-serif; font-weight:800; font-size:24px; line-height:1.05; text-transform:uppercase; padding-right:62px; }
[data-testid="stMarkdownContainer"] .kx .txc-p span{ margin-top:auto; font-size:12px; color:var(--muted) !important; }
.kx .txc-p.last span{ color:var(--amber) !important; }
.kx .pips{ display:flex; gap:5px; margin-top:4px; } .kx .pips u{ width:30px; height:5px; border-radius:3px; background:var(--kl); text-decoration:none; }
.kx .pips u.on{ background:var(--teal); } .kx .pips u.now{ background:var(--amber); }
.kx .txc-n{ font-size:12px; color:var(--muted); max-width:300px; }

/* 9. the franchise stamp - one tag, once: it presses down the Z axis */
.frs{ position:relative; } .contract.frs{ padding-right:128px; }
.frs .stamp{ position:absolute; right:18px; top:50%; width:96px; height:96px; margin-top:-48px; border:4px solid var(--acc); border-radius:50%;
  display:flex; flex-direction:column; align-items:center; justify-content:center; color:var(--acc); text-transform:uppercase; pointer-events:none;
  font-family:'Big Shoulders Display',sans-serif; font-weight:900; transform:rotate(-15deg); opacity:.95; z-index:2;
  animation:kx-press .62s .4s cubic-bezier(.3,1.5,.5,1) backwards; }
.frs .stamp b{ font-size:21px; line-height:.95; } [data-testid="stMarkdownContainer"] .frs .stamp span{ font-size:10px; letter-spacing:.12em; color:var(--acc) !important; }
.frs.go{ animation:kx-shake .34s .85s ease-out; }
@keyframes kx-press{ 0%{ opacity:0; transform:perspective(600px) translateZ(300px) rotate(-38deg) scale(2.3); }
  65%{ opacity:1; transform:perspective(600px) translateZ(0) rotate(-15deg) scale(.93); }
  100%{ opacity:.95; transform:perspective(600px) translateZ(0) rotate(-15deg) scale(1); } }

/* 10. the Chase, lit - both brackets on one tilted plane, seats dropping in
       off the Z axis; the four playing for the pot are the ones that glow */
.kx.brk{ display:grid; grid-template-columns:1fr 1fr; gap:22px; perspective:1100px; padding:30px 18px 18px; background:var(--kink);
  border:1px solid var(--kl); border-radius:12px; margin:0 0 14px; }
.kx .brk-c{ transform-style:preserve-3d; transform:rotateX(14deg) rotateY(-9deg); display:flex; flex-direction:column; gap:7px; position:relative; }
.kx .brk-c:nth-child(2){ transform:rotateX(14deg) rotateY(9deg); }
[data-testid="stMarkdownContainer"] .kx .brk-c > span{ font-size:10px; letter-spacing:.14em; text-transform:uppercase; color:var(--teal) !important; margin-bottom:2px; }
[data-testid="stMarkdownContainer"] .kx .brk-c.cz > span{ color:var(--kr2) !important; }
.kx .seat{ display:flex; align-items:center; gap:9px; height:40px; padding:0 11px; border-radius:8px; border:1px solid var(--kl); background:#151314;
  animation:kx-seat .5s var(--dl,0s) backwards; }
.kx .seat.pot{ border-color:rgba(54,157,134,.55); background:rgba(54,157,134,.10); }
.kx .seat.chase{ border-color:var(--kr2); background:rgba(251,8,73,.12); box-shadow:0 0 18px rgba(251,8,73,.28); }
.kx .seat.me{ outline:2px solid var(--kg); outline-offset:1px; }
.kx .seat em{ font-style:normal; font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:18px; color:var(--muted); width:16px; }
.kx .seat b{ font-size:13.5px; font-weight:650; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; min-width:0; }
[data-testid="stMarkdownContainer"] .kx .seat span{ margin-left:auto; font-size:11.5px; color:var(--muted) !important; white-space:nowrap; }
.kx .seat i.mf.mf{ width:28px; height:28px; }
@keyframes kx-seat{ from{ opacity:0; transform:translateZ(-120px); } to{ opacity:1; transform:none; } }
@media (max-width:760px){
  .kx.brk{ grid-template-columns:1fr; } .kx .brk-c, .kx .brk-c:nth-child(2){ transform:rotateX(10deg); }
  .kx.sky{ gap:4px; padding:56px 4px 26px; } .kx .sky-t b{ font-size:13px; } .kx .sky-t i.mf.mf{ width:26px; height:26px; margin-left:-13px; top:-52px; }
  .kx .drum{ transform:scale(.82); transform-origin:top center; margin-bottom:-40px; }
}

@media (prefers-reduced-motion: reduce){
  .kx.gw.in *, .kx.xb.in *, .kx.gw.in, .kx.xb.in, .kx .fd .ft, .kx .fd .fb, .kx .fl-d,
  .kx .drum *, .kx .coin, .kx .fillv, .kx .fillv::before, .kx .spill, .kx .seat, .kx .sky-s, .frs, .frs .stamp{ animation:none !important; }
  [data-testid="stMarkdownContainer"] .kx .fd .ft{ display:none !important; } [data-testid="stMarkdownContainer"] .kx .fd .fb{ transform:none !important; }
  .kx .mc-in, .kx .kf-in, .kx .txc-in, .kx.gw, .kx.xb, .kx .sup{ transition:none !important; }
  .kx .coin{ opacity:1; } .kx .fillv{ height:var(--lvl,0%); } .kx .spill{ height:var(--sp,0px); } .kx .sky-s{ height:var(--h); }
}
/* the lineup as one list */
.kx.xl-wrap{ display:block; }
.kx .xl{ display:grid; grid-template-columns:42px 34px minmax(0,1fr) minmax(50px,140px) 64px 48px; gap:10px; align-items:center;
  padding:7px 6px; border-bottom:1px solid #221f20; }
.kx .xl.swap{ background:var(--kr); border-radius:10px; border:0; margin:3px 0; }
[data-testid="stMarkdownContainer"] .kx .xl-s{ font-family:'Archivo',sans-serif; font-size:10px; color:var(--dim) !important; }
.kx .xl-f{ width:34px; height:34px; border-radius:50%; object-fit:cover !important; object-position:top !important; background:var(--panel2); filter:grayscale(1); }
.kx .xl-n{ min-width:0; } .kx .xl-n b{ display:block; font-family:'Archivo',sans-serif; font-weight:700; font-size:15px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.kx .xl-n i{ display:block; font-style:normal; font-size:11px; color:var(--dim); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.kx .xl.swap .xl-n i{ color:#ffd0dc; }
.kx .xl-b{ height:9px; background:var(--panel2); border-radius:99px; overflow:hidden; }
.kx .xl-b i{ display:block; height:100%; background:linear-gradient(90deg,var(--kr),var(--kr2) 60%,var(--kg)); }
.kx .xl.swap .xl-b{ background:rgba(0,0,0,.3); } .kx .xl.swap .xl-b i{ background:var(--kg); }
.kx .xl-r{ text-align:center; }
.kx .xl-p{ font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:21px; text-align:right; color:var(--ink); }
/* standings as a ranked list */
.kx .sr{ display:grid; grid-template-columns:36px minmax(0,1.3fr) minmax(0,1.6fr) 56px; gap:10px; align-items:center; padding:8px 10px;
  border-bottom:1px solid #221f20; }
.kx .sr.me{ background:linear-gradient(90deg,rgba(251,8,73,.45),transparent 70%); border-radius:10px; }
.kx .sr-n{ font-family:'Big Shoulders Display',sans-serif; font-size:26px; color:var(--dim); } .kx .sr.me .sr-n{ color:var(--kg); }
.kx .sr-t{ min-width:0; } .kx .sr-t b{ display:block; font-family:'Archivo',sans-serif; font-weight:700; font-size:15px; }
[data-testid="stMarkdownContainer"] .kx .sr-t span{ font-size:11px; color:var(--dim) !important; }
.kx .sr-b{ position:relative; height:16px; background:var(--panel2); border-radius:4px; }
.kx .sr-b i{ position:absolute; left:0; top:0; bottom:0; background:#3a3436; border-radius:4px; } .kx .sr.me .sr-b i{ background:var(--kr2); }
.kx .sr-b em{ position:absolute; right:6px; top:1px; font-style:normal; font-family:'Archivo',sans-serif; font-size:10.5px; color:var(--ink); }
[data-testid="stMarkdownContainer"] .kx .sr-k{ font-family:'Archivo',sans-serif; font-size:11px; text-align:center; padding:3px 0; border-radius:6px;
  border:1px solid var(--kl); color:var(--dim) !important; }
[data-testid="stMarkdownContainer"] .kx .sr-k.w{ color:var(--kg) !important; border-color:rgba(87,142,213,.5); }
.kx .sr-cut{ border-top:2px solid var(--kg); margin:4px 0; padding-top:3px; }
[data-testid="stMarkdownContainer"] .kx .sr-cut span{ font-family:'Archivo',sans-serif; font-size:9.5px; letter-spacing:.12em; color:var(--kg) !important; }
/* the to-do list: quiet, the first that needs you on royal */
.todo{ --c:var(--muted); } .todo.bad{ --c:var(--kg); } .todo.good{ --c:var(--muted); }
.todo .tv b{ font-family:'Big Shoulders Display',sans-serif !important; font-weight:400; font-size:28px; color:var(--ink) !important; }
.todo.hot{ background:#c8063b !important; border-color:#c8063b !important; --c:#ffd0dc; }
[data-testid="stMarkdownContainer"] .todo.hot div > span{ color:#ffd0dc !important; }
/* the keeper tray: black-and-white portraits, gold rounds */
.ktray .kt{ background:#101011; border:0; border-radius:4px; padding:0 0 10px; overflow:hidden; box-shadow:inset 0 -3px 0 #fb0849; }
.ktray .kt i{ padding-top:8px; }
/* the thumbs are 350x254: keep that shape (capped) so a wide tile shows the face, not a crop of the forehead */
.ktray .kt .kh-img{ width:100%; height:auto; aspect-ratio:350 / 254; max-height:190px; border-radius:0; object-fit:cover; object-position:center top; filter:grayscale(1); margin:0 0 6px; }
.ktray .kt b{ font-family:'Playfair Display',serif; font-size:14.5px; }
.ktray .kt.empty{ box-shadow:none; }
@media (max-width:1100px){
  /* the hub's content column is narrow: the photo sits BEHIND the score */
  .kx.xb{ grid-template-columns:1fr 220px 1fr; }
  .kx .xb-s{ position:relative; min-height:176px; }
  .kx .xb-ph{ position:absolute; bottom:0; height:150px; margin:0; z-index:0; }
  .kx .xb-s.me .xb-ph{ left:-10px; } .kx .xb-s.op .xb-ph{ right:-10px; opacity:.45; }
  .kx .xb-t{ position:relative; z-index:1; } .kx .xb-s.me .xb-t{ text-align:right; }
  .kx .xb-t b{ font-size:60px; } .kx .xb-m b{ font-size:66px; }
}
@media (max-width:760px){
  .kx.bh.has-grid{ grid-template-columns:1fr; } .kx .bh-grid{ border-left:0; border-top:1px solid rgba(87,142,213,.25); }
  .kx .bh-n{ font-size:84px; } .kx .bh-l em{ font-size:18px; } .kx .bh-duo{ opacity:.5; }
  .kx.xb{ grid-template-columns:1fr 1fr; min-height:0; }
  .kx .xb-m{ grid-column:1 / -1; grid-row:2; flex-direction:row; flex-wrap:wrap; gap:4px 10px; padding:8px 12px; }
  .kx .xb-m b{ font-size:44px; } .kx .xb-bar{ width:100%; }
  .kx .xb-s{ position:relative; padding:10px 12px; min-height:118px; }
  .kx .xb-ph{ position:absolute; bottom:0; height:104px; margin:0; z-index:0; } .kx .xb-s.me .xb-ph{ left:-14px; } .kx .xb-s.op .xb-ph{ right:-14px; opacity:.4; }
  .kx .xb-t{ position:relative; z-index:1; } .kx .xb-s.me .xb-t{ text-align:right; } .kx .xb-t b{ font-size:44px; white-space:nowrap; }
  .kx.xb-tiles{ grid-template-columns:repeat(2,1fr); } .kx.xb-tiles b{ font-size:22px; }
  .kx .xl{ grid-template-columns:34px 30px minmax(0,1fr) 56px 40px; gap:6px; } .kx .xl-b{ display:none; }
  .kx .sr{ grid-template-columns:26px minmax(0,1fr) 90px 48px; gap:6px; }
}

/* ==== the rest of the in-season pages (Live, Trades, Playoffs, FAAB, Lottery, Record Book) */
.kx .mm{ display:grid; grid-template-columns:1fr 150px 1fr; border-radius:12px; overflow:hidden; margin-bottom:8px; min-height:84px; box-shadow:inset 0 0 0 1px #2a2a30; }
.kx .mm-s{ display:flex; align-items:center; gap:10px; padding:8px 14px; background:#101011; min-width:0; }
.kx .mm-s.b{ justify-content:flex-end; text-align:right; } .kx .mm.me .mm-s.a{ background:#c8063b; }
.kx .mm-s > div{ min-width:0; }
.kx .mm-f{ width:52px; height:52px; border-radius:50%; object-fit:cover !important; object-position:top !important; filter:grayscale(1); background:var(--panel2); flex:none; }
[data-testid="stMarkdownContainer"] .kx .mm-s span{ display:block; font-size:10px; letter-spacing:.12em; font-weight:700; color:var(--kg) !important;
  text-transform:uppercase; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
[data-testid="stMarkdownContainer"] .kx .mm.me .mm-s.a span{ color:#ffd0dc !important; }
.kx .mm-s b{ display:block; font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:34px; line-height:1; color:var(--ink); }
.kx .mm-s i{ font-style:normal; font-size:11px; color:var(--muted); } .kx .mm.me .mm-s.a i{ color:#ffd0dc; }
.kx .mm-m{ background:#08080a; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:4px; }
.kx .mm-m b{ font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:32px; color:var(--kg); line-height:1; } .kx .mm-m sup{ font-size:13px; }
.kx .mm-bar{ width:70%; height:4px; background:#2a2a30; border-radius:9px; overflow:hidden; } .kx .mm-bar i{ display:block; height:100%; background:linear-gradient(90deg,#fb0849,#578ed5); }
.kx .khs{ display:grid; grid-template-columns:40px minmax(0,1fr) 48px 150px 48px minmax(0,1fr); gap:8px; align-items:center; padding:6px 0; border-bottom:1px solid #221f20; }
.kx .hn{ font-size:13px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; } .kx .hn.r{ text-align:right; }
.kx .hp{ font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:20px; text-align:center; color:var(--dim); } .kx .hp.win{ color:var(--ink); }
.kx .hp.pj{ opacity:.75; } .kx .hp.zero{ color:var(--kg); }
.kx .he{ display:grid; grid-template-columns:1fr 46px 1fr; align-items:center; gap:4px; }
[data-testid="stMarkdownContainer"] .kx .he span{ font-family:'Archivo',sans-serif; font-size:11px; text-align:center; color:var(--muted) !important; }
.kx .hh{ height:8px; background:var(--panel2); border-radius:99px; display:flex; overflow:hidden; } .kx .hh.l{ justify-content:flex-end; }
.kx .hh.l i{ background:#fb0849; display:block; } .kx .hh.r i{ background:#4a4245; display:block; }
.kx .tc{ background:var(--panel); border:1px solid #2a2a30; border-left:4px solid var(--kg); border-radius:12px; padding:12px 14px; margin-bottom:10px; }
.kx .tc-h{ display:flex; align-items:baseline; gap:8px; flex-wrap:wrap; } .kx .tc-h b{ font-family:'Archivo',sans-serif; font-weight:700; font-size:16px; }
[data-testid="stMarkdownContainer"] .kx .tc-h span{ font-size:11px; color:var(--dim) !important; }
.kx .tc-h em{ margin-left:auto; font-style:normal; font-family:'Archivo',sans-serif; font-size:10.5px; color:var(--dim); }
.kx .tc-c{ display:grid; grid-template-columns:1fr 40px 1fr; gap:10px; align-items:start; margin-top:10px; }
.kx .tc-x{ text-align:center; font-size:20px; color:var(--kg); padding-top:22px; }
[data-testid="stMarkdownContainer"] .kx .tl{ display:block; font-family:'Archivo',sans-serif; font-size:9.5px; letter-spacing:.12em; color:var(--dim) !important; margin-bottom:6px; text-transform:uppercase; }
[data-testid="stMarkdownContainer"] .kx .ktp{ display:inline-flex; align-items:center; gap:7px; background:#101011; border:1px solid #2a2a30; border-radius:999px;
  padding:3px 10px 3px 3px; margin:0 6px 6px 0; font-size:12.5px; font-weight:600; color:var(--ink) !important; }
.kx .ktp-f{ width:28px; height:28px; border-radius:50%; object-fit:cover !important; object-position:top !important; filter:grayscale(1); background:var(--panel2); }
[data-testid="stMarkdownContainer"] .kx .ktp.pk{ padding:5px 12px; color:var(--kg) !important; border-color:rgba(87,142,213,.45); font-family:'Archivo',sans-serif; font-size:11.5px; }
.kx .mk{ display:grid; grid-template-columns:34px minmax(0,1.3fr) 1fr 50px; gap:10px; align-items:center; padding:7px 0; border-bottom:1px solid #221f20; }
.kx .mk-n b{ display:block; font-family:'Archivo',sans-serif; font-weight:700; font-size:15px; }
[data-testid="stMarkdownContainer"] .kx .mk-n span{ font-size:11px; color:var(--dim) !important; }
.kx .mk-b{ height:10px; background:var(--panel2); border-radius:99px; overflow:hidden; } .kx .mk-b i{ display:block; height:100%; background:linear-gradient(90deg,#c8063b,#578ed5); }
.kx .mk-b i.neg{ background:#4a4245; }
.kx .mk em{ font-style:normal; font-family:'Big Shoulders Display',sans-serif; font-size:22px; color:var(--kg); text-align:right; } .kx .mk em.neg{ color:var(--dim); }
.kx .sp{ display:grid; grid-template-columns:minmax(0,150px) 1fr 50px 130px; gap:10px; align-items:center; padding:7px 0; border-bottom:1px solid #221f20; }
.kx .sp b{ font-family:'Archivo',sans-serif; font-weight:700; font-size:15px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; } .kx .sp.me b{ color:var(--kg); }
.kx .sp-b{ height:14px; background:var(--panel2); border-radius:4px; display:flex; overflow:hidden; }
.kx .sp-b i.live{ background:var(--kg); } .kx .sp-b i.dead{ background:#3a2530; }
.kx .sp em{ font-style:normal; font-family:'Big Shoulders Display',sans-serif; font-size:20px; text-align:right; color:var(--ink); }
[data-testid="stMarkdownContainer"] .kx .sp span{ font-family:'Archivo',sans-serif; font-size:10.5px; color:var(--dim) !important; }
.kx .lt{ display:grid; grid-template-columns:36px minmax(0,1fr) 1.6fr 64px; gap:10px; align-items:center; padding:7px 10px; border-bottom:1px solid #221f20; }
.kx .lt.me{ background:linear-gradient(90deg,rgba(251,8,73,.45),transparent 70%); border-radius:10px; }
[data-testid="stMarkdownContainer"] .kx .lt-n{ font-family:'Big Shoulders Display',sans-serif; font-size:22px; color:var(--dim) !important; }
.kx .lt-t b{ display:block; font-family:'Archivo',sans-serif; font-weight:700; font-size:15px; }
[data-testid="stMarkdownContainer"] .kx .lt-t span{ font-size:11px; color:var(--dim) !important; }
.kx .lt-b{ height:14px; background:var(--panel2); border-radius:4px; overflow:hidden; } .kx .lt-b i{ display:block; height:100%; background:linear-gradient(90deg,#c8063b,#578ed5); }
.kx .lt em{ font-style:normal; font-family:'Big Shoulders Display',sans-serif; font-size:20px; color:var(--kg); text-align:right; }
.kx.chs{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:10px; margin:0 0 16px; }
.kx .ch{ background:#101011; border:1px solid #2a2a30; border-radius:12px; padding:12px 14px; }
.kx .ch em{ display:block; font-style:normal; font-family:'Big Shoulders Display',sans-serif; font-size:40px; color:var(--kg); line-height:1; }
.kx .ch b{ display:block; font-family:'Playfair Display',serif; font-style:italic; font-size:19px; margin-top:4px; }
[data-testid="stMarkdownContainer"] .kx .ch span{ font-size:11.5px; color:var(--muted) !important; }
/* Playoffs (kreeper/playoffs_view.py): seeds gold-to-royal, Anton numbers, the big game on royal */
.po-sd.in i{ background:linear-gradient(180deg,#578ed5,#fb0849) !important; opacity:1 !important; }
.po-sd b{ font-family:'Big Shoulders Display',sans-serif !important; font-weight:400 !important; font-size:15px !important; }
.po-sd.in b{ color:var(--ink) !important; }
.po-wk b{ font-family:'Big Shoulders Display',sans-serif !important; font-weight:400 !important; font-size:20px !important; color:var(--ink) !important; }
.po-wk b.po-d{ color:var(--dim) !important; }
.po-wk i.po-g,.po-wk i.po-a{ background:#578ed5 !important; opacity:.85 !important; } .po-wk i.po-d{ background:#4a4245 !important; }
.po-wk.big{ background:#c8063b !important; border-color:#c8063b !important; box-shadow:none !important; }
.po-big{ background:#c8063b !important; border:0 !important; color:#ffd0dc; }
.po-big .po-k{ color:#ffd0dc !important; } .po-big div{ color:#ffd0dc !important; }
.po-big div b{ color:var(--ink) !important; font-family:'Playfair Display',serif; font-style:italic; font-size:15px; }
.kx.bh ~ .po-box, .po-box{ max-width:none !important; } .po-strip2, .po-big{ max-width:none !important; }
@media (max-width:760px){
  .kx .mm{ grid-template-columns:1fr 70px 1fr; } .kx .mm-f{ display:none; } .kx .mm-s b{ font-size:24px; } .kx .mm-m b{ font-size:22px; }
  .kx .khs{ grid-template-columns:30px minmax(0,1fr) 36px 50px 36px minmax(0,1fr); gap:4px; } .kx .hh{ display:none; } .kx .he{ grid-template-columns:1fr; }
  .kx .tc-c{ grid-template-columns:1fr; } .kx .tc-x{ padding:0; }
  .kx .sp{ grid-template-columns:80px 1fr 40px; } .kx .sp span{ display:none; }
  .kx .lt{ grid-template-columns:28px minmax(0,1fr) 70px 50px; }
}

/* The Wire's value board as a ranked list */
.kx .wv{ display:grid; grid-template-columns:34px minmax(0,1.3fr) 150px 1fr 52px 100px; gap:10px; align-items:center; padding:8px 10px; border-bottom:1px solid #221f20; }
.kx .wv.me{ background:linear-gradient(90deg,rgba(251,8,73,.22),transparent 70%); border-radius:10px; }
.kx .wv-n{ min-width:0; } .kx .wv-n b{ display:block; font-weight:700; font-size:14px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
[data-testid="stMarkdownContainer"] .kx .wv-n span, [data-testid="stMarkdownContainer"] .kx .wv-c span{ font-size:11px; color:var(--dim) !important; }
.kx .wv-c b{ display:block; font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:22px; }
.kx .wv-b{ height:10px; background:var(--card2); border-radius:99px; overflow:hidden; }
.kx .wv-b i{ display:block; height:100%; background:linear-gradient(90deg,#24456e,#578ed5); } .kx .wv-b i.neg{ background:#4a4245; }
.kx .wv em{ font-style:normal; font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:24px; color:#578ed5; text-align:right; }
.kx .wv em.neg{ color:var(--dim); }
[data-testid="stMarkdownContainer"] .kx .wv-t{ font-size:9.5px; letter-spacing:.08em; text-transform:uppercase; color:#578ed5 !important; }
@media (max-width:760px){ .kx .wv{ grid-template-columns:30px minmax(0,1fr) 60px 44px; } .kx .wv-b, .kx .wv-t{ display:none; } }

/* Taxi: the league's squads as a list, yours as photo cards */
.kx .tx{ display:grid; grid-template-columns:minmax(0,200px) 1fr 52px 100px; gap:10px; align-items:center; padding:9px 10px; border-bottom:1px solid #221f20; }
.kx .tx.me{ background:linear-gradient(90deg,rgba(251,8,73,.22),transparent 70%); border-radius:10px; }
.kx .tx.warn{ box-shadow:inset 3px 0 0 var(--warn); }
.kx .tx-n b{ display:block; font-weight:700; font-size:14px; }
[data-testid="stMarkdownContainer"] .kx .tx-n span{ font-size:11px; color:var(--dim) !important; }
[data-testid="stMarkdownContainer"] .kx .txc{ display:inline-block; font-size:11px; font-weight:700; padding:3px 9px; border-radius:999px; border:1px solid var(--line); margin:0 6px 4px 0; color:var(--ink) !important; }
[data-testid="stMarkdownContainer"] .kx .txc.dash{ border-style:dashed; color:var(--warn) !important; border-color:var(--warn); }
.kx .tx em{ font-style:normal; font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:24px; }
[data-testid="stMarkdownContainer"] .kx .tx-f{ font-size:10px; letter-spacing:.1em; text-transform:uppercase; color:var(--dim) !important; }
[data-testid="stMarkdownContainer"] .kx .tx.warn .tx-f{ color:var(--warn) !important; }
.ktray.txtray{ display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,280px)); gap:12px; }
.ktray.txtray .kt{ background:#101011; border:0; border-radius:6px; padding:0 0 12px; overflow:hidden; box-shadow:inset 0 -3px 0 #fb0849; text-align:left; }
.ktray.txtray .kt.last{ box-shadow:inset 0 -3px 0 var(--warn); }
.ktray.txtray .kt .kh-img{ width:100%; height:auto; aspect-ratio:350 / 254; max-height:200px; border-radius:0; object-fit:cover; object-position:center top; filter:grayscale(1); display:block; margin:0 0 8px; }
.ktray.txtray .kt i{ display:block; font-style:normal; font-size:10px; letter-spacing:.14em; font-weight:800; text-transform:uppercase; color:#578ed5; padding:0 12px; }
.ktray.txtray .kt b{ display:block; font-family:'Playfair Display',serif; font-size:19px; padding:2px 12px; }
.ktray.txtray .kt span{ display:block; font-size:11px; padding:0 12px; }
.ktray.txtray .kt.empty{ border:1px dashed var(--line); padding:14px 0; }
@media (max-width:760px){ .kx .tx{ grid-template-columns:minmax(0,1fr) 44px; } .kx .tx-s, .kx .tx-f{ grid-column:1 / -1; } }
/* The Pot: owed bars in crimson (the ported .sp is gold/dead for Kreeper's FAAB) */
.kx .sp .sp-b i.live{ background:linear-gradient(90deg,#c8063b,#fb0849) !important; }
.kx .sp.me b{ color:#fb0849 !important; }
/* Archivo is wider than Kreeper's condensed face: give the names the room */
.kx .xl{ grid-template-columns:38px 30px minmax(110px,1fr) minmax(40px,100px) 52px 44px !important; gap:8px !important; }
.kx .xl-f{ width:30px !important; height:30px !important; }
.kx .xl-n b{ font-size:13.5px !important; }
/* the status banner's edge is crimson here (Kreeper's is gold) */
.kx.bh.ink::after{ background:#fb0849 !important; }

/* ==== offseason pages ===================================================== */
/* What a keeper costs: the matrix as a crimson heat-map */
.kx.hmx{ display:grid; gap:4px; max-width:760px; }
.kx .hmx-r{ display:grid; grid-template-columns:80px repeat(5,minmax(0,1fr)); gap:4px; align-items:center; }
@media (max-width:760px){
  /* six columns on a phone: the header words ("becomes R1") are what forced
     the grid wider than the screen, so they shrink and wrap instead */
  .kx .hmx-r{ grid-template-columns:54px repeat(5,minmax(0,1fr)); gap:3px; }
  [data-testid="stMarkdownContainer"] .kx .hmx-r.hd span{ font-size:8.5px; letter-spacing:.04em; white-space:normal; line-height:1.15;
    word-break:normal; overflow-wrap:normal; hyphens:none; }
  [data-testid="stMarkdownContainer"] .kx .hmx-c{ font-size:14px; }
  /* the pot's cap label sits inside the glass instead of hanging off it */
  [data-testid="stMarkdownContainer"] .kx .capv span{ left:auto; right:4px; top:-17px; }
  .kx.vbox{ gap:16px; } .kx .vnote{ max-width:none; }
}
[data-testid="stMarkdownContainer"] .kx .hmx-r.hd span{ font-size:10px; letter-spacing:.1em; text-transform:uppercase; font-weight:700; color:var(--dim) !important; text-align:center; }
[data-testid="stMarkdownContainer"] .kx .hmx-t{ font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:18px; color:var(--ink) !important; }
.kx .hmx-c{ --h:0; }   /* each cell sets its own intensity inline */
[data-testid="stMarkdownContainer"] .kx .hmx-c{ text-align:center; font-family:'Big Shoulders Display',sans-serif; font-weight:900; font-size:17px; padding:6px 0; border-radius:6px;
  color:var(--ink) !important; background:rgba(251,8,73,calc(var(--h) * .85 + .05)); }
[data-testid="stMarkdownContainer"] .kx .hmx-c.none{ background:transparent; color:var(--line2) !important; }
/* Set my keepers: a face on every contract, the price in Big Shoulders */
.contract{ display:grid !important; grid-template-columns:auto 1fr auto; gap:14px; align-items:center; }
.contract .cface{ width:64px; height:64px; border-radius:10px; object-fit:cover !important; object-position:top !important; max-width:none !important; filter:grayscale(1); background:var(--card2); }
.contract .price .rd{ font-family:'Big Shoulders Display',sans-serif !important; font-weight:900 !important; font-size:44px !important; }
/* the draft room's on-the-clock card as a crimson banner */
.clockcard{ background:#c8063b !important; border:0 !important; padding:18px 22px !important; }
.clockcard .k{ color:#ffd0dc !important; }
.clockcard .w{ color:var(--ink) !important; font-weight:900 !important; font-size:48px !important; }
.clockcard .v{ font-weight:900 !important; font-size:56px !important; }
.clockcard .tm{ color:#ffd0dc !important; }
.clockcard.late{ background:#101011 !important; box-shadow:inset 5px 0 0 var(--bad); }
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


def masthead(subtitle: str, right: str = "") -> None:
    # The build fingerprint is off the face of the masthead - it was diagnostic
    # clutter sitting on the brand band - but it is not gone. It rides in the
    # title attribute, so hovering the wordmark still answers the only question
    # it was ever there for: is Streamlit Cloud serving this build, or a stale
    # module with the old stylesheet still in memory?
    st.markdown(
        '<div class="mast" title="build %s"><span class="the">the</span>'
        '<span class="name">7<span class="half">&frac12;</span> Men</span>'
        '<span class="yr">%s</span>%s</div>' % (fingerprint(), subtitle, right),
        unsafe_allow_html=True)


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


def potfill(series: list, budget: int, weeks: int = 17) -> str:
    """Cumulative FAAB spend per team - what each has put into the pot.

    The argument is the AREA UNDER the line: every dollar bid is a dollar owed,
    so the filled region is literally the bill. This chart used to make the
    opposite argument - it bracketed the empty space ABOVE each line and called
    that the bill, which was true under the old rule, where unspent budget was
    what came due. Inverting the rule without inverting the picture left the
    page quietly arguing for the wrong behaviour.

    `series` is [{"name", "values", "colour", "key"}] - `key` lines are drawn
    full strength and filled, everyone else recedes.
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
        'font-size="10" fill="var(--acc2)">$%d budget &#8212; the most you could owe</text>'
        % (PL, y(budget), W - PR, y(budget), PL + 5, y(budget) - 7, budget))

    lines, marks = "", []
    for srs in series:
        vals = list(srs["values"])[:n] or [0]
        vals += [vals[-1]] * (n - len(vals))
        pts = " ".join("%.1f,%.1f" % (x(i), y(v)) for i, v in enumerate(vals))
        key, col = bool(srs.get("key")), srs.get("colour", "var(--dim)")
        if key:
            # The filled area IS the bill. Drawn before the stroke so the line
            # still reads as the top edge of the money, not as a border on it.
            lines += ('<polygon points="%s %.1f,%.1f %.1f,%.1f" fill="%s" opacity=".16"/>'
                      % (pts, x(n - 1), y(0), x(0), y(0), col))
        lines += ('<polyline points="%s" fill="none" stroke="%s" stroke-width="%s" '
                  'opacity="%s" stroke-linejoin="round" stroke-linecap="round"/>'
                  % (pts, col, "2.6" if key else "1.3", "1" if key else ".55"))
        ey = y(vals[-1])
        if key:
            # Bracket from the BASELINE up to the endpoint - the height owed.
            lines += ('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                      'stroke-width="1" stroke-dasharray="3 3" opacity=".85"/>'
                      '<circle cx="%.1f" cy="%.1f" r="3.5" fill="%s"/>'
                      % (x(n - 1), ey, x(n - 1), y(0), col, x(n - 1), ey, col))
        marks.append({"y": ey, "col": col, "key": key,
                      "label": "%s  $%d" % (srs["name"][:16], vals[-1])})

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

    return ('<svg viewBox="0 0 %d %d" class="chart" role="img" aria-label="FAAB put into the '
            'pot by team, cumulative">%s%s%s%s%s</svg>'
            % (W, H, grid, ticks, ceiling, lines, labels))


# Old name kept briefly; the chart it drew made the opposite argument.
burndown = potfill


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
