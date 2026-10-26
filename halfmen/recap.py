"""The week as one picture, for the group chat.

Pure drawing - no Streamlit. The app gathers the numbers (the same ones Week
in Review shows) and this turns them into a 1080x1350 PNG: last week's eight
scores as a skyline with each manager's face on his tower, the five stories
of the week underneath, and this week's Game of the Week as the sign-off.

Fonts are bundled in assets/fonts (Big Shoulders Display, Archivo - both OFL)
because Streamlit Cloud has neither installed, and a recap in DejaVu Sans
would not look like the app it came from.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
FACES = ROOT / "assets" / "managers"

W, H = 1080, 1350
BG = (20, 19, 20)
CARD = (29, 27, 28)
LINE = (51, 47, 49)
INK = (244, 241, 242)
INK2 = (180, 170, 174)
DIM = (147, 138, 142)
ACC = (251, 8, 73)
ACC2 = (87, 142, 213)
TEAL = (54, 157, 134)
GREY = (87, 80, 90)


def _font(name: str, size: int):
    try:
        return ImageFont.truetype(str(FONTS / name), size)
    except OSError:
        return ImageFont.load_default()


def _display(size):
    return _font("BigShouldersDisplay-ExtraBold.ttf", size)


def _body(size, bold=False):
    return _font("Archivo-Bold.ttf" if bold else "Archivo-Regular.ttf", size)


def _face(owner: str, d: int, ring: Tuple[int, int, int]) -> Optional[Image.Image]:
    f = FACES / f"{owner}.jpg"
    if not f.exists():
        return None
    im = Image.open(f).convert("RGB").resize((d, d), Image.LANCZOS)
    mask = Image.new("L", (d, d), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, d - 1, d - 1), fill=255)
    out = Image.new("RGBA", (d + 6, d + 6), (0, 0, 0, 0))
    ImageDraw.Draw(out).ellipse((0, 0, d + 5, d + 5), fill=ring + (255,))
    out.paste(im, (3, 3), mask)
    return out


def _fit(draw, text: str, font, width: int) -> str:
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text + "…"


def render(week: int, league: str, scores: Sequence[Tuple[str, str, float]],
           tiles: Sequence[Tuple[str, str, str]], me: Optional[str] = None,
           footer: str = "") -> bytes:
    """`scores` is [(owner_id, first_name, points)], `tiles` [(kicker, big, sub)]."""
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)

    # masthead band
    d.rectangle((0, 0, W, 150), fill=ACC)
    d.text((56, 34), league.upper(), font=_display(64), fill=(26, 2, 8))
    d.text((58, 104), "WEEK %d IN REVIEW" % week, font=_body(26, bold=True), fill=(26, 2, 8))

    # the skyline
    top, base = 330, 760
    order = sorted(scores, key=lambda x: -x[2])
    hi = max([s[2] for s in order] + [1.0])
    n = len(order) or 1
    gap = 18
    bw = (W - 112 - gap * (n - 1)) // n
    for i, (o, name, v) in enumerate(order):
        x = 56 + i * (bw + gap)
        h = int((base - top) * v / hi)
        col = ACC if o == me else ACC2 if i == 0 else GREY
        shade = tuple(int(c * .55) for c in col)
        d.rectangle((x + 10, base - h + 8, x + bw + 8, base), fill=shade)      # the side face
        d.rectangle((x, base - h, x + bw, base), fill=col)
        sc = "%.0f" % v
        fnt = _display(40)
        d.text((x + bw / 2, base - h - 14), sc, font=fnt, fill=INK, anchor="ms")
        f = _face(o, min(bw - 8, 84), col)
        if f is not None:
            im.paste(f, (int(x + bw / 2 - f.width / 2), int(base - h - 64 - f.height)), f)
        d.text((x + bw / 2, base + 34), _fit(d, name, _body(24, True), bw + 12), font=_body(24, True),
               fill=INK2, anchor="ms")

    # the five stories
    y0, cols = 822, 2
    tw = (W - 112 - 16) // cols
    th = 128
    for k, (kick, big, sub) in enumerate(tiles[:6]):
        cx = 56 + (k % cols) * (tw + 16)
        cy = y0 + (k // cols) * (th + 14)
        d.rounded_rectangle((cx, cy, cx + tw, cy + th), radius=14, fill=CARD, outline=LINE, width=2)
        d.text((cx + 22, cy + 18), kick.upper(), font=_body(18, True), fill=ACC2)
        d.text((cx + 22, cy + 42), _fit(d, big, _display(46), tw - 44), font=_display(46), fill=INK)
        d.text((cx + 22, cy + 100), _fit(d, sub, _body(19), tw - 44), font=_body(19), fill=DIM)

    if footer:
        d.rectangle((0, H - 92, W, H), fill=CARD)
        d.line((0, H - 92, W, H - 92), fill=ACC, width=4)
        d.text((56, H - 46), _fit(d, footer, _body(26, True), W - 112), font=_body(26, True), fill=INK, anchor="lm")

    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()
