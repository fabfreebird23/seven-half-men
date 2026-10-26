"""The weekly cover: one week's biggest story as a skate-mag cover.

Six layouts, one per kind of story, all borrowed from the same shelf of
magazine covers (the run club's app uses the same vocabulary):

  biggest  the week's top score         yellow checks, blue sticker, black boxes
  chase    last place, the Chase        concrete, black and white, script headline
  mover    the biggest climber          sky blue, a giant thin word, breaking the wordmark
  gotw     the Game of the Week         concrete, a wordmark filled with photos, two cut-outs
  bench    the most left on a bench     xerox yellow, stacked red numerals
  lucky    the luckiest win             pink and violet, gothic wordmark, black boxes
  hitlist  teams under 2% playoff odds  cream paper, orange prints, a marker list crossed out
  issue    a quiet week                 white frame, cyan duotone, the stories in black boxes
  fights   the last regular-season week the whole league in red riso, the four games listed
  streak   four or more wins straight   night sky, flames, burnt-orange halftone, a badge
  rip      a team mathematically out    black notebook paper, red outline, a framed portrait
  field    the regular season is over   all eight in a crushed black-and-white grid
  champion the final is final           black, flames, a gold-foil print
  blowout  a 50-point win               paint splatter, pop-art print
  clinch   a team locks a playoff spot  full-bleed black and white, "IN."

Every manager is printed, not pasted: each look is a posterized gradient map
with its own inks (scripts/manager_photos.py bakes them, halftone and all),
and the cover adds only a glow or an offset shadow on top.

Pure HTML - no Streamlit. The app gathers the numbers (app._cover_stories) and
hands this module a story dict plus a function that returns a manager's
cut-out as (data URI, manifest). The manifest says which sides the photo
frame cut through; the cut-out is pinned flush to the cover on its deepest
cut, so a slice reads as the edge of the cover, never a line down the middle.
"""
from __future__ import annotations

import html
import random
from typing import Callable, Dict, Optional, Tuple

FONTS = ("https://fonts.googleapis.com/css2?family=Anton&family=Bungee&family=Shrikhand"
         "&family=Metal+Mania&family=Grenze+Gotisch:wght@900&family=Yellowtail"
         "&family=Permanent+Marker&family=Italiana&family=Space+Mono:wght@700"
         "&family=Archivo:wdth,wght@62..125,500..900&display=swap")

