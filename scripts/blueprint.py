#!/usr/bin/env python3
"""
Describe a v1/v73 screen as a build blueprint: every text run with its exact
box, ink colour and background colour, plus the flat colour bands (cards,
headers, sheets) with their x/y extents.

The parent agent cannot look at images (multimodal budget spent), so this is
the substitute for seeing the design.

    python3 scripts/blueprint.py v1-search
    python3 scripts/blueprint.py v1-search --bands
    python3 scripts/blueprint.py v1-search --y0 0 --y1 400
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
RENDER = Path("/tmp/figma-render")


def hexs(rgb) -> str:
    r, g, b = (int(v) for v in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def load_1x(slug: str) -> tuple[np.ndarray, int, int]:
    """Return the source PNG downscaled to 1x css pixels."""
    if slug.startswith("v73-"):
        src = ROOT / "source/v1raw73/screens" / f"{slug}.png"
    else:
        src = ROOT / "source/v1raw/screens" / f"{slug[3:]}.png"
    im = Image.open(src).convert("RGB")
    w, h = im.size
    return np.asarray(im.resize((w // 4, h // 4), Image.LANCZOS)), w // 4, h // 4


def ocr_rows(slug: str) -> list[dict]:
    p = ROOT / "analysis" / "ocr" / f"{slug}.tsv"
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        x0, y0, x1, y1, conf, text = parts[0], parts[1], parts[2], parts[3], parts[4], "\t".join(parts[5:])
        out.append(
            {
                "x0": int(x0), "y0": int(y0), "x1": int(x1), "y1": int(y1),
                "conf": float(conf), "text": text,
            }
        )
    out.sort(key=lambda r: (r["y0"], r["x0"]))
    return out


def ink_and_bg(arr: np.ndarray, x0: int, y0: int, x1: int, y1: int):
    h, w, _ = arr.shape
    x0 = max(0, x0 - 1); y0 = max(0, y0 - 1)
    x1 = min(w, x1 + 1); y1 = min(h, y1 + 1)
    reg = arr[y0:y1, x0:x1]
    if reg.size == 0:
        return None, None
    flat = reg.reshape(-1, 3)
    lum = flat.mean(axis=1)
    bg = flat[int(np.argmax(np.bincount(lum.astype(int), minlength=256)))] if False else None
    # background = the most common colour
    cols, counts = np.unique(flat, axis=0, return_counts=True)
    bg = cols[int(np.argmax(counts))]
    # ink = the darkest 15% of pixels
    order = np.argsort(lum)
    dark = flat[order[: max(1, len(order) // 8)]]
    ink = dark.mean(axis=0)
    return ink, bg


def cards(arr: np.ndarray, tol: int = 6):
    """Find the white card rectangles: a card is a run of rows that are white
    across a wide x span, sitting on a page background of another colour."""
    h, w, _ = arr.shape
    # page background = the modal colour of the very first row
    row0 = arr[0]
    cols, counts = np.unique(row0, axis=0, return_counts=True)
    page = cols[int(np.argmax(counts))]
    # a card row: mostly white
    white = (np.abs(arr - 255).max(axis=2) <= tol)
    frac = white.mean(axis=1)
    # inside a card the left inset column (x = 20) is white for most of its height
    edge = white[:, 20] if w > 20 else white[:, 0]
    out = []
    y = 0
    while y < h:
        if edge[y]:
            s = y
            while y < h and edge[y]:
                y += 1
            if y - s > 8:
                # trim the rounded corners: the card top/bottom are ~18px in
                out.append({"y0": s, "y1": y - 1})
        else:
            y += 1
    res = []
    for c in out:
        mid = (c["y0"] + c["y1"]) // 2
        row = white[mid]
        idx = np.where(row)[0]
        if len(idx) and idx.max() - idx.min() > 100:
            res.append({**c, "x0": int(idx.min()), "x1": int(idx.max())})
    return res


def bands(arr: np.ndarray, tol: int = 18, min_len: int = 4):
    """Group rows by modal colour; report each run's y-range and x-extent."""
    h, w, _ = arr.shape
    out = []
    y = 0
    while y < h:
        row = arr[y]
        cols, counts = np.unique(row, axis=0, return_counts=True)
        modal = cols[int(np.argmax(counts))]
        m = np.abs(row.astype(int) - modal.astype(int)).max(axis=1) <= tol
        idx = np.where(m)[0]
        y2 = y
        while y2 + 1 < h:
            nxt = arr[y2 + 1]
            c2, n2 = np.unique(nxt, axis=0, return_counts=True)
            m2 = c2[int(np.argmax(n2))]
            if np.abs(modal.astype(int) - m2.astype(int)).max() > tol:
                break
            y2 += 1
        if y2 - y + 1 >= min_len:
            out.append({"y0": y, "y1": y2, "colour": hexs(modal), "x0": int(idx.min()), "x1": int(idx.max())})
        y = y2 + 1
    return out


