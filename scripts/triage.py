#!/usr/bin/env python3
"""Split a screen's pixel diff into "text" and "everything else".

Text rows have a hard floor: the export is a 4x raster that gets LANCZOS
downscaled, Chrome rasterises natively at 2x, and even with identical glyph
geometry the two disagree on most edge pixels.  A screen whose diff sits
almost entirely inside text rows cannot be improved much further with static
HTML and CSS; a screen whose diff also shows up on cards, gradients or
images can.

This tool prints, per screen, how much of the diff falls inside the OCR text
rows and how much does not.

  python3 scripts/triage.py --all
  python3 scripts/triage.py v1-competition-detail-closed v1-home
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-render")


def source_png(slug: str) -> Path:
    if slug.startswith("v73-"):
        return ROOT / "source/v1raw73/screens" / f"{slug}.png"
    return ROOT / "source/v1raw/screens" / f"{slug[3:]}.png"


def text_mask(slug: str, h: int, w: int) -> np.ndarray | None:
    """Mask of the text rows, in device pixels (2x)."""
    mask = np.zeros((h * 2, w * 2), dtype=bool)
    md = ROOT / "analysis/ocr" / f"{slug}.md"
    boxes = []
    if md.exists():
        for line in md.read_text(encoding="utf-8").splitlines():
            if not line.startswith("|") or "---" in line or "x0" in line:
                continue
            parts = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(parts) < 4:
                continue
            try:
                boxes.append(tuple(int(parts[i]) for i in range(4)))
            except ValueError:
                continue
    else:
        fit = ROOT / "analysis/ocr" / f"{slug}-fit.json"
        if not fit.exists():
            return None
        for r in json.load(open(fit)):
            boxes.append((int(r["src_x0"]), int(r["src_y0"]), int(r["src_x1"]), int(r["src_y1"])))
    if not boxes:
        return None
    for (x0, y0, x1, y1) in boxes:
        y0 = max(0, y0 - 4); y1 = min(h, y1 + 4)
        x0 = max(0, x0 - 4); x1 = min(w, x1 + 4)
        if y1 <= y0 or x1 <= x0:
            continue
        mask[y0 * 2:y1 * 2, x0 * 2:x1 * 2] = True
    return mask


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="*")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    if args.all:
        slugs = sorted(p.stem for p in WORK.glob("*.png") if not p.name.endswith("-diff.png"))
    else:
        slugs = args.slugs

    rows = []
    for slug in slugs:
        ren_p = WORK / f"{slug}.png"
        src_p = source_png(slug)
        if not ren_p.exists() or not src_p.exists():
            continue
        ren = Image.open(ren_p).convert("RGB")
        src = Image.open(src_p).convert("RGB")
        if ren.size != src.size:
            src = src.resize(ren.size, Image.LANCZOS)
        h, w = ren.size[1], ren.size[0]
        d = (np.abs(np.asarray(ren).astype(int) - np.asarray(src).astype(int)).sum(axis=2) > 24)
        total = d.sum()
        pct = total / d.size * 100
        m = text_mask(slug, h // 2, w // 2)
        if m is None:
            rows.append((pct, 0.0, 0.0, slug))
            continue
        mm = m[:d.shape[0], :d.shape[1]]
        in_text = (d & mm).sum()
        rows.append((pct, in_text / max(1, total) * 100, (total - in_text) / max(1, total) * 100, slug))

    rows.sort(reverse=True)
    print("%7s %8s %8s  %s" % ("diff %", "text %", "other %", "screen"))
    for pct, t, o, slug in rows:
        print("%6.2f%% %7.1f%% %7.1f%%  %s" % (pct, t, o, slug))


if __name__ == "__main__":
    main()
