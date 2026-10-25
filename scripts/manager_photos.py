"""Turn a photo of a manager into the three files the app wants.

    .venv/bin/python scripts/manager_photos.py photo.jpg --name "Josh Lavanchy"
    .venv/bin/python scripts/manager_photos.py photo.jpg --id 334162589502144512

Writes into assets/managers/:

  <id>.jpg       200x200 natural colour, for the circles
  <id>_g.webp    220x220 background-free cutout, crimson-side duotone
  <id>_r.webp    220x220 background-free cutout, ink-side duotone

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

# Bloody Sunday: the "me" half of a cover band is crimson, so that side's
# cutout is the same pink ink the band's type uses; the opponent's half is
# near-black with a blue edge, so theirs is blue.
TONES = {"g": ((0x1A, 0x02, 0x08), (0xFF, 0xD0, 0xDC)),
         "r": ((0x06, 0x10, 0x1C), (0x57, 0x8E, 0xD5))}

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
guard let buf = try? obs.generateMaskedImage(ofInstances: obs.allInstances,
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


def duotone(cut: Image.Image, lo, hi, size: int) -> Image.Image:
    """Flatten the cutout onto a two-colour ramp, keeping its alpha."""
    cut = square_rgba(cut, size)
    lum = cut.convert("L")
    ramp = []
    for ch in range(3):
        ramp += [int(lo[ch] + (hi[ch] - lo[ch]) * (i / 255)) for i in range(256)]
    tinted = Image.merge("RGB", (lum, lum, lum)).convert("RGB").point(ramp)
    tinted.putalpha(cut.getchannel("A"))
    return tinted


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
    ap.add_argument("photo", type=Path)
    ap.add_argument("--name", help="any part of the manager's name in config.yaml")
    ap.add_argument("--id", dest="oid", help="his Sleeper user id")
    ap.add_argument("--box", help="LEFT,TOP,RIGHT,BOTTOM to crop to one person first")
    a = ap.parse_args()

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
    for tone, (lo, hi) in TONES.items():
        f = OUT / f"{oid}_{tone}.webp"
        duotone(cut, lo, hi, 220).save(f, lossless=False, quality=86)
        print(f"{who}: wrote {f.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