def ink_of(arr: np.ndarray, x0: int, y0: int, x1: int, y1: int, bg):
    """Exact ink bbox inside the OCR box, plus the ink colour."""
    h, w, _ = arr.shape
    x0 = max(0, x0 - 4); y0 = max(0, y0 - 4)
    x1 = min(w, x1 + 4); y1 = min(h, y1 + 4)
    reg = arr[y0:y1, x0:x1]
    if reg.size == 0:
        return None
    bgc = np.array(bg, dtype=int)
    m = np.abs(reg - bgc).max(axis=2) > 34
    if not m.any():
        return None
    ys, xs = np.where(m)
    ink = reg[m]
    lum = ink.mean(axis=1)
    k = max(1, len(lum) // 12)
    core = ink[np.argsort(lum)[:k]].mean(axis=0)
    return (
        int(xs.min() + x0), int(ys.min() + y0), int(xs.max() + x0), int(ys.max() + y0),
        hexs(core.astype(int)),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--bands", action="store_true")
    ap.add_argument("--cards", action="store_true")
    ap.add_argument("--y0", type=int, default=0)
    ap.add_argument("--y1", type=int, default=10**6)
    ap.add_argument("--x0", type=int, default=0)
    ap.add_argument("--x1", type=int, default=10**6)
    args = ap.parse_args()

    arr, W, H = load_1x(args.slug)
    print(f"# {args.slug}  {W} x {H} css px")
    print(f"# page bg (corner): {hexs(arr[0, 0])}")

    if args.bands:
        print("\n## flat colour bands")
        for b in bands(arr):
            if b["y1"] < args.y0 or b["y0"] > args.y1:
                continue
            if b["x1"] < args.x0 or b["x0"] > args.x1:
                continue
            print(f"  y {b['y0']:5d}-{b['y1']:5d}  x {b['x0']:4d}-{b['x1']:4d}  {b['colour']}")

    if args.cards:
        print("\n## card rectangles")
        for c in cards(arr):
            print(f"  x {c['x0']:4d}-{c['x1']:4d}  y {c['y0']:5d}-{c['y1']:5d}"
                  f"  (w {c['x1']-c['x0']+1} h {c['y1']-c['y0']+1})")

    print("\n## text runs")
    rows = ocr_rows(args.slug)
    if not rows:
        print("  (no OCR file — run scripts/ocr_screen.py)")
    for r in rows:
        if r["y1"] < args.y0 or r["y0"] > args.y1:
            continue
        if r["x1"] < args.x0 or r["x0"] > args.x1:
            continue
        ink, bg = ink_and_bg(arr, r["x0"], r["y0"], r["x1"], r["y1"])
        bh = hexs(bg.astype(int)) if bg is not None else "?"
        exact = ink_of(arr, r["x0"], r["y0"], r["x1"], r["y1"], bg)
        if exact:
            ex0, ey0, ex1, ey1, icol = exact
            geo = f"x {ex0:4d}-{ex1:4d}  y {ey0:5d}-{ey1:5d}  h{ey1-ey0+1:3d}  ink {icol}"
        else:
            geo = f"x {r['x0']:4d}-{r['x1']:4d}  y {r['y0']:5d}-{r['y1']:5d}  ink ?"
        print(f"  {geo}  bg {bh}  c{r['conf']:.2f}  {r['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
