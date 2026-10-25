"""Turn a photo of a manager into the three files the app wants.

    .venv/bin/python scripts/manager_photos.py photo.jpg --name "Josh Lavanchy"
    .venv/bin/python scripts/manager_photos.py photo.jpg --id 334162589502144512

Writes into assets/managers/:

  <id>.jpg       200x200 natural colour, for the circles
  <id>_cut.png   the background-free cutout in natural colour, kept so the
                 duotones can be rebuilt without the original photo
  <id>_g.webp    220x220 cutout in the ACCENT duotone (blue) - "you"
  <id>_r.webp    220x220 cutout in the BASE duotone (crimson) - "them"

    .venv/bin/python scripts/manager_photos.py --retone     # rebuild every
                                                            # duotone from _cut.png

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
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

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
    a = ap.parse_args()

    if a.retone:
        for oid in config.managers():
            f = OUT / f"{oid}_cut.png"
            if f.exists():
                write_tones(oid, Image.open(f).convert("RGBA"), config.manager_name(oid))
            else:
                print(f"{config.manager_name(oid)}: no _cut.png - rerun with his photo")
        return
    if not a.photo:
        ap.error("a photo is required unless --retone")

    oid = resolve(a.name, a.oid)
    who = config.manager_name(oid)
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


if __name__ == "__main__":
    main()
