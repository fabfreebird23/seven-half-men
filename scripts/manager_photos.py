"""Turn a photo of a manager into the three files the app wants.

    .venv/bin/python scripts/manager_photos.py photo.jpg --name "Josh Lavanchy"
    .venv/bin/python scripts/manager_photos.py photo.jpg --id 334162589502144512

Writes into assets/managers/:

  <id>.jpg       200x200 natural colour, for the circles
  <id>_cut.png   the background-free cutout in natural colour, kept so the
                 duotones can be rebuilt without the original photo
  <id>_g.webp    220x220 cutout in the ACCENT duotone (blue) - "you"
  <id>_r.webp    220x220 cutout in the BASE duotone (crimson) - "them"

    .venv/bin/python scripts/manager_photos.py photo.jpg --name Josh --body L,T,R,B
                     # the weekly cover's head-and-torso cut-out (see below)
    .venv/bin/python scripts/manager_photos.py --retone     # rebuild every
                                                            # duotone from _cut.png

The body cut-out is printed in every cover look (LOOKS: posterized inks,
halftone, sticker edge) as <id>_body-<look>.webp, and the circle cut-out as
square framed portraits, <id>_face-<look>.webp.

The cutout is cut by macOS's own Vision subject mask (same thing Preview's
"remove background" uses), run through a tiny Swift program compiled on the
fly. It needs macOS 14 or newer and the Xcode command line tools. Without
them the duotones are skipped and the app falls back to the side's best
player's headshot on the covers - the circles still work.

Photos with more than one person in them: pass --box LEFT,TOP,RIGHT,BOTTOM
(pixels in the source image) to crop to one of them first.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from halfmen import config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "managers"

# The Kreeper League's look, in Bloody Sunday. Kreeper puts YOU in its accent
# (gold) on the royal band and THEM in royal on black; this app maps royal to
# crimson and gold to blue, so _g is blue and _r is crimson. Same shape of
# ramp as Kreeper's: shadows almost black, the accent around the upper mids,
# a lighter tint only in the top highlights - which is what makes a face read
# as a poster rather than a tinted photo.
TONES = {
    "g": [(0.00, (3, 6, 16)), (0.45, (28, 56, 108)), (0.78, (87, 142, 213)), (1.00, (198, 220, 248))],
    "r": [(0.00, (12, 1, 4)), (0.45, (92, 4, 30)), (0.78, (200, 6, 59)), (1.00, (255, 178, 196))],
}

_SWIFT = r'''
import Foundation
import Vision
import CoreImage
let args = CommandLine.arguments
guard args.count == 3, let src = CIImage(contentsOf: URL(fileURLWithPath: args[1])) else { exit(2) }
let req = VNGenerateForegroundInstanceMaskRequest()
let handler = VNImageRequestHandler(ciImage: src)
do { try handler.perform([req]) } catch { exit(3) }
guard let obs = req.results?.first else { exit(4) }
// Keep only the person in the middle of the crop. Vision returns every
// subject it finds, and a group photo hands back the neighbours' shoulders
// too. Sample the instance map around where a face sits in a head-and-
// shoulders crop and keep whichever instance owns most of it.
let map = obs.instanceMask
CVPixelBufferLockBaseAddress(map, .readOnly)
let mw = CVPixelBufferGetWidth(map), mh = CVPixelBufferGetHeight(map)
let row = CVPixelBufferGetBytesPerRow(map)
let px = CVPixelBufferGetBaseAddress(map)!.assumingMemoryBound(to: UInt8.self)
var counts = [Int: Int]()
for dy in -12...12 { for dx in -12...12 {
    let x = min(mw - 1, max(0, mw / 2 + dx * mw / 90))
    let y = min(mh - 1, max(0, mh * 9 / 20 + dy * mh / 90))
    let v = Int(px[y * row + x]); if v > 0 { counts[v, default: 0] += 1 }
} }
CVPixelBufferUnlockBaseAddress(map, .readOnly)
let keep = counts.max(by: { $0.value < $1.value }).map { IndexSet(integer: $0.key) } ?? obs.allInstances
guard let buf = try? obs.generateMaskedImage(ofInstances: keep,
                                             from: handler, croppedToInstancesExtent: true) else { exit(5) }
let out = CIImage(cvPixelBuffer: buf)
let ctx = CIContext()
guard let data = ctx.pngRepresentation(of: out, format: .RGBA8,
        colorSpace: CGColorSpace(name: CGColorSpace.sRGB)!) else { exit(6) }
try? data.write(to: URL(fileURLWithPath: args[2]))
'''


def cutout(src: Path) -> Image.Image | None:
    """The subject on a transparent background, via macOS Vision. None if the
    machine can't do it - the app degrades without complaining."""
    with tempfile.TemporaryDirectory() as td:
        swift, png = Path(td) / "cut.swift", Path(td) / "cut.png"
        swift.write_text(_SWIFT)
        try:
            r = subprocess.run(["swift", str(swift), str(src), str(png)],
                               capture_output=True, timeout=180)
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            print(f"  ! no cutout ({e.__class__.__name__}): skipping the duotones")
            return None
        if r.returncode or not png.exists():
            print(f"  ! Vision found no subject (exit {r.returncode}): skipping the duotones")
            return None
        return Image.open(png).convert("RGBA")


