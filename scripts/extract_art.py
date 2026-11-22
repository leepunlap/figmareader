#!/usr/bin/env python3
"""
Cut a line-art / illustration out of a flat-ish background and save it as a
transparent PNG.

The mascot drawings in the v1.0 designs are black outlines on a smooth
gradient.  The gradient is reproducible in CSS, but the drawing is not, so we
ship the drawing as an asset and keep the gradient in CSS.

How it works:
  * the background of every row is estimated from the row's own pixels
    (the median colour of the pixels that are not part of the artwork),
  * the artwork's alpha is how much darker the pixel is than that estimate,
  * the artwork's colour is normalised to the darkest ink of the region.

  python3 scripts/extract_art.py source/v1raw/screens/img-1142-1.png \
      --rect 150,77,90,82 --out assets/v1/img-1142-1-mascot.png --prescale 2
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def background_estimate(img: np.ndarray) -> np.ndarray:
    """Per-row background colour: the row median of the lighter half."""
    out = np.zeros_like(img)
    h = img.shape[0]
    for y in range(h):
        row = img[y]
        lum = row.mean(axis=1)
        thr = np.percentile(lum, 70)
        light = row[lum >= thr]
        out[y] = np.median(light, axis=0)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--rect", required=True, help="css x,y,w,h")
    ap.add_argument("--out", required=True)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--prescale", type=float, default=None)
    args = ap.parse_args()

    x, y, w, h = (int(v) for v in args.rect.split(","))
    im = Image.open(args.src).convert("RGB")
    if args.prescale:
        im = im.resize(
            (int(im.width / args.prescale), int(im.height / args.prescale)),
            Image.LANCZOS,
        )
        x, y, w, h = (int(round(v / args.prescale)) for v in (x, y, w, h))
    crop = im.crop((x, y, x + w, y + h))

    a = np.asarray(crop, dtype=float)
    bg = background_estimate(a)

    # distance from the local background, normalised by the darkest pixel
    dist = np.linalg.norm(a - bg, axis=2)
    ink = a.mean(axis=2)
    ink_min = np.percentile(ink, 2)
    bg_lum = bg.mean(axis=2)
    span = np.maximum(bg_lum - ink_min, 1.0)

    alpha = np.clip(dist / (span * 1.6), 0, 1)
    alpha = np.where(ink >= bg_lum - 1.0, 0.0, alpha)
    alpha = alpha ** 0.85

    # normalise the artwork colour towards the region's darkest ink
    ink_rgb = a[ink <= ink_min + 12].mean(axis=0) if (ink <= ink_min + 12).any() else a[0, 0]
    colour = np.where(alpha[..., None] > 0.02, ink_rgb[None, None, :], a)

    out = np.dstack([colour, alpha * 255]).astype(np.uint8)
    img = Image.fromarray(out, "RGBA")
    if args.scale != 1.0:
        img = img.resize(
            (max(1, int(img.width * args.scale)), max(1, int(img.height * args.scale))),
            Image.LANCZOS,
        )
    p = Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    img.save(p)
    print(f"-> {p}  {img.size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
