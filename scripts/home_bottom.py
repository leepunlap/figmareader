#!/usr/bin/env python3
"""
Cut the bottom artwork out of a home screen export.

The bottom of the home screens is a white navigation bar with a mascot
illustration, a speech bubble and four line icons.  The bubble carries a
label, so its text is painted out and re-drawn as real HTML text.

    python3 scripts/home_bottom.py v1-home-1
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ROOT = Path(__file__).resolve().parent.parent

# css rects: name -> x, y, w, h
PIECES = {
    "mascot": (150, 814, 90, 94),
    "bubble": (225, 797, 80, 46),
    "nav1": (35, 860, 25, 26),
    "nav2": (102, 858, 26, 28),
    "nav3": (262, 858, 26, 28),
    "nav4": (331, 858, 25, 26),
}


def main() -> int:
    slug = sys.argv[1]
    src = ROOT / "source/v1raw/screens" / f"{slug[3:]}.png"
    im = Image.open(src).convert("RGB")
    half = im.resize((im.width // 2, im.height // 2), Image.LANCZOS)

    for name, (x, y, w, h) in PIECES.items():
        crop = half.crop((x * 2, y * 2, (x + w) * 2, (y + h) * 2))
        a = np.asarray(crop).copy()
        if name == "bubble":
            # paint the label out: the bubble interior is a flat white
            inside = a[12:28, 16:80]
            fill = np.median(inside.reshape(-1, 3), axis=0)
            a[30:60, 20:140] = fill
            crop = Image.fromarray(a)
        out = ROOT / "assets/v1" / f"{slug[3:]}-{name}.png"
        crop.save(out)
        print(out, crop.size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
