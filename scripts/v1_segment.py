#!/usr/bin/env python3
"""
Segment the v1.0 / 7.3 Figma page sections into the individual phone screens.

The 7.3 page was exported as four big section images (one per coloured
section).  Each section holds a loose grid of phone screens on a flat
section background, wired together by thin annotation connector lines.

Detection is done at 1x (a 4x downscale) and the crops are taken at 4x:

  1. `content` = everything that is not the canvas grey (#EFEFEF) and not
     the annotation-panel orange (#FFB486).
  2. `body`    = `content` eroded by 5px.  That removes the 2-4px connector
     lines and the thin text strokes, so neighbouring screens stop being
     bridged into one blob.
  3. connected components of `body` -> one candidate per screen.
  4. each candidate is snapped to the true artboard edges with a 60%
     majority vote per row/column, which ignores connector lines that
     touch a screen.

The result is a manifest.json in exactly the same shape as the one for the
big v1.0 page, so scripts/render_check.py picks the screens up unchanged.

  python3 scripts/v1_segment.py --out source/v1raw73
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent.parent

GREY = np.array([239, 239, 239])
ORANGE = np.array([255, 180, 134])

SCALE = 4                 # the section exports are 4x the design grid
ERODE = 5                 # kills the thin connector lines
MAJORITY = 0.6            # fraction of the body that must carry content

SECTIONS = [
    ("source/v1raw73/活动-section.png", "activity", "活動"),
    ("source/v1raw73/我嘅-section.png", "mine", "我嘅"),
    ("source/v1raw73/比賽-section.png", "competition", "比賽"),
    ("source/v1raw73/比賽-section2.png", "competition2", "比賽"),
]


# ---------------------------------------------------------------- primitives

def background(a: np.ndarray) -> np.ndarray:
    """True where the pixel is canvas grey or annotation-panel orange."""
    return ((np.abs(a - GREY).max(axis=2) <= 10) |
            (np.abs(a - ORANGE).max(axis=2) <= 10))


def erode(mask: np.ndarray, k: int) -> np.ndarray:
    r = k // 2
    out = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out &= np.roll(np.roll(mask, dy, axis=0), dx, axis=1)
    return out


def row_runs(mask: np.ndarray):
    """Yield (y, [(x0, x1), ...]) for every row, empty rows included."""
    H, W = mask.shape
    for y in range(H):
        row = mask[y]
        d = np.diff(row.astype(np.int8))
        st = np.flatnonzero(d == 1) + 1
        en = np.flatnonzero(d == -1) + 1
        if row[0]:
            st = np.r_[0, st]
        if row[-1]:
            en = np.r_[en, W]
        yield y, [(int(s), int(e)) for s, e in zip(st, en)]


def components(mask: np.ndarray) -> list[list[int]]:
    """Connected components of a boolean mask -> [x0, y0, x1, y1, area]."""
    parent: dict[int, int] = {}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    prev: list[tuple[int, int, int]] = []
    all_runs: list[tuple[int, int, int, int]] = []
    rid = 0
    for _y, runs in row_runs(mask):
        cur = []
        for (x0, x1) in runs:
            my = rid
            rid += 1
            parent[my] = my
            all_runs.append((_y, x0, x1, my))
            for (px0, px1, prid) in prev:
                if px0 < x1 and x0 < px1:
                    ra, rb = find(my), find(prid)
                    if ra != rb:
                        parent[rb] = ra
            cur.append((x0, x1, my))
        prev = cur

    boxes: dict[int, list[int]] = {}
    for y, x0, x1, r in all_runs:
        root = find(r)
        if root not in boxes:
            boxes[root] = [x0, y, x1, y + 1, x1 - x0]
        else:
            b = boxes[root]
            b[0] = min(b[0], x0)
            b[1] = min(b[1], y)
            b[2] = max(b[2], x1)
            b[3] = max(b[3], y + 1)
            b[4] += x1 - x0
    return list(boxes.values())


def refine(content: np.ndarray, box: list[int], pad: int = 8):
    """Snap a component bbox onto the true artboard edges."""
    x0, y0, x1, y1 = box[0], box[1], box[2], box[3]
    H, W = content.shape
    ry0, ry1 = max(0, y0 - pad), min(H, y1 + pad)
    rx0, rx1 = max(0, x0 - pad), min(W, x1 + pad)
    sub = content[ry0:ry1, rx0:rx1]
    colf = sub.sum(axis=0) / max(1, y1 - y0)
    rowf = sub.sum(axis=1) / max(1, x1 - x0)
    nz = np.flatnonzero(colf >= MAJORITY)
    nzr = np.flatnonzero(rowf >= MAJORITY)
    if nz.size == 0 or nzr.size == 0:
        return (x0, y0, x1, y1)
    return (rx0 + int(nz[0]), ry0 + int(nzr[0]),
            rx0 + int(nz[-1]) + 1, ry0 + int(nzr[-1]) + 1)


# ------------------------------------------------------------------ matching

def thumb(path: Path, w: int = 32, h: int = 64) -> np.ndarray | None:
    try:
        im = Image.open(path).convert("RGB")
    except Exception:
        return None
    w0, h0 = im.size
    if w0 == 0 or h0 == 0:
        return None
    nh = max(1, int(round(h0 * w / w0)))
    im = im.resize((w, nh), Image.LANCZOS)
    a = np.asarray(im.convert("L"), dtype=np.float32)
    if a.shape[0] < h:
        a = np.pad(a, ((0, h - a.shape[0]), (0, 0)))
    a = a[:h]
    a = a - a.mean()
    n = float(np.linalg.norm(a))
    return a / n if n else None


def match_screens(ref_dir: Path, ref_manifest: list[dict], targets: list[Path]):
    """For every target screenshot return the best matching reference slug."""
    refs = []
    for row in ref_manifest:
        t = thumb(ref_dir / row["file"])
        if t is not None:
            refs.append((row["slug"], t))
    out = []
    for tgt in targets:
        t = thumb(tgt)
        if t is None or not refs:
            out.append((None, 0.0))
            continue
        best, score = None, -1.0
        for slug, r in refs:
            s = float((t * r).sum())
            if s > score:
                best, score = slug, s
        out.append((best, score))
    return out


# --------------------------------------------------------------------- main

def segment(section: Path) -> list[tuple[int, int, int, int]]:
    im = Image.open(section).convert("RGB")
    W4, H4 = im.size
    small = im.resize((W4 // SCALE, H4 // SCALE), Image.LANCZOS)
    a = np.asarray(small).astype(np.int16)
    content = ~background(a)
    body = erode(content, ERODE)

    rects = []
    for c in components(body):
        if (c[2] - c[0]) >= 150 and (c[3] - c[1]) >= 150:
            rects.append(refine(content, c))
    # drop anything that is not phone-screen shaped
    rects = [r for r in rects if 340 <= (r[2] - r[0]) <= 420 and (r[3] - r[1]) >= 300]
    # remove rects fully inside another
    rects.sort(key=lambda r: (r[1], r[0]))
    kept = []
    for r in rects:
        if any(o is not r and r[0] >= o[0] and r[2] <= o[2] and r[1] >= o[1] and r[3] <= o[3]
               for o in rects):
            continue
        kept.append(r)
    return kept


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="source/v1raw73")
    args = ap.parse_args()

    out = ROOT / args.out
    screens = out / "screens"
    screens.mkdir(parents=True, exist_ok=True)

    ref_manifest_path = ROOT / "source/v1raw/screens/manifest.json"
    ref_manifest = json.loads(ref_manifest_path.read_text(encoding="utf-8")) if ref_manifest_path.exists() else []

    manifest: list[dict] = []
    for rel, prefix, label in SECTIONS:
        section = ROOT / rel
        if not section.exists():
            print(f"!! missing {section}")
            continue
        rects = segment(section)
        print(f"{section.name}: {len(rects)} screens")
        im = Image.open(section).convert("RGB")
        for i, (x0, y0, x1, y1) in enumerate(rects, 1):
            slug = f"v73-{prefix}-{i:02d}"
            name = f"{slug}.png"
            crop = im.crop((x0 * SCALE, y0 * SCALE, x1 * SCALE, y1 * SCALE))
            crop.save(screens / name)
            manifest.append({
                "file": name,
                "slug": slug,
                "key": slug,
                "page": f"{slug}.html",
                "title": f"{label} {i:02d}",
                "css": [x1 - x0, y1 - y0],
                "px": [(x1 - x0) * SCALE, (y1 - y0) * SCALE],
                "section": prefix,
            })

    matches = match_screens(ROOT / "source/v1raw/screens", ref_manifest,
                            [screens / row["file"] for row in manifest])
    titles = {row["slug"]: row["title"] for row in ref_manifest}
    for row, (slug, score) in zip(manifest, matches):
        if slug and score >= 0.55:
            row["match"] = slug
            row["family"] = slug.split("-")[0]
            row["title"] = f"{titles.get(slug, slug)}（最初版）"
            row["score"] = round(score, 3)

    (screens / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(manifest)} screens -> {screens}")
    for row in manifest:
        m = f"  ~ {row['match']} ({row['score']})" if row.get("match") else ""
        print(f"  {row['slug']:<22} {row['css'][0]}x{row['css'][1]:<5} {row['title']}{m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