CSS = """<style>
@import url('""" + FONTS + """');
.wc-row{ display:grid; grid-template-columns:minmax(0,380px) minmax(0,1fr); gap:26px; align-items:start; margin:0 0 18px; }
@media (max-width:760px){ .wc-row{ grid-template-columns:minmax(0,1fr); } }
.kx.wc{ position:relative; aspect-ratio:3/4; overflow:hidden; border-radius:3px; container-type:inline-size; background:#111;
  box-shadow:0 18px 40px -16px rgba(0,0,0,.8), 0 0 0 1px #000; max-width:420px; }
.wc .bg{ position:absolute; inset:0; }
.wc .bg.checker{ background:conic-gradient(#ffd400 25%,#ffe866 0 50%,#ffd400 0 75%,#ffe866 0) 0 0/9cqw 9cqw; }
.wc .bg.concrete{ background:radial-gradient(70% 50% at 30% 30%,rgba(255,255,255,.25),transparent 70%),var(--g,#8f8f94); }
.wc .bg.concrete::after{ content:""; position:absolute; inset:0; opacity:.5; background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.55' numOctaves='3'/><feColorMatrix values='0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 .55 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>"); }
.wc .bg.sky{ background:linear-gradient(180deg,#1460d6,#5fb0ff 75%); }
.wc .bg.holo{ background:radial-gradient(60% 50% at 30% 30%,#ff5cc8,transparent 60%),radial-gradient(50% 60% at 80% 70%,#6a3bff,transparent 60%),#2a0f45; }
.wc .bg.xerox{ background:#efe59a; }
.wc .bg.xerox::after{ content:""; position:absolute; inset:0; opacity:.35; mix-blend-mode:multiply;
  background:repeating-linear-gradient(45deg,#1d1a3a 0 .3cqw,transparent .3cqw 5cqw),repeating-linear-gradient(-45deg,#1d1a3a 0 .3cqw,transparent .3cqw 5cqw); }
.wc .wc-mast{ position:absolute; left:50%; z-index:2; overflow:visible; width:94%; }
.wc img.cut{ position:absolute; z-index:3; bottom:0; max-width:none; width:auto; filter:drop-shadow(0 6px 10px rgba(0,0,0,.25)); }
.wc .topbar{ position:absolute; left:0; right:0; top:0; z-index:4; background:#000; color:#fff; font-family:'Anton',sans-serif;
  font-size:7.2cqw; line-height:1.15; text-align:center; padding:1cqw 2cqw; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.wc .topbar em{ font-style:normal; color:#fb0849; }
.wc .topbar.dark{ font-size:5.2cqw; }
.wc .topbar.light{ background:transparent; color:#000; font-size:4.4cqw; }
.wc .bx{ position:absolute; z-index:4; background:#000; color:#fff; font-family:'Anton',sans-serif; font-size:6cqw; line-height:1.02;
  padding:1cqw 2cqw; text-transform:uppercase; transform:rotate(-2deg); max-width:60%; }
.wc .bx.sm{ font-size:4.4cqw; } .wc .bx.lg{ font-size:9cqw; line-height:.95; }
.wc .bx.pk{ background:#fb0849; color:#000; font-size:8.6cqw; }
.wc .script{ position:absolute; right:5%; bottom:28%; z-index:4; text-align:right; color:#fff; text-shadow:.6cqw .6cqw 0 #000; max-width:80%; }
.wc .script small{ display:block; font:900 4.4cqw 'Archivo',sans-serif; letter-spacing:.3cqw; }
.wc .script b{ display:block; font-family:'Yellowtail',cursive; font-weight:400; font-size:15cqw; line-height:.85; color:#fff; }
.wc .script i{ display:block; font:900 3.6cqw 'Archivo',sans-serif; font-style:normal; text-transform:uppercase; margin-top:1cqw; }
.wc .scrawl{ position:absolute; left:32%; right:3%; bottom:4%; z-index:4; font-family:'Permanent Marker',cursive; font-size:5.2cqw;
  color:#e02a3a; text-align:center; transform:rotate(-3deg); line-height:1.05; }
.wc .thin{ position:absolute; left:0; right:0; top:40%; z-index:4; text-align:center; font-family:'Italiana',serif; font-size:20cqw;
  letter-spacing:3cqw; color:#fff; text-shadow:0 .6cqw 3cqw rgba(0,0,0,.35); }
.wc .vert{ position:absolute; left:2%; bottom:7%; z-index:4; writing-mode:vertical-rl; transform:rotate(180deg);
  font:900 6.4cqw 'Archivo',sans-serif; font-stretch:80%; color:#fb0849; -webkit-text-stroke:.25cqw #000; text-transform:uppercase; }
.wc .vert b{ color:#ffd400; }
.wc .credit{ position:absolute; right:4%; bottom:21%; z-index:4; text-align:right; font:900 5cqw 'Archivo',sans-serif; line-height:1;
  color:#ffd400; text-shadow:.4cqw .4cqw 0 #000; }
.wc .paint{ position:absolute; left:-3%; bottom:13%; z-index:4; font:900 15cqw 'Archivo',sans-serif; font-stretch:120%;
  color:rgba(255,255,255,.82); -webkit-text-stroke:.3cqw rgba(29,26,58,.55); transform:rotate(-8deg) skewX(-10deg); }
.wc .stack{ position:absolute; right:5%; bottom:24%; z-index:4; text-align:right; font:900 28cqw/.8 'Archivo',sans-serif;
  font-stretch:75%; color:#ff3030; letter-spacing:-1cqw; }
.wc .stack small{ display:block; font:700 3.8cqw 'Space Mono',monospace; letter-spacing:.3cqw; color:#1d1a3a; margin-top:2cqw; }
.wc .bc{ position:absolute; z-index:5; left:4%; bottom:3%; background:#fff; color:#000; padding:.8cqw 1.4cqw .6cqw; width:24%; }
.wc .bc.r{ left:auto; right:4%; }
.wc .bc .tp{ display:flex; justify-content:space-between; font:700 2.2cqw 'Space Mono',monospace; }
.wc .bc i{ display:block; height:6cqw; margin-top:.5cqw; background:repeating-linear-gradient(90deg,#000 0 1px,transparent 1px 2px,#000 2px 4px,transparent 4px 5px,#000 5px 6px,transparent 6px 8px); }
.wc .bc u{ display:block; text-decoration:none; font:700 2cqw 'Space Mono',monospace; text-align:center; }
.wc .grain{ position:absolute; inset:0; pointer-events:none; z-index:6; opacity:.18; mix-blend-mode:overlay;
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>"); }
.wc img.cut{ object-fit:contain; object-position:bottom; }
.wc .bg.paper{ background:#f3ead6; }
.wc .bg.paper::after{ content:""; position:absolute; inset:0; opacity:.35; background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='140' height='140'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.7' numOctaves='3'/><feColorMatrix values='0 0 0 0 .45  0 0 0 0 .35  0 0 0 0 .2  0 0 0 .5 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>"); }
.wc .bg.notebook{ background:repeating-linear-gradient(180deg,transparent 0 6.2cqw,#2c3a55 6.2cqw calc(6.2cqw + 1px)),linear-gradient(90deg,transparent 13cqw,#9b1b22 13cqw calc(13cqw + 2px),transparent 0),#0d0d0f; }
.wc .bg.night{ background:radial-gradient(60% 50% at 50% 20%,#1d2c52,transparent 70%),#05060c; }
.wc .bg.ink{ background:#050505; }
.wc .bg.white{ background:#fafafa; }
.wc .bg.slate{ background:#1c1c1c; }
.wc svg.fx{ position:absolute; inset:0; width:100%; height:100%; z-index:1; }
.wc .hand{ position:absolute; z-index:4; font-family:'Permanent Marker',cursive; color:#181512; line-height:1.08; }
.wc .hand s{ text-decoration-thickness:.7cqw; text-decoration-color:#d4240f; }
.wc .frame{ position:absolute; z-index:3; overflow:hidden; }
.wc .frame.red{ border:2.2cqw solid #d8141c; background:#262626; }
.wc .frame img.face{ width:100%; height:100%; object-fit:cover; object-position:center 20%; display:block; }
.wc .list{ position:absolute; z-index:4; display:flex; flex-direction:column; gap:1.2cqw; align-items:flex-start; }
.wc .list .bx{ position:static; transform:none; max-width:none; }
.wc .list .bx.r{ background:#d8141c; }
.wc .grid9{ position:absolute; inset:17% 0 0; display:grid; grid-template-columns:repeat(3,1fr); grid-template-rows:repeat(3,1fr); gap:.6cqw; background:#000; }
.wc .grid9>div{ position:relative; overflow:hidden; background:#3c3c3c; }
.wc .grid9 img{ width:100%; height:100%; object-fit:cover; object-position:center 15%; display:block; }
.wc .grid9 i{ position:absolute; left:1.6cqw; bottom:1.2cqw; font:900 3cqw 'Archivo',sans-serif; color:#fff; font-style:normal; text-shadow:0 0 1cqw #000; }
.wc .grid9 .mid{ background:#d8141c; display:grid; place-items:center; text-align:center; font:400 7cqw/1 'Anton',sans-serif; color:#fff; }
.wc .grid9 .mid small{ display:block; font:700 2.6cqw 'Space Mono',monospace; margin-top:1cqw; }
.wc .badge{ position:absolute; z-index:5; width:24cqw; aspect-ratio:1; border-radius:50%; display:grid; place-items:center; text-align:center;
  background:#ffd400; color:#000; font:900 4cqw/1 'Archivo',sans-serif; transform:rotate(-12deg); box-shadow:0 0 0 .8cqw #000,0 0 0 1.4cqw #ffd400; }
.wc .badge b{ display:block; font-size:10cqw; line-height:.85; }
.wc .ndash{ position:absolute; z-index:4; left:0; right:0; text-align:center; font:400 8cqw 'Anton',sans-serif; color:#fff; letter-spacing:.2cqw; }
.wc .ndash small{ display:block; font:700 3.4cqw 'Space Mono',monospace; color:#d8141c; letter-spacing:.6cqw; }
.wc .big-in{ position:absolute; right:5%; bottom:15%; z-index:4; font:900 22cqw/1 'Archivo',sans-serif; color:#fff; text-shadow:.6cqw .6cqw 0 #000; }
/* the issue's other stories, beside the cover */
.wc-in{ display:grid; gap:10px; min-width:0; }
.wc-in .wc-k{ font-family:'Space Mono',monospace; font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--acc); }
.wc-in h3{ margin:0; font-family:var(--f-display); font-weight:800; font-size:34px; line-height:.95; text-transform:uppercase; text-wrap:balance; }
.wc-in p{ margin:0; color:var(--ink2); font-size:14px; max-width:52ch; }
.wc-in ol{ margin:6px 0 0; padding:0; list-style:none; display:grid; gap:8px; }
.wc-in li{ display:grid; grid-template-columns:auto minmax(0,1fr); gap:10px; align-items:baseline; border-top:1px solid var(--line); padding-top:8px; }
.wc-in li b{ font-family:'Anton',sans-serif; font-weight:400; font-size:15px; letter-spacing:.02em; text-transform:uppercase; color:var(--ink); }
.wc-in li em{ font-style:normal; font-size:13px; color:var(--ink2); }
[data-testid="stMarkdownContainer"] a.wc-all{ display:inline-block; margin-top:6px; color:var(--acc2) !important;
  text-decoration:none; font-weight:600; font-size:13px; }
/* the archive: every issue on a rack */
.wc-rack{ display:grid; gap:26px; grid-template-columns:repeat(auto-fill,minmax(min(100%,250px),1fr)); }
.wc-rack figure{ margin:0; min-width:0; }
.wc-rack .kx.wc{ max-width:none; }
.wc-rack figcaption{ margin-top:10px; font-size:12px; color:var(--ink2); }
.wc-rack figcaption b{ display:block; font-family:'Anton',sans-serif; font-weight:400; font-size:15px; letter-spacing:.02em;
  text-transform:uppercase; color:var(--ink); }
@media (max-width:760px){ .wc-rack{ grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; } }
[data-testid="stMarkdownContainer"] .wc-in a{ color:var(--acc2) !important; text-decoration:none; font-weight:600; font-size:13px; }
</style>"""

