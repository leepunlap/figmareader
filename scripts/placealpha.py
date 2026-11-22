#!/usr/bin/env python3
"""Find where a transparent PNG asset sits inside its export.

`place.py` compares RGB, which breaks for cut-outs that carry an alpha
channel: the transparent pixels become black and never match.  This variant
only compares the pixels that are actually opaque in the asset, so a
line-art illustration or a mascot can be located reliably.

The search is coarse-to-fine: a cheap 1x-css pass finds the neighbourhood and
a 2x-css pass refines it, so it stays fast even on a 1659 css tall screen.

    python3 scripts/placealpha.py v1-home-2 assets/v1/home-2-ill1.png
    python3 scripts/placealpha.py v1-home-2 assets/v1/home-2-bottom.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent.parent


def source_png(slug: str) -> Path:
    if slug.startswith("v73-"):
        return ROOT / "source/v1raw73/screens" / f"{slug}.png"
    return ROOT / "source/v1raw/screens" / f"{slug[3:]}.png"


def score(src: np.ndarray, asset: np.ndarray, mask: np.ndarray, x: int, y: int) -> float:
    h, w = mask.shape
    reg = src[y:y + h, x:x + w]
    if reg.shape[0] != h or reg.shape[1] != w:
        return 9e9
    d = np.abs(reg - asset).sum(axis=2)
    return float((d[mask] > 24).mean())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("asset")
    ap.add_argument("--alpha", type=int, default=200, help="minimum alpha to count as opaque")
    ap.add_argument("--tolerance", type=int, default=24)
    args = ap.parse_args()

    src_im = Image.open(source_png(args.slug)).convert("RGB")
    ast_im = Image.open(args.asset).convert("RGBA")

    # ---- coarse pass at 1x css -------------------------------------------
    s1 = np.asarray(src_im.resize((src_im.width // 4, src_im.height // 4), Image.LANCZOS)).astype(np.int16)
    a1 = np.asarray(ast_im.resize((max(1, ast_im.width // 2), max(1, ast_im.height // 2)), Image.LANCZOS)).astype(np.int16)
    m1 = a1[:, :, 3] >= args.alpha
    if m1.sum() < 40:
        print("[error] the asset has almost no opaque pixels")
        return 1
    if a1.shape[0] > s1.shape[0] or a1.shape[1] > s1.shape[1]:
        print("[error] the asset is larger than the export")
        return 1

    best = (9e9, 0, 0)
    for y in range(0, s1.shape[0] - a1.shape[0] + 1):
        for x in range(0, s1.shape[1] - a1.shape[1] + 1):
            v = score(s1, a1[:, :, :3], m1, x, y)
            if v < best[0]:
                best = (v, x, y)
    cx, cy = best[1], best[2]

    # ---- fine pass at 2x css ---------------------------------------------
    s2 = np.asarray(src_im.resize((src_im.width // 2, src_im.height // 2), Image.LANCZOS)).astype(np.int16)
    a2 = np.asarray(ast_im).astype(np.int16)
    m2 = a2[:, :, 3] >= args.alpha
    ah, aw = m2.shape
    fx, fy = cx * 2, cy * 2
    best2 = (9e9, fx, fy)
    for y in range(max(0, fy - 12), min(s2.shape[0] - ah, fy + 12) + 1):
        for x in range(max(0, fx - 12), min(s2.shape[1] - aw, fx + 12) + 1):
            v = score(s2, a2[:, :, :3], m2, x, y)
            if v < best2[0]:
                best2 = (v, x, y)
    v, x, y = best2

    print(f"{Path(args.asset).name}: match {v * 100:.2f}%  "
          f"css left {x / 2:.2f} top {y / 2:.2f}  size {aw / 2:.1f} x {ah / 2:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
