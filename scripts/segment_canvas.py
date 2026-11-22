#!/usr/bin/env python3
"""
Segment an exported Figma page canvas into individual frames.

The bulk export writes one large PNG of the whole page (e.g. "Aimeee 2026 OCT.png"
at 4x).  Frames sit on a flat page background (#F5F5F5) in a loose grid.

Row/column projection alone is not enough: the frames in one visual row have
different heights, so global gutters slice through them.  Instead this does a
real connected-component pass (row-run union-find, pure numpy + python) over
the ink mask, then keeps the components that look like phone screens.

  python3 scripts/segment_canvas.py source/"Aimeee 2026 OCT.png" --out source/lion

Writes one cropped PNG per frame plus frames.json with the geometry.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

BG = (245, 245, 245)   # exact page background colour; white cards inside a
BG_TOL = 3            # frame are NOT background, so frames stay connected


class UF:
    def __init__(self) -> None:
        self.p: list[int] = []

    def make(self) -> int:
        self.p.append(len(self.p))
        return len(self.p) - 1

    def find(self, a: int) -> int:
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("canvas")
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-w", type=int, default=700)
    ap.add_argument("--min-h", type=int, default=700)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    src = Image.open(args.canvas)
    rgb = src.convert("RGB")
    a = np.asarray(rgb)
    H, W = a.shape[:2]
    bgc = np.array(BG, dtype=np.int16)
    mask = (np.abs(a.astype(np.int16) - bgc).max(axis=2) > BG_TOL)

    # --- connected components via run-length union-find -------------------
    uf = UF()
    runs: list[tuple[int, int, int, int]] = []   # (y, x0, x1, run_id)
    prev: list[tuple[int, int, int]] = []

    for y in range(H):
        row = mask[y]
        if not row.any():
            prev = []
            continue
        d = np.diff(row.astype(np.int8))
        starts = (np.flatnonzero(d == 1) + 1).tolist()
        ends = (np.flatnonzero(d == -1) + 1).tolist()
        if row[0]:
            starts.insert(0, 0)
        if row[-1]:
            ends.append(W)

        cur = []
        for x0, x1 in zip(starts, ends):
            rid = uf.make()
            runs.append((y, x0, x1, rid))
            for pid, px0, px1 in prev:
                if px0 < x1 and x0 < px1:
                    uf.union(rid, pid)
            cur.append((rid, x0, x1))
        prev = cur

    boxes: dict[int, list[int]] = {}
    for y, x0, x1, rid in runs:
        r = uf.find(rid)
        if r not in boxes:
            boxes[r] = [x0, y, x1, y + 1]
        b = boxes[r]
        b[0] = min(b[0], x0)
        b[1] = min(b[1], y)
        b[2] = max(b[2], x1)
        b[3] = max(b[3], y + 1)

    keep = [b for b in boxes.values()
            if (b[2] - b[0]) >= args.min_w and (b[3] - b[1]) >= args.min_h]
    keep.sort(key=lambda b: (b[1], b[0]))
    print(f"{len(boxes)} components, {len(keep)} look like frames")

    manifest = []
    for i, (x0, y0, x1, y1) in enumerate(keep, 1):
        name = f"frame-{i:02d}.png"
        rgb.crop((x0, y0, x1, y1)).save(out / name)
        manifest.append({
            "file": name,
            "px": [x0, y0, x1, y1],
            "size": [x1 - x0, y1 - y0],
            "pt": [round((x1 - x0) / 4, 2), round((y1 - y0) / 4, 2)],
        })
        print(f"{name}  {x1-x0}x{y1-y0}px = {round((x1-x0)/4,1)}x{round((y1-y0)/4,1)}pt @({x0},{y0})")

    (out / "frames.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\n{len(manifest)} frames -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