Img = Callable[[str, str], Tuple[Optional[str], dict]]


def _e(s) -> str:
    return html.escape(str(s), quote=True)


def _mast(word: str, font: str, size: int, fill: str, *, top: str, tilt: float = -2,
          stroke: str = "#000", shadow: Optional[str] = "#000", sw: float = 3, fill_attr: str = None,
          attrs: str = "", z: int = 2) -> str:
    """The wordmark as SVG text, stretched to the cover's width whatever the
    face - which is what keeps a wide font from running off the edge."""
    f = fill_attr or fill
    under = (f'<text x="154" y="67" text-anchor="middle" textLength="286" lengthAdjust="spacingAndGlyphs" '
             f'font-family="{font}" font-size="{size}" fill="{shadow}" stroke="{shadow}" stroke-width="{sw}" {attrs}>{_e(word)}</text>'
             if shadow else "")
    return (f'<svg class="wc-mast" style="z-index:{z};top:{top};transform:translateX(-50%) rotate({tilt}deg)" viewBox="0 0 300 84" aria-hidden="true">'
            + under
            + f'<text x="150" y="62" text-anchor="middle" textLength="286" lengthAdjust="spacingAndGlyphs" '
            f'font-family="{font}" font-size="{size}" fill="{f}" stroke="{stroke}" stroke-width="{sw}" paint-order="stroke" {attrs}>{_e(word)}</text></svg>')


