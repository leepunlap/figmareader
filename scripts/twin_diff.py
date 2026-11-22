#!/usr/bin/env python3
"""
Compare a 7.3 screen with its v1.0 twin, band by band.

When a 7.3 artboard is a near-copy of a v1.0 artboard we clone the v1.0 page.
That only works if the *design* is the same, so this script shows where the
two exports disagree.  A band that differs in the exports but matches in the
render is a band we must re-lay-out; a band that differs in both is either a
design difference or plain anti-aliasing noise.

    python3 scripts/twin_diff.py v73-competition-01
    python3 scripts/twin_diff.py v73-competition-01 --band 40
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent.parent


def load(p: Path) -> np.ndarray:
    return np.asarray(Image.open(p).convert("RGB")).astype(np.int16)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--band", type=int, default=50, help="band height in css px")
    args = ap.parse_args()

    slug = args.slug
    m73 = {r["slug"]: r for r in json.loads(
        (ROOT / "source/v1raw73/screens/manifest.json").read_text(encoding="utf-8"))}
    m1 = {r["slug"]: r for r in json.loads(
        (ROOT / "source/v1raw/screens/manifest.json").read_text(encoding="utf-8"))}

    row = m73[slug]
    twin = row.get("match")
    if not twin:
        print(f"[error] {slug} has no v1 twin")
        return 1

    a = load(ROOT / "source/v1raw73/screens" / row["file"])
    b = load(ROOT / "source/v1raw/screens" / m1[twin]["file"])
    h = min(a.shape[0], b.shape[0])
    w = min(a.shape[1], b.shape[1])
    a, b = a[:h, :w], b[:h, :w]

    hot = np.abs(a - b).sum(axis=2) > 24
    css_w = row["css"][0]
    scale = w / css_w
    print(f"{slug}  vs  v1-{twin}   export {w}x{h}  css {row['css']}")
    print(f"total export diff {hot.mean() * 100:.2f}%")

    step = max(1, int(args.band * scale))
    rows = []
    for i in range(0, hot.shape[0], step):
        seg = hot[i:i + step]
        if seg.size:
            rows.append((i / scale, float(seg.mean() * 100)))
    rows.sort(key=lambda r: -r[1])
    for y, pct in rows[:14]:
        if pct < 0.4:
            break
        print(f"  y={y:7.0f} {pct:6.2f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