def square(im: Image.Image, size: int) -> Image.Image:
    """Centre square crop, biased to the top so a head isn't cut off."""
    w, h = im.size
    side = min(w, h)
    left = (w - side) // 2
    top = min(max(0, (h - side) // 4), h - side)
    return im.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS)


def _ramp(stops):
    """256-entry RGB lookup through the colour stops."""
    out = []
    for i in range(256):
        t = i / 255
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t <= t1:
                f = 0 if t1 == t0 else (t - t0) / (t1 - t0)
                out.append(tuple(round(c0[k] + (c1[k] - c0[k]) * f) for k in range(3)))
                break
    return out


def duotone(cut: Image.Image, stops, size: int) -> Image.Image:
    """The cutout as a poster: luminance stretched to full range across the
    SUBJECT only (the transparent background would otherwise pin the black
    point), then mapped through the tone's ramp. Alpha kept."""
    cut = square_rgba(cut, size)
    alpha = cut.getchannel("A")
    lum = cut.convert("L")
    mask = alpha.point(lambda a: 255 if a > 128 else 0)
    hist = lum.histogram(mask=mask)
    total = sum(hist) or 1
    lo_cut = hi_cut = 0
    acc = 0
    for i, n in enumerate(hist):          # 1% clip at each end, subject pixels only
        acc += n
        if acc >= total * 0.01:
            lo_cut = i
            break
    acc = 0
    for i in range(255, -1, -1):
        acc += hist[i]
        if acc >= total * 0.01:
            hi_cut = i
            break
    span = max(1, hi_cut - lo_cut)
    lum = lum.point(lambda v: max(0, min(255, round((v - lo_cut) * 255 / span))))
    table = _ramp(stops)
    r = lum.point([c[0] for c in table])
    g = lum.point([c[1] for c in table])
    b = lum.point([c[2] for c in table])
    out = Image.merge("RGB", (r, g, b))
    out.putalpha(alpha)
    return out


def write_tones(oid: str, cut: Image.Image, who: str) -> None:
    for tone, stops in TONES.items():
        f = OUT / f"{oid}_{tone}.webp"
        duotone(cut, stops, 220).save(f, lossless=False, quality=88)
        print(f"{who}: wrote {f.relative_to(ROOT)}")


def square_rgba(im: Image.Image, size: int) -> Image.Image:
    """Pad the cutout to a square without stretching it, sitting on the floor."""
    w, h = im.size
    side = max(w, h)
    pad = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    pad.paste(im, ((side - w) // 2, side - h))
    return pad.resize((size, size), Image.LANCZOS)


# ------------------------------------------------------------------ covers
# The weekly cover wants the whole manager - head and torso, as big as the
# cover - in four treatments: a white sticker, a blue sticker, black and
# white, and two-ink xerox. A cut-out can only be as whole as the photo it
# came from: when someone stands at the edge of the frame, the frame slices
# him with a straight line. Those sides are recorded as "hard", get no
# sticker edge, and the cover pins them flush to its own edge, where a
# straight line is just the edge of the cover.
BODY_MAX_H = 820

# Every cover look is a posterized gradient map: the subject's luminance,
# stretched across the subject only, pushed harder (slope/intercept), then
# snapped to a handful of inks from dark to light - which is what makes a
# phone photo read as a printed cover rather than a tinted photo. Some looks
# add a halftone dot screen; most get a sticker edge in their lightest ink.
#   name: (inks dark -> light, halftone, sticker rgb or None, slope, intercept)
LOOKS = {
    "blue":   (["#0b0d2a", "#24308f", "#fb0849", "#ffd9c2", "#fff6ea"], True, (46, 155, 255), 1.3, -.12),   # biggest
    "bw":     (["#000000", "#2a2a2a", "#7a7a7a", "#c8c8c8", "#ffffff"], True, (255, 255, 255), 1.3, -.08),  # chase, clinch
    "sky":    (["#061634", "#1450c8", "#5fb0ff", "#ffd400", "#fffbe6"], False, (255, 255, 255), 1.3, -.12),  # mover
    "riso":   (["#0a0a0a", "#0a0a0a", "#d8141c", "#f4efe6", "#f4efe6"], False, (244, 239, 230), 1.4, -.2),  # gotw, fights
    "xerox":  (["#1d1a3a", "#1d1a3a", "#4c4775", "#c9bf7a", "#f1e896"], True, None, 1.35, -.15),           # bench
    "holo":   (["#1a0730", "#6a3bff", "#ff4fb0", "#ffd0ec", "#fff4fb"], True, (255, 255, 255), 1.3, -.12),  # lucky
    "orange": (["#181512", "#c43a0a", "#ff8a1f", "#ffc46b", "#f3ead6"], True, (243, 234, 214), 1.5, -.22),  # hit list
    "gold":   (["#140400", "#5a1d00", "#b8540a", "#f0a422", "#ffe8a0"], True, (255, 232, 160), 1.35, -.17), # champion
    "fire":   (["#1a0000", "#7a0a00", "#e02a00", "#ff8a00", "#fff2a8"], True, (255, 242, 168), 1.15, -.12), # streak
    "cyan":   (["#04141c", "#0e5d78", "#1fb6dd", "#e9fbff"], False, None, 1.35, -.17),                       # the issue
    "pop":    (["#1a1440", "#6a3bff", "#ff2d6f", "#ffd400", "#ffffff"], True, (255, 255, 255), 1.3, -.12),  # blowout
}
# Head-and-shoulders looks for the framed portraits (In memoriam, The field),
# from the circle cut-out rather than the body.
FACE_LOOKS = {
    "ink": (["#000000", "#3a3a3a", "#9a9a9a", "#f4f4f4"], True, None, 1.5, -.25),
    "bw":  (["#000000", "#2a2a2a", "#7a7a7a", "#c8c8c8", "#ffffff"], False, None, 1.3, -.08),
}


def _hard_sides(cut: Image.Image) -> list:
    """Which sides of the subject's box the photo frame cut through: a side
    is hard when the subject runs along it - judged over the outer few pixels
    because Vision's mask is soft at the edge, and at a low share because an
    arm crossing the frame is only a short run and still reads as a slice."""
    a = cut.getchannel("A")
    w, h = a.size
    px = a.load()
    band = 3

    def share(cols=None, rows=None):
        if cols is not None:
            return max(sum(1 for y in range(h) if px[x, y] > 100) / h for x in cols)
        return max(sum(1 for x in range(w) if px[x, y] > 100) / w for y in rows)
    shares = {"left": share(cols=range(band)), "right": share(cols=range(w - band, w)),
              "bottom": share(rows=range(h - band, h))}
    return {k: round(v, 2) for k, v in shares.items() if v > (0.10 if k == "bottom" else 0.04)}


def _fade(im: Image.Image, sides: dict) -> Image.Image:
    """Dissolve each cut side over the outer fifth of the width, so a slice
    through an arm or a shoulder fades into the cover instead of ending in a
    straight line. Deeper slices get a longer fade."""
    w, h = im.size
    a = im.getchannel("A")
    ramp = Image.new("L", (w, 1), 255)
    rp = ramp.load()
    for side in ("left", "right"):
        if side not in sides:
            continue
        span = max(12, int(w * (0.14 + 0.16 * min(1.0, sides[side]))))
        for i in range(span):
            x = i if side == "left" else w - 1 - i
            rp[x, 0] = min(rp[x, 0], int(255 * (i / span) ** 1.4))
    a = Image.composite(a, Image.new("L", (w, h), 0), ramp.resize((w, h)))
    out = im.copy()
    out.putalpha(a)
    return out


def _sticker(cut: Image.Image, colour, px: int) -> Image.Image:
    a = cut.getchannel("A")
    grown = a.filter(ImageFilter.MaxFilter(px * 2 + 1)).filter(ImageFilter.GaussianBlur(1))
    grown = grown.point(lambda v: 255 if v > 90 else 0)
    base = Image.new("RGBA", cut.size, colour + (0,))
    base.putalpha(grown)
    base.alpha_composite(cut)
    return base


def _hex(c: str):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def _norm_lum(cut: Image.Image) -> Image.Image:
    """Luminance stretched across the subject only (1% clip each end)."""
    mask = cut.getchannel("A").point(lambda a: 255 if a > 128 else 0)
    lum = cut.convert("L")
    hist = lum.histogram(mask=mask)
    total = sum(hist) or 1
    acc, lo = 0, 0
    for i, n in enumerate(hist):
        acc += n
        if acc >= total * 0.01:
            lo = i
            break
    acc, hi = 0, 255
    for i in range(255, -1, -1):
        acc += hist[i]
        if acc >= total * 0.01:
            hi = i
            break
    span = max(1, hi - lo)
    return lum.point(lambda v: max(0, min(255, round((v - lo) * 255 / span))))


def _halftone(rgb: Image.Image, lum: Image.Image, cell: int, strength: float = .45) -> Image.Image:
    """A dot screen multiplied over the print: bigger dots where it is darker."""
    from PIL import ImageChops, ImageDraw
    w, h = lum.size
    dots = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(dots)
    small = lum.resize((max(1, w // cell), max(1, h // cell)), Image.BOX)
    sp = small.load()
    for j in range(small.height):
        for i in range(small.width):
            r = cell * .62 * (1 - sp[i, j] / 255) ** .5
            if r > .4:
                cx, cy = i * cell + cell / 2, j * cell + cell / 2
                d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=0)
    inked = ImageChops.multiply(rgb, Image.merge("RGB", (dots, dots, dots)))
    return Image.blend(rgb, inked, strength)


def posterize(cut: Image.Image, inks, halftone: bool, slope: float, icpt: float, cell: int) -> Image.Image:
    """The cut-out as a printed cover: pushed contrast, snapped to `inks`."""
    lum = _norm_lum(cut)
    n = len(inks)
    pal = [_hex(c) for c in inks]

    def idx(v):
        x = max(0.0, min(1.0, v / 255 * slope + icpt))
        return min(n - 1, int(x * n))
    table = [pal[idx(v)] for v in range(256)]
    rgb = Image.merge("RGB", tuple(lum.point([c[k] for c in table]) for k in range(3)))
    if halftone:
        rgb = _halftone(rgb, lum, cell)
    rgb.putalpha(cut.getchannel("A"))
    return rgb


def write_faces(oid: str, cut: Image.Image, who: str) -> None:
    """Square head-and-shoulders prints for the framed covers."""
    sq = square_rgba(cut, 360)
    for k, (inks, ht, _st, slope, icpt) in FACE_LOOKS.items():
        posterize(sq, inks, ht, slope, icpt, 6).save(OUT / f"{oid}_face-{k}.webp", quality=86)
    print(f"{who}: face prints {', '.join(FACE_LOOKS)}")


def write_body(oid: str, cut: Image.Image, who: str) -> None:
    """The four cover treatments plus a small manifest from a natural-colour
    body cut-out (already cropped to the subject)."""
    hard = _hard_sides(cut)
    if cut.height > BODY_MAX_H:
        cut = cut.resize((round(cut.width * BODY_MAX_H / cut.height), BODY_MAX_H), Image.LANCZOS)
    px = max(8, cut.height // 55)
    # room for the sticker edge on every SOFT side only
    l, r, t = (0 if "left" in hard else px), (0 if "right" in hard else px), px
    canvas = Image.new("RGBA", (cut.width + l + r, cut.height + t), (0, 0, 0, 0))
    canvas.paste(cut, (l, t))
    cut = canvas
    cell = max(5, cut.height // 95)
    for k, (inks, ht, sticker, slope, icpt) in LOOKS.items():
        im = posterize(cut, inks, ht, slope, icpt, cell)
        if sticker:
            im = _sticker(im, sticker, px)
        _fade(im, hard).save(OUT / f"{oid}_body-{k}.webp", quality=86)
    (OUT / f"{oid}_body.json").write_text(json.dumps(
        {"w": cut.width, "h": cut.height, "hard": hard}, indent=1))
    print(f"{who}: body cut-out {cut.size}, hard sides {hard or 'none'}")


def resolve(name: str | None, oid: str | None) -> str:
    if oid:
        if oid not in config.managers():
            sys.exit(f"{oid} is not a manager in config.yaml")
        return oid
    want = (name or "").strip().lower()
    hits = [k for k, m in config.managers().items()
            if want and want in m["name"].lower()]
    if len(hits) != 1:
        sys.exit(f"--name {name!r} matched {len(hits)} managers; use --id instead")
    return hits[0]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("photo", type=Path, nargs="?")
    ap.add_argument("--retone", action="store_true",
                    help="rebuild every manager's duotones from his saved _cut.png")
    ap.add_argument("--name", help="any part of the manager's name in config.yaml")
    ap.add_argument("--id", dest="oid", help="his Sleeper user id")
    ap.add_argument("--box", help="LEFT,TOP,RIGHT,BOTTOM to crop to one person first")
    ap.add_argument("--body", help="LEFT,TOP,RIGHT,BOTTOM of head and torso, for the weekly cover")
    a = ap.parse_args()

    if a.retone:
        for oid in config.managers():
            f = OUT / f"{oid}_cut.png"
            if f.exists():
                write_tones(oid, Image.open(f).convert("RGBA"), config.manager_name(oid))
                write_faces(oid, Image.open(f).convert("RGBA"), config.manager_name(oid))
            else:
                print(f"{config.manager_name(oid)}: no _cut.png - rerun with his photo")
            b = OUT / f"{oid}_body_cut.png"
            if b.exists():
                write_body(oid, Image.open(b).convert("RGBA"), config.manager_name(oid))
        return
    if not a.photo:
        ap.error("a photo is required unless --retone")

    oid = resolve(a.name, a.oid)
    who = config.manager_name(oid)
    OUT.mkdir(parents=True, exist_ok=True)
    if a.body:
        src = Image.open(a.photo).convert("RGB").crop(tuple(int(x) for x in a.body.split(",")))
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "src.png"
            src.save(tmp)
            cut = cutout(tmp)
        if cut is None:
            return
        cut = cut.crop(cut.getchannel("A").point(lambda v: 255 if v > 100 else 0).getbbox())
        cut.save(OUT / f"{oid}_body_cut.png", optimize=True)
        write_body(oid, cut, who)
        return
    src = Image.open(a.photo).convert("RGB")
    if a.box:
        src = src.crop(tuple(int(x) for x in a.box.split(",")))
    OUT.mkdir(parents=True, exist_ok=True)

    jpg = OUT / f"{oid}.jpg"
    square(src, 200).save(jpg, quality=88, optimize=True)
    print(f"{who}: wrote {jpg.relative_to(ROOT)}")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "src.png"
        src.save(tmp)
        cut = cutout(tmp)
    if cut is None:
        return
    cut.save(OUT / f"{oid}_cut.png", optimize=True)
    write_tones(oid, cut, who)
    write_faces(oid, cut, who)


if __name__ == "__main__":
    main()