# What the cover adds over a printed cut-out: a glow or an offset shadow.
GLOW = {
    "gold": "drop-shadow(0 0 1.6cqw #ff5a00) drop-shadow(0 0 .3cqw #ffd76a)",
    "fire": "drop-shadow(0 0 2.2cqw #ff3c00) drop-shadow(.8cqw .8cqw 0 #000)",
    "riso": "drop-shadow(.9cqw .4cqw 0 #d8141c)",
    "pop": "drop-shadow(1.2cqw 1.2cqw 0 #000)",
    "orange": "drop-shadow(.6cqw .6cqw 0 #181512)",
    "xerox": "none",
}


def _cut(img: Img, owner: str, look: str, *, height: float, x: float = 50, tilt: float = 0, flip: bool = False,
         bottom: float = 0, cap: Optional[float] = None, pin: bool = True) -> str:
    """A manager's cut-out, as tall as `height` percent of the cover, centred
    on `x` percent - unless the photo frame sliced him, in which case his
    deepest cut sits flush on that edge of the cover."""
    src, man = img(owner, look)
    if not src:
        return ""
    hard = man.get("hard") or {}
    left, right = hard.get("left", 0), hard.get("right", 0)
    flip_t = " scaleX(-1)" if flip else ""
    if flip:
        left, right = right, left
    if pin and max(left, right) >= 0.25:
        side = "right" if right >= left else "left"
        # a flip turns about the image's own centre, so it stays where it is pinned
        pos = (f"{side}:0;transform:rotate({tilt}deg){flip_t};"
               f"transform-origin:{'bottom center' if flip else 'bottom ' + side}")
    else:
        pos = f"left:{x}%;transform:translateX(-50%) rotate({tilt}deg){flip_t}"
    extra = (f";bottom:{bottom}%" if bottom else "") + (f";max-width:{cap}%" if cap else "")
    if look in GLOW:
        extra += f";filter:{GLOW[look]}"
    return f'<img class="cut" src="{src}" alt="" style="height:{height}%;{pos}{extra}">'


def _pinned(img: Img, owner: str, look: str) -> Optional[str]:
    """The cover edge this cut-out will be pinned to, if any - so the rest of
    the layout can move to the free side."""
    _src, man = img(owner, look)
    hard = man.get("hard") or {}
    left, right = hard.get("left", 0), hard.get("right", 0)
    if max(left, right) >= 0.25:
        return "right" if right >= left else "left"
    return None


def _barcode(week: int, month: str, right: bool = False) -> str:
    return (f'<div class="bc{" r" if right else ""}"><div class="tp"><b>{_e(month)}</b><b>{week:02d}</b></div><i></i>'
            f'<u>0 75026 000{week:02d} {(week * 7) % 10}</u></div>')


def _flames(key: str, seed: int) -> str:
    """A wall of fire along the bottom of the cover, the same every time it
    is drawn for the same week (ids carry `key` so a rack of covers never
    shares one)."""
    import random
    rnd = random.Random(seed)
    d, x = "M-20 420 L-20 300", -20.0
    while x < 320:
        w = rnd.uniform(18, 34)
        peak = rnd.uniform(120, 250) if 40 < x < 260 else rnd.uniform(190, 280)
        d += (f" Q{x + w * .2:.0f} {peak + 60:.0f} {x + w * .5:.0f} {peak:.0f}"
              f" Q{x + w * .8:.0f} {peak + 70:.0f} {x + w:.0f} {rnd.uniform(270, 320):.0f}")
        x += w
    d += " L320 420Z"
    return (f'<svg class="fx" viewBox="0 0 300 400" preserveAspectRatio="none" aria-hidden="true"><defs>'
            f'<filter id="fl{key}" x="-20%" y="-30%" width="140%" height="160%"><feTurbulence type="fractalNoise" '
            f'baseFrequency=".015 .05" numOctaves="3" seed="{seed % 97 + 3}"/><feDisplacementMap in="SourceGraphic" scale="26"/></filter>'
            f'<filter id="gl{key}" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="14"/></filter>'
            f'<linearGradient id="fg{key}" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#fff6c2"/>'
            f'<stop offset=".2" stop-color="#ffc21a"/><stop offset=".42" stop-color="#ff5a00"/><stop offset=".7" stop-color="#c41a00"/>'
            f'<stop offset="1" stop-color="#6a0a00"/></linearGradient></defs>'
            f'<path d="{d}" fill="#ff4a00" filter="url(#gl{key})" opacity=".8"/>'
            f'<g filter="url(#fl{key})"><path d="{d}" fill="url(#fg{key})"/></g></svg>')


