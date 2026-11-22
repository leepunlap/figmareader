#!/usr/bin/env python3
"""
Break a screen's pixel diff down into horizontal bands so the biggest
contributors can be ranked.

  python3 scripts/diff_bands.py home
  python3 scripts/diff_bands.py home --rows 40
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RENDER = Path("/tmp/figma-render")

SCREENS = {
    "home": ("home.png", 1196),
    "list-020": ("list-020.png", 1074),
    "list-023": ("list-023.png", 1032),
    "list-027": ("list-027.png", 990),
    "lion-01": ("lion-01-activity-feed.png", 874),
    "lion-02": ("lion-02-activity-filter.png", 874),
    "lion-03": ("lion-03-org-feed-a.png", 848),
    "lion-04": ("lion-04-org-feed-b.png", 848),
    "lion-05": ("lion-05-org-filter.png", 848),
    "lion-06": ("lion-06-org-detail-lionsclub.png", 1428),
    "lion-07": ("lion-07-event-detail-rosewood.png", 1918),
    "lion-08": ("lion-08-chat-1.png", 928),
    "lion-09": ("lion-09-org-detail-lionshk.png", 1428),
    "lion-10": ("lion-10-event-detail-lionshk.png", 1918),
    "lion-11": ("lion-11-chat-2.png", 928),
}


def main() -> int:
    screen = sys.argv[1] if len(sys.argv) > 1 else "home"
    rows = 40
    if "--rows" in sys.argv:
        rows = int(sys.argv[sys.argv.index("--rows") + 1])

    src_name, height = SCREENS[screen]
    a = np.asarray(Image.open(RENDER / f"{screen}.png").convert("RGB")).astype(np.int16)
    src_path = ROOT / "source" / src_name
    if not src_path.exists():
        src_path = ROOT / "source" / "lion" / src_name
    if not src_path.exists():
        man = json.loads((ROOT / "source" / "lion" / "frames.json").read_text())
        hit = [m for m in man if m["name"] == src_name[:-4]]
        if hit:
            src_path = ROOT / "source" / "lion" / hit[0]["file"]
    b = np.asarray(Image.open(src_path).convert("RGB")).astype(np.int16)
    if a.shape != b.shape:
        b = np.asarray(
            Image.open(src_path).convert("RGB").resize((a.shape[1], a.shape[0]), Image.LANCZOS)
        ).astype(np.int16)

    d = np.abs(a - b).sum(axis=2)
    hot = d > 24
    per = hot.shape[0] // 2
    print(f"{screen}: total diff {hot.mean() * 100:.2f}%   (bands of {rows} css px)\n")
    print(f"  {'css y':>12s} {'diff %':>8s}  hot x-ranges")
    rows_out = []
    for i in range(0, per, rows):
        band = hot[i * 2:(i + rows) * 2]
        if band.size == 0:
            continue
        pct = band.mean() * 100
        if pct < 0.05:
            continue
        colsum = band.mean(axis=0)
        idx = np.where(colsum > 0.02)[0]
        ranges = []
        if len(idx):
            start = idx[0]
            prev = idx[0]
            for x in idx[1:]:
                if x - prev > 8:
                    ranges.append((start / 2, prev / 2))
                    start = x
                prev = x
            ranges.append((start / 2, prev / 2))
        rtxt = " ".join(f"{s:.0f}-{e:.0f}" for s, e in ranges[:8])
        rows_out.append((i, pct, rtxt))
    for i, pct, rtxt in sorted(rows_out, key=lambda r: -r[1]):
        print(f"  {i:5d}-{i + rows:5d} {pct:7.2f}%  {rtxt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
