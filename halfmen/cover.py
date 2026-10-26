"""The weekly cover: one week's biggest story as a skate-mag cover.

Six layouts, one per kind of story, all borrowed from the same shelf of
magazine covers (the run club's app uses the same vocabulary):

  biggest  the week's top score         yellow checks, blue sticker, black boxes
  chase    last place, the Chase        concrete, black and white, script headline
  mover    the biggest climber          sky blue, a giant thin word, breaking the wordmark
  gotw     the Game of the Week         concrete, a wordmark filled with photos, two cut-outs
  bench    the most left on a bench     xerox yellow, stacked red numerals
  lucky    the luckiest win             pink and violet, gothic wordmark, black boxes

Pure HTML - no Streamlit. The app gathers the numbers (app._cover_stories) and
hands this module a story dict plus a function that returns a manager's
cut-out as (data URI, manifest). The manifest says which sides the photo
frame cut through; the cut-out is pinned flush to the cover on its deepest
cut, so a slice reads as the edge of the cover, never a line down the middle.
"""
from __future__ import annotations

import html
from typing import Callable, Dict, Optional, Tuple

FONTS = ("https://fonts.googleapis.com/css2?family=Anton&family=Bungee&family=Shrikhand"
         "&family=Metal+Mania&family=Grenze+Gotisch:wght@900&family=Yellowtail"
         "&family=Permanent+Marker&family=Italiana&family=Space+Mono:wght@700&display=swap")

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
          stroke: str = "#000", shadow: str = "#000", sw: float = 3, fill_attr: str = None) -> str:
    """The wordmark as SVG text, stretched to the cover's width whatever the
    face - which is what keeps a wide font from running off the edge."""
    f = fill_attr or fill
    return (f'<svg class="wc-mast" style="top:{top};transform:translateX(-50%) rotate({tilt}deg)" viewBox="0 0 300 84" aria-hidden="true">'
            f'<text x="154" y="67" text-anchor="middle" textLength="286" lengthAdjust="spacingAndGlyphs" '
            f'font-family="{font}" font-size="{size}" fill="{shadow}" stroke="{shadow}" stroke-width="{sw}">{_e(word)}</text>'
            f'<text x="150" y="62" text-anchor="middle" textLength="286" lengthAdjust="spacingAndGlyphs" '
            f'font-family="{font}" font-size="{size}" fill="{f}" stroke="{stroke}" stroke-width="{sw}" paint-order="stroke">{_e(word)}</text></svg>')


def _cut(img: Img, owner: str, look: str, *, height: float, x: float = 50, tilt: float = 0, flip: bool = False) -> str:
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
    if max(left, right) >= 0.25:
        side = "right" if right >= left else "left"
        # a flip turns about the image's own centre, so it stays where it is pinned
        pos = (f"{side}:0;transform:rotate({tilt}deg){flip_t};"
               f"transform-origin:{'bottom center' if flip else 'bottom ' + side}")
    else:
        pos = f"left:{x}%;transform:translateX(-50%) rotate({tilt}deg){flip_t}"
    return f'<img class="cut" src="{src}" alt="" style="height:{height}%;{pos}">'


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


