#!/usr/bin/env python3
"""Make the background of a cut-out asset transparent.

Some illustrations are cut out of a screen as a plain rectangle, so they still
carry the background they were sitting on.  When the artwork is then placed on
a coloured card the old background shows up as a white box.  This tool floods
the near-white background away from the edges and keeps the ink.

    python3 scripts/knockout.py assets/v1/home-2-ill2.png
    python3 scripts/knockout.py assets/v1/x.png --threshold 240
"""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image


def knockout(src: Path, dst: Path, thresh: int = 238) -> tuple[int, int]:
    im = Image.open(src).convert("RGB")
    a = np.asarray(im).astype(np.int16)
    h, w, _ = a.shape
    white = a.min(axis=2) >= thresh

    out = np.zeros((h, w), dtype=bool)
    dq: deque[tuple[int, int]] = deque()
    for x in range(w):
        for y in (0, h - 1):
            if white[y, x] and not out[y, x]:
                out[y, x] = True
                dq.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if white[y, x] and not out[y, x]:
                out[y, x] = True
                dq.append((y, x))

    while dq:
        y, x = dq.popleft()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h and 0 <= nx < w and white[ny, nx] and not out[ny, nx]:
                out[ny, nx] = True
                dq.append((ny, nx))

    alpha = np.where(out, 0, 255).astype(np.uint8)
    rgba = np.concatenate([a.astype(np.uint8), alpha[:, :, None]], axis=2)
    Image.fromarray(rgba, "RGBA").save(dst)
    return int(out.sum()), w * h


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--out", default=None)
    ap.add_argument("--threshold", type=int, default=238)
    args = ap.parse_args()

    src = Path(args.src)
    dst = Path(args.out) if args.out else src
    cleared, total = knockout(src, dst, args.threshold)
    print(f"{src.name}: cleared {cleared}/{total} px ({cleared / total * 100:.1f}%) -> {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
