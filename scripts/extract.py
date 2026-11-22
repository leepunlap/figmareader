#!/usr/bin/env python3
"""
Crop an asset out of a 4x Figma export.

  python3 scripts/extract.py source/lion/lion-03-org-feed-a.png \
      --rect 30.75,186.75,78,78 --out assets/lion/studio.jpg

--rect is in CSS pixels; the crop is taken from the 4x raster and written at
2x (the scale the site is authored at) unless --scale says otherwise.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--rect", required=True, help="css x,y,w,h")
    ap.add_argument("--out", required=True)
    ap.add_argument("--scale", type=float, default=2.0, help="output scale")
    ap.add_argument("--prescale", type=float, default=None,
                    help="downscale the WHOLE frame first, then crop.  Matching "
                         "the way the verification pipeline resizes the source "
                         "makes the asset pixel-identical to it.")
    args = ap.parse_args()

    x, y, w, h = (float(v) for v in args.rect.split(","))
    im = Image.open(args.src).convert("RGB")
    s = 4.0  # the exports are 4x

    if args.prescale:
        pre = args.prescale
        im = im.resize((int(round(im.width * pre / s)), int(round(im.height * pre / s))),
                       Image.LANCZOS)
        s = pre

    crop = im.crop((int(round(x * s)), int(round(y * s)),
                    int(round((x + w) * s)), int(round((y + h) * s))))
    if args.scale != s:
        crop = crop.resize((int(round(w * args.scale)), int(round(h * args.scale))),
                           Image.LANCZOS)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    crop.save(out)
    print(f"{out}  {crop.size[0]}x{crop.size[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