def _splatter(key: str) -> str:
    blobs = ((70, 90, 70, "#1fb3ff"), (240, 70, 58, "#ffd400"), (250, 250, 80, "#ff2d6f"), (50, 300, 76, "#18c26b"),
             (160, 180, 44, "#ff7a1a"), (130, 360, 38, "#6a3bff"), (20, 170, 12, "#ff2d6f"), (290, 150, 10, "#1fb3ff"),
             (200, 330, 14, "#ffd400"), (110, 40, 9, "#ff2d6f"))
    return (f'<svg class="fx" viewBox="0 0 300 400" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><defs>'
            f'<filter id="sp{key}" x="-20%" y="-20%" width="140%" height="140%"><feTurbulence type="fractalNoise" '
            f'baseFrequency=".05" numOctaves="2" seed="9"/><feDisplacementMap in="SourceGraphic" scale="34"/></filter></defs>'
            f'<rect width="300" height="400" fill="#f4efe6"/><g filter="url(#sp{key})">'
            + "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}"/>' for x, y, r, c in blobs) + '</g></svg>')


def _face(img: Img, owner: str, look: str, cls: str = "face") -> str:
    src, _man = img(owner, "face-" + look)
    return f'<img class="{cls}" src="{src}" alt="">' if src else ""


BLACK = 'font-weight="900" font-stretch="125%"'


# ------------------------------------------------------------------ skins
# A story is not tied to a look. Every one-person story (the top score, the
# bench, a lucky win, the mover, the Chase, a streak, a blowout, a clinch)
# can run in any of these skins, each one off the Thrasher shelf; the app
# deals them out at random week by week, never the same skin within two
# weeks. The layouts that only make sense for one story - the Game of the
# Week, the hit list, the four fights, the field, In memoriam, the
# championship issue, the table of contents - keep their own.
SKINS = ("checker", "concrete", "sky", "xerox", "holo", "night", "splat", "slate", "paper", "cyan")
HOME = {"biggest": "checker", "chase": "concrete", "mover": "sky", "bench": "xerox", "lucky": "holo",
        "streak": "night", "blowout": "splat", "clinch": "slate"}
ROTATING = tuple(HOME)
# The skin each fixed layout looks most like, so the deal never puts, say, a
# cyan frame the week after the table of contents.
LOOK_OF = {"issue": "cyan", "hitlist": "paper", "gotw": "concrete", "fights": "concrete", "champion": "night"}


def deal(kinds: Dict[int, str], seed: str, chosen: Optional[Dict[int, str]] = None) -> Dict[int, str]:
    """{week: skin} for a season's covers, dealt oldest first: a one-person
    story draws at random from SKINS, never a skin used in the two weeks
    before it; a fixed layout keeps its own. Seeded by `seed` and the week,
    so a cover looks the same every time it is shown. `chosen` pins weeks
    that already have a skin."""
    out: Dict[int, str] = {}
    recent: list = []
    for w in sorted(kinds):
        k = kinds[w]
        if k in ROTATING:
            pool = [x for x in SKINS if x not in recent[-2:]]
            sk = (chosen or {}).get(w) or random.Random("%s-%d-%s" % (seed, w, k)).choice(pool)
            look = sk
        else:
            sk, look = k, LOOK_OF.get(k, k)
        out[w] = sk
        recent.append(look)
    return out


def _slots(story: Dict) -> Dict:
    """What any skin needs, from whatever kind of story this is: the big
    number and its unit, the one giant word, a kicker line, the cover lines,
    a script headline and the top bar."""
    k, first = story["kind"], str(story.get("first") or "").upper()
    rng = random.Random("%s-%s" % (story.get("week"), k))
    if k == "biggest":
        return dict(big=story["pts"], unit="POINTS", word="SCORING", kicker="IN ONE SUNDAY", script="Big Sunday",
                    tag=rng.choice(["BELIEVE<br>THE HYPE", "NOBODY<br>WAS CLOSE", "CALL THE<br>COMMISH"]),
                    top=rng.choice(["SCORING IS (STILL) KING", "THE BIG SUNDAY ISSUE", "PUT UP NUMBERS"]),
                    lines=[x for x in ((f'{_e(story["star"])}<br>{_e(story["star_pts"])}' if story.get("star") else ""),
                                       _e(story.get("buried") or "")) if x], raw=True)
    if k == "chase":
        return dict(big=story["rec"], unit="", word="CHASE", kicker="A $%s POT TO PLAY FOR" % story["cap"],
                    script="Chase is Real!", tag="THE<br>CHASE", top="THE CHASE IS REAL",
                    lines=[_e(story["team"]).upper(), "%s · %s" % (first, _e(story["rec"]))], raw=True,
                    quote="“%s” — %s" % (story["team"], story.get("first", "")))
    if k == "mover":
        return dict(big=str(story["moved_word"]).upper(), unit="SPOTS UP", word="MOVER", kicker="THE BIGGEST CLIMB",
                    script="Movin' Up", tag="LOOK<br>OUT", top="THE CLIMB",
                    lines=["%s %s" % (first, story["rec"])])
    if k == "bench":
        return dict(big="%.1f" % float(story["pts"]), unit="POINTS ON THE BENCH", word="BENCH",
                    kicker="LEFT ON THE BENCH", script="Benched!", tag="START<br>'EM NEXT TIME",
                    top=rng.choice(["BENCH WATCH", "WRONG GUYS", "SET YOUR LINEUP"]), lines=["%s'S BENCH" % first])
    if k == "lucky":
        n = int(story["beaten"])
        return dict(big=story["pts"], unit="POINTS", word="LUCKY", kicker="THE LUCKIEST WIN OF THE WEEK",
                    script="Lucky!", tag="WE'LL<br>ALLOW IT", top="THE LUCKY ISSUE",
                    lines=["%d TEAM%s SCORED MORE" % (n, "S" if n != 1 else ""), "%s WILL TAKE IT" % str(story["team"]).upper()])
    if k == "streak":
        return dict(big=str(story["n"]), unit="STRAIGHT", word="ON FIRE", kicker="%s WINS IN A ROW" % story["n"],
                    script="On Fire", tag="HEATING<br>UP", top="HOT HOT HOT",
                    lines=["%s %s" % (first, story["rec"]), "%s POINTS FOR" % story["pf"]])
    if k == "blowout":
        return dict(big="BY " + str(story["margin"]), unit="", word="BLOWOUT", kicker="NOT EVEN CLOSE",
                    script="Blowout", tag="CALL<br>IT", top="THE BLOWOUT ISSUE",
                    lines=["%s %s" % (first, story["pts_w"]), "%s %s" % (str(story["loser"]).upper(), story["pts_l"])])
    if k == "clinch":
        return dict(big="IN.", unit="", word="CLINCHED", kicker="LOCKED INTO THE PLAYOFFS", script="Clinched",
                    tag="SEE YOU IN<br>DECEMBER", top="PLAYOFF BOUND", lines=["%s · CLINCHED" % first])
    return {}


def _fit(text: str, size: float, room: float) -> float:
    """A font size, in cqw, that keeps `text` inside `room` cqw of width."""
    return round(min(size, room / max(1, len(str(text))) * 1.9), 1)


def _skin(skin: str, story: Dict, img: Img, wordmark: str) -> str:
    s = _slots(story)
    if not s:
        return ""
    wk, month, o = int(story["week"]), story["month"], story["owner"]
    first = _e(str(story.get("first") or "").upper())
    big, unit, word = _e(s["big"]), _e(s["unit"]), _e(s["word"])
    lines = s["lines"] if s.get("raw") else [_e(x) for x in s["lines"]]
    if skin == "checker":
        return ('<div class="bg checker"></div>' + f'<div class="topbar">{_e(s["top"])}</div>'
                + _mast(wordmark, "Bungee", 64, "#fb0849", top="9%")
                + _cut(img, o, "blue", height=88, x=60, tilt=-3)
                + f'<div class="bx" style="left:5%;top:36%">{big} {unit}<br>{_e(s["kicker"])}</div>'
                + f'<div class="bx sm" style="right:4%;top:29%">{s["tag"]}</div>'
                + (f'<div class="bx sm" style="left:4%;top:62%">{lines[0]}</div>' if len(lines) > 1 else "")
                + (f'<div class="bx sm" style="left:4%;bottom:16%">BURIED INSIDE:</div>'
                   f'<div class="bx lg" style="left:4%;bottom:5%">{lines[-1]}</div>' if lines else "")
                + _barcode(wk, month, right=True))
    if skin == "concrete":
        return ('<div class="bg concrete" style="--g:#77767c"></div>'
                + _mast(wordmark.title(), "Shrikhand", 70, "#ff7a1a", top="3%")
                + _cut(img, o, "bw", height=86, x=44)
                + f'<div class="script"><small>THE</small><b>{_e(s["script"])}</b><i>{first} · {big} {unit} · '
                  f'{_e(s["kicker"])}</i></div>'
                + f'<div class="scrawl">{_e(s["quote"]) if s.get("quote") else (lines[-1] if lines else "")}</div>'
                + _barcode(wk, month))
    if skin == "sky":
        return ('<div class="bg sky"></div>' + f'<div class="topbar dark">{_e(s["top"])} <em>•</em> WEEK {wk}</div>'
                + _mast(wordmark, "Metal Mania", 66, "#ffd400", top="9%")
                + f'<div class="thin" style="font-size:{_fit(s["word"], 20, 92)}cqw">{word}</div>'
                + _cut(img, o, "sky", height=84, x=56, tilt=4)
                + f'<div class="vert"><b>{big}</b> {unit}</div>'
                + f'<div class="credit">{first}<br>{lines[0] if lines else ""}</div>'
                + _barcode(wk, month, right=True))
    if skin == "xerox":
        whole, dot, frac = str(s["big"]).partition(".")
        on_right = _pinned(img, o, "xerox") == "right"
        stack_at = "left:5%;right:auto;text-align:left;" if on_right else ""
        num = (f'{_e(whole)}<br>.{_e(frac)}' if dot and len(whole) <= 3 else big)
        size = 28 if dot and len(whole) <= 3 else _fit(s["big"], 28, 70)
        return ('<div class="bg xerox"></div>'
                + _mast(wordmark, "Bungee", 62, "#2a5bd8", top="6%", tilt=-1, stroke="#e8202a", shadow="#e8202a", sw=1.5)
                + _cut(img, o, "xerox", height=86, x=34)
                + f'<div class="paint" style="{"left:auto;right:-3%;" if on_right else ""}font-size:{_fit(s["word"], 15, 80)}cqw">{word}</div>'
                + f'<div class="stack" style="{stack_at}font-size:{size}cqw">{num}<small>{unit or _e(s["kicker"])}</small></div>'
                + _barcode(wk, month, right=not on_right))
    if skin == "holo":
        return ('<div class="bg holo"></div>'
                + _mast(wordmark.title(), "Grenze Gotisch", 76, "#ff4fb0", top="4%")
                + _cut(img, o, "holo", height=60, x=50, tilt=-2)
                + f'<div class="bx pk" style="left:6%;top:30%">{big} {unit if len(unit) < 9 else ""}</div>'
                + f'<div class="bx" style="left:6%;top:42%">{_e(s["kicker"])}</div>'
                + (f'<div class="bx sm" style="right:5%;top:31%;transform:rotate(3deg)">{lines[0]}</div>' if lines else "")
                + (f'<div class="bx sm" style="right:5%;bottom:6%;transform:rotate(2deg)">{lines[1]}</div>' if len(lines) > 1 else "")
                + _barcode(wk, month))
    if skin == "night":
        return ('<div class="bg night"></div>' + _flames(f"n{wk}", wk * 31 + 1)
                + _mast(wordmark, "Bungee", 64, "#ffd400", top="4%", z=4)
                + _cut(img, o, "fire", height=80, x=52)
                + f'<div class="badge" style="right:5%;top:24%"><div><b style="font-size:{_fit(s["big"], 10, 20)}cqw">{big}</b>'
                  f'{unit if len(unit) < 10 else ""}</div></div>'
                + f'<div class="bx lg" style="left:5%;top:28%">{word}</div>'
                + f'<div class="bx sm" style="left:5%;top:40%">{"<br>".join(lines[:2])}</div>'
                + _barcode(wk, month))
    if skin == "splat":
        return (_splatter(f"p{wk}")
                + _mast(wordmark, "Shrikhand", 70, "#fff", top="4%", tilt=-3, z=4)
                + _cut(img, o, "pop", height=62, x=62, tilt=3)
                + f'<div class="bx lg" style="left:5%;top:29%">{big}</div>'
                + f'<div class="bx sm" style="left:5%;top:42%">{"<br>".join(lines[:2]) or unit}</div>'
                + f'<div class="paint" style="color:#fff;-webkit-text-stroke:.4cqw #000;bottom:7%;font-size:{_fit(s["word"], 15, 80)}cqw">{word}</div>'
                + _barcode(wk, month, right=True))
    if skin == "slate":
        return ('<div class="bg slate"></div>'
                + _mast(wordmark, "Archivo", 72, "#fff", top="4%", tilt=0, shadow=None, sw=0, attrs=BLACK, z=4)
                + _cut(img, o, "bw", height=112, x=50, bottom=-18)
                + f'<div class="big-in" style="font-size:{_fit(s["big"], 22, 70)}cqw">{big}</div>'
                + f'<div class="bx" style="right:5%;bottom:9%;transform:none;background:#fff;color:#000">{first} · {word}</div>'
                + _barcode(wk, month))
    if skin == "paper":
        notes = "".join(f"{x}<br>" for x in lines[:3])
        return ('<div class="bg paper"></div>'
                + _mast(wordmark, "Metal Mania", 66, "#181512", top="4%", tilt=-3, stroke="#181512", shadow=None, sw=1, z=4)
                + _cut(img, o, "orange", height=72, x=28, tilt=-3, cap=60)
                + f'<div class="hand" style="right:5%;top:24%;max-width:48%;text-align:right;font-size:5.4cqw;transform:rotate(3deg)">'
                  f'{first}<div style="font-size:{_fit(s["big"], 14, 44)}cqw;color:#d4240f;line-height:1">{big}</div>'
                  f'<div style="font-size:4.2cqw">{unit}<br>{notes}</div></div>'
                + f'<div class="hand" style="left:4%;right:4%;bottom:4%;text-align:center;font-size:{_fit(s["word"] + "!!!", 9, 80)}cqw;'
                  f'color:#d4240f;transform:rotate(-4deg)">{word}!!!</div>')
    if skin == "cyan":
        rows = [f"{first} {big}", _e(s["kicker"])] + [x for x in lines[:3]]
        boxes = "".join(f'<div class="bx{" r" if i == len(rows) - 1 else ""}">{x}</div>' for i, x in enumerate(rows))
        return ('<div class="bg white"></div><div class="frame" style="inset:4%;background:#04141c">'
                + _cut(img, o, "cyan", height=96, x=72, pin=False, cap=70) + '</div>'
                + _mast(wordmark, "Archivo", 70, "#2fd3ff", top="6%", tilt=0, shadow=None, sw=0, attrs=BLACK, z=4)
                + f'<div class="list" style="left:8%;top:30%"><div class="bx sm">WEEK {wk}:</div>{boxes}</div>'
                + _barcode(wk, month, right=True))
    return ""


def render(story: Dict, img: Img, wordmark: str = "7½ MEN", skin: Optional[str] = None) -> str:
    """One cover as HTML (the CSS is `CSS`, injected once by the page). One-
    person stories run in `skin` (one of SKINS), or their home skin."""
    k = story["kind"]
    wk, month = int(story["week"]), story["month"]
    lines = story.get("lines") or []
    tb = " <em>•</em> ".join(_e(x) for x in lines[:3])
    body = ""
    if k in ROTATING:
        body = _skin(skin if skin in SKINS else HOME[k], story, img, wordmark)
        if not body:
            return ""
    elif k == "gotw":
        pics = "".join(
            f'<image href="{src}" x="{i * 100}" y="-8" width="100" height="100" preserveAspectRatio="xMidYMid slice"/>'
            for i, src in enumerate(story.get("photos") or []) if src)
        pid = f"wcp{wk}"
        mast = (f'<svg class="wc-mast" style="top:7%;transform:translateX(-50%) rotate(-2deg)" viewBox="0 0 300 84" aria-hidden="true">'
                f'<defs><pattern id="{pid}" patternUnits="userSpaceOnUse" width="300" height="84">{pics}</pattern></defs>'
                f'<text x="154" y="67" text-anchor="middle" textLength="286" lengthAdjust="spacingAndGlyphs" font-family="Bungee" '
                f'font-size="64" fill="#000" stroke="#000" stroke-width="3">{_e(wordmark)}</text>'
                f'<text x="150" y="62" text-anchor="middle" textLength="286" lengthAdjust="spacingAndGlyphs" font-family="Bungee" '
                f'font-size="64" fill="url(#{pid})" stroke="#fff" stroke-width="2.4" paint-order="stroke">{_e(wordmark)}</text></svg>')
        body = ('<div class="bg concrete" style="--g:#9a98a4"></div>'
                + f'<div class="topbar light">{_e(month)} <em>•</em> WEEK {wk} <em>•</em> {_e(story["stakes"])} PTS AT STAKE</div>'
                + mast
                + _cut(img, story["a"], "riso", height=72, x=28)
                + _cut(img, story["b"], "riso", height=76, x=72)
                + f'<div class="scrawl">{_e(story["team_a"])} v {_e(story["team_b"])}</div>'
                + _barcode(wk, month))
    elif k == "hitlist":
        rows = "".join((f"<s>{_e(n)} {_e(rec)}</s>" if dead else f"{_e(n)} {_e(rec)}") + "<br>"
                       for n, rec, dead in story["rows"])
        a, b = (list(story["owners"]) + [None, None])[:2]
        body = ('<div class="bg paper"></div>'
                + _mast(wordmark, "Metal Mania", 66, "#181512", top="4%", tilt=-3, stroke="#181512", shadow=None, sw=1, z=4)
                + (_cut(img, a, "orange", height=58, x=20, tilt=-4, pin=False, cap=46) if a else "")
                + (_cut(img, b, "orange", height=52, x=84, tilt=5, pin=False, cap=40) if b else "")
                + '<div class="hand" style="left:33%;top:23%;font-size:6.4cqw;transform:rotate(-3deg)">THE HIT LIST<br>'
                  f'<div style="font-size:4.6cqw">{rows}</div></div>'
                + '<div class="hand" style="left:4%;right:4%;bottom:4%;text-align:center;font-size:8.6cqw;color:#d4240f;'
                  'transform:rotate(-4deg)">DEAD IN DECEMBER!!!</div>')
    elif k == "issue":
        boxes = "".join(f'<div class="bx{" r" if i == len(lines[:5]) - 1 else ""}">{_e(x)}</div>' for i, x in enumerate(lines[:5]))
        body = ('<div class="bg white"></div><div class="frame" style="inset:4%;background:#04141c">'
                + _cut(img, story["owner"], "cyan", height=96, x=72, pin=False, cap=70) + '</div>'
                + _mast(wordmark, "Archivo", 70, "#2fd3ff", top="6%", tilt=0, shadow=None, sw=0, attrs=BLACK, z=4)
                + f'<div class="list" style="left:8%;top:30%"><div class="bx sm">INSIDE WEEK {wk}:</div>{boxes}</div>'
                + _barcode(wk, month, right=True))
    elif k == "fights":
        spots = [(48, 12, 26), (58, 90, 22), (54, 50, 30), (58, 32, 18), (62, 70, 16), (62, 14, 0), (66, 88, 0), (72, 52, 0)]
        owners = list(story["owners"])[:8]
        crowd = "".join(_cut(img, o, "riso", height=h, x=x, bottom=b, pin=False, cap=42)
                        for o, (h, x, b) in zip(reversed(owners), spots[8 - len(owners):]))
        fights = "".join(f'<div class="bx sm">{_e(a)} V {_e(b)}</div>' for a, b in story["pairs"])
        body = ('<div class="bg concrete" style="--g:#3a393e"></div>'
                + _mast(wordmark, "Bungee", 64, "#d8141c", top="3%")
                + '<div style="position:absolute;inset:0;z-index:3">' + crowd + '</div>'
                + f'<div class="list" style="left:5%;top:23%"><div class="bx r lg">{_e(story["count_word"])} FIGHTS</div>{fights}</div>'
                + _barcode(wk, month, right=True))
    elif k == "rip":
        body = ('<div class="bg notebook"></div>'
                + _mast(wordmark, "Archivo", 70, "none", top="4%", tilt=0, stroke="#d8141c", shadow=None, sw=2, attrs=BLACK)
                + '<div class="frame red" style="left:17%;right:17%;top:24%;height:50%">'
                + _face(img, story["owner"], "ink") + '</div>'
                + f'<div class="ndash" style="top:78%">{_e(story["first"]).upper()}\'S PLAYOFF HOPES'
                  f'<small>WEEK 1 – WEEK {_e(story["through"])}</small></div>')
    elif k == "field":
        cells = []
        for i, (o, n, place) in enumerate(story["rows"][:8]):
            if i == 4:
                cells.append(f'<div class="mid"><div>THE<br>FIELD<small>AFTER WK {_e(story["through"])}</small></div></div>')
            cells.append(f'<div>{_face(img, o, "bw", "")}<i>{_e(place)} · {_e(n).upper()}</i></div>')
        body = ('<div class="bg ink"></div><div class="grid9">' + "".join(cells) + '</div>'
                + _mast(wordmark, "Archivo", 70, "#fff", top="1%", tilt=0, shadow=None, sw=0, attrs=BLACK, z=4))
    elif k == "champion":
        body = ('<div class="bg ink"></div>' + _flames(f"c{wk}", wk * 17 + 5)
                + _mast(wordmark, "Metal Mania", 68, "#e6b422", top="4%", shadow="#7a1200", z=4)
                + _cut(img, story["owner"], "gold", height=80, x=46, bottom=4, tilt=-2)
                + f'<div class="script" style="bottom:30%;right:4%"><small>YOUR</small><b>Champion</b><i>{_e(story["team"])}</i></div>'
                + f'<div class="topbar dark" style="top:auto;bottom:0;background:#e6b422;color:#000">THE CHAMPIONSHIP ISSUE '
                  f'<em>•</em> {_e(story["year"])}</div>')
    else:
        return ""
    return f'<div class="kx wc" role="img" aria-label="{_e(story.get("label", ""))}">{body}<div class="grain"></div></div>'