def render(story: Dict, img: Img, wordmark: str = "7½ MEN") -> str:
    """One cover as HTML (the CSS is `CSS`, injected once by the page)."""
    k = story["kind"]
    wk, month = int(story["week"]), story["month"]
    lines = story.get("lines") or []
    tb = " <em>•</em> ".join(_e(x) for x in lines[:3])
    body = ""
    if k == "biggest":
        body = ('<div class="bg checker"></div><div class="topbar">SCORING IS (STILL) KING</div>'
                + _mast(wordmark, "Bungee", 64, "#fb0849", top="9%")
                + _cut(img, story["owner"], "blue", height=88, x=60, tilt=-3)
                + f'<div class="bx" style="left:5%;top:36%">{_e(story["pts"])} POINTS<br>IN ONE SUNDAY</div>'
                + '<div class="bx sm" style="right:4%;top:29%">BELIEVE<br>THE HYPE</div>'
                + (f'<div class="bx sm" style="left:4%;top:62%">{_e(story["star"])}<br>{_e(story["star_pts"])}</div>'
                   if story.get("star") else "")
                + ('<div class="bx sm" style="left:4%;bottom:16%">BURIED INSIDE:</div>'
                   f'<div class="bx lg" style="left:4%;bottom:5%">{_e(story["buried"])}</div>' if story.get("buried") else "")
                + _barcode(wk, month, right=True))
    elif k == "chase":
        body = ('<div class="bg concrete" style="--g:#77767c"></div>'
                + _mast(wordmark.title(), "Shrikhand", 70, "#ff7a1a", top="3%")
                + _cut(img, story["owner"], "bw", height=86, x=44)
                + f'<div class="script"><small>THE</small><b>Chase is Real!</b><i>{_e(story["first"])} · {_e(story["rec"])} · '
                  f'a ${_e(story["cap"])} pot to play for</i></div>'
                + f'<div class="scrawl">“{_e(story["team"])}” — {_e(story["first"])}</div>'
                + _barcode(wk, month))
    elif k == "mover":
        body = ('<div class="bg sky"></div>'
                + (f'<div class="topbar dark">{tb}</div>' if tb else "")
                + _mast(wordmark, "Metal Mania", 66, "#ffd400", top="9%")
                + '<div class="thin">MOVER</div>'
                + _cut(img, story["owner"], "white", height=84, x=56, tilt=4)
                + f'<div class="vert"><b>{_e(story["moved_word"])}</b> spots up</div>'
                + f'<div class="credit">{_e(story["first"]).upper()}<br>{_e(story["rec"])}</div>'
                + _barcode(wk, month, right=True))
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
                + _cut(img, story["a"], "white", height=72, x=28)
                + _cut(img, story["b"], "white", height=76, x=72)
                + f'<div class="scrawl">{_e(story["team_a"])} v {_e(story["team_b"])}</div>'
                + _barcode(wk, month))
    elif k == "bench":
        whole, _, frac = f'{float(story["pts"]):.1f}'.partition(".")
        on_right = _pinned(img, story["owner"], "xerox") == "right"
        stack_at = "left:5%;right:auto;text-align:left" if on_right else ""
        paint_at = "left:auto;right:-3%" if on_right else ""
        body = ('<div class="bg xerox"></div>'
                + _mast(wordmark, "Bungee", 62, "#2a5bd8", top="6%", tilt=-1, stroke="#e8202a", shadow="#e8202a", sw=1.5)
                + _cut(img, story["owner"], "xerox", height=86, x=34)
                + f'<div class="paint" style="{paint_at}">BENCH</div>'
                + f'<div class="stack" style="{stack_at}">{_e(whole)}<br>.{_e(frac)}<small>POINTS ON THE BENCH</small></div>'
                + _barcode(wk, month, right=not on_right))
    elif k == "lucky":
        body = ('<div class="bg holo"></div>'
                + _mast(wordmark.title(), "Grenze Gotisch", 76, "#ff4fb0", top="4%")
                + _cut(img, story["owner"], "white", height=60, x=50, tilt=-2)
                + f'<div class="bx pk" style="left:6%;top:30%">{_e(story["pts"])} POINTS</div>'
                + '<div class="bx" style="left:6%;top:42%">THE LUCKIEST<br>WIN OF THE WEEK</div>'
                + f'<div class="bx sm" style="right:5%;top:31%;transform:rotate(3deg)">{_e(story["beaten"])} TEAM'
                  f'{"S" if int(story["beaten"]) != 1 else ""}<br>SCORED MORE</div>'
                + f'<div class="bx sm" style="right:5%;bottom:6%;transform:rotate(2deg)">{_e(story["team"]).upper()}<br>WILL TAKE IT</div>'
                + _barcode(wk, month))
    else:
        return ""
    return f'<div class="kx wc" role="img" aria-label="{_e(story.get("label", ""))}">{body}<div class="grain"></div></div>'
