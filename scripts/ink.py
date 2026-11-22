#!/usr/bin/env python3
"""
Measure "ink coverage" (how much of a text box is actually covered by glyph
pixels) for a region, so the rendered type weight can be compared numerically
against the Figma export.

  python3 scripts/ink.py list-020

Compares source/<screen>.png (4x export, downscaled to the render scale) with
/tmp/figma-render/<screen>.png (2x render).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RENDER = Path("/tmp/figma-render")

# label -> css rect (x, y, w, h)
REGIONS = {
    "list-020": {
        "card1 title": (93, 458, 200, 20),
        "card1 desc":  (93, 479, 260, 20),
        "card2 title": (93, 528, 220, 20),
        "card2 desc":  (93, 549, 260, 20),
        "banner title": (20, 250, 240, 32),
        "banner meta":  (30, 288, 160, 20),
        "progress label": (20, 360, 120, 20),
        "section title": (49, 408, 180, 26),
    },
    "home": {
        "hero age":   (20, 46, 120, 20),
        "hero title": (20, 76, 240, 32),
        "hero lede":  (20, 320, 140, 54),
        "section title": (82, 426, 260, 28),
        "section lede":  (82, 460, 290, 56),
        "caption":    (100, 592, 200, 22),
        "card1 title": (69, 640, 140, 20),
        "card1 text":  (69, 658, 140, 40),
    },
}


def load(path: Path, scale: int | None = None) -> tuple[np.ndarray, int]:
    img = Image.open(path).convert("RGB")
    if scale is None:
        scale = img.width // 390
    if img.width != 390 * scale:
        img = img.resize((390 * scale, round(img.height * scale / (img.width / 390))), Image.LANCZOS)
    return np.asarray(img).astype(np.int16), scale


def ink(patch: np.ndarray) -> float:
    """fraction of pixels that differ noticeably from the local background"""
    flat = patch.reshape(-1, 3)
    keys = (flat[:, 0].astype(np.int32) << 16) | (flat[:, 1].astype(np.int32) << 8) | flat[:, 2].astype(np.int32)
    vals, counts = np.unique(keys, return_counts=True)
    k = int(vals[np.argmax(counts)])
    bg = np.array([(k >> 16) & 0xFF, (k >> 8) & 0xFF, k & 0xFF])
    return float((np.abs(patch - bg).sum(axis=2) > 26).mean()) * 100


def main() -> int:
    screens = sys.argv[1:] or list(REGIONS)
    for screen in screens:
        src, _ = load(ROOT / "source" / f"{screen}.png")
        ren, _ = load(RENDER / f"{screen}.png")
        print(f"\n===== {screen} =====   ink coverage %  (source vs render)")
        print(f"  {'region':16s} {'source':>8s} {'render':>8s} {'delta':>8s}")
        for label, (x, y, w, h) in REGIONS[screen].items():
            s = ink(src[y * 4 : (y + h) * 4, x * 4 : (x + w) * 4])
            r = ink(ren[y * 2 : (y + h) * 2, x * 2 : (x + w) * 2])
            print(f"  {label:16s} {s:7.2f}% {r:7.2f}% {r - s:+7.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
