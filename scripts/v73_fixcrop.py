#!/usr/bin/env python3
"""
Audit the 7.3 screen crops against their v1.0 twins.

The 7.3 page was exported per *section*.  The segmenter snapped to the
artboard edges of a loose grid, and on some screens it snapped 4 device px
(1 css px) too high.  The crop then contains one extra row above the artboard
and every element sits one css px too low, which a pixel comparison reads as
a completely different screen.

For every screen that has a v1.0 twin this finds the integer device-pixel
offset that best aligns the two exports.  `--fix` rewrites the crop and the
manifest entry.

    python3 scripts/v73_fixcrop.py --audit
    python3 scripts/v73_fixcrop.py --fix --only v73-competition-0
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


def load(p: Path, scale: int = 2) -> np.ndarray:
    im = Image.open(p).convert("RGB")
    if scale != 1:
        im = im.resize((im.width // scale, im.height // scale), Image.LANCZOS)
    return np.asarray(im).astype(np.int16)


def best_shift(a: np.ndarray, b: np.ndarray, rng: int = 5):
    h, w = a.shape[:2]
    best = None
    for dy in range(-rng, rng + 1):
        for dx in range(-rng, rng + 1):
            ys0, ys1 = max(0, -dy), min(h, h - dy)
            xs0, xs1 = max(0, -dx), min(w, w - dx)
            if ys1 - ys0 < 40 or xs1 - xs0 < 40:
                continue
            pa = a[ys0:ys1, xs0:xs1]
            pb = b[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx]
            pct = float((np.abs(pa - pb).sum(axis=2) > 24).mean() * 100)
            if best is None or pct < best[2]:
                best = (dy, dx, pct)
    return best


def twin_of(slug: str, m1: dict) -> str | None:
    m73 = {r["slug"]: r for r in json.loads(
        (ROOT / "source/v1raw73/screens/manifest.json").read_text(encoding="utf-8"))}
    row = m73.get(slug)
    if not row:
        return None
    mt = row.get("match")
    return mt if mt and mt in m1 else None


def audit(only: str | None) -> list[tuple[str, str, int, int, float, float]]:
    m73 = json.loads((ROOT / "source/v1raw73/screens/manifest.json").read_text(encoding="utf-8"))
    m1 = {r["slug"]: r for r in json.loads(
        (ROOT / "source/v1raw/screens/manifest.json").read_text(encoding="utf-8"))}
    out = []
    for row in m73:
        slug = row["slug"]
        if only and only not in slug:
            continue
        mt = row.get("match")
        if not mt or mt not in m1:
            continue
        a = load(ROOT / "source/v1raw73/screens" / row["file"], 2)
        b = load(ROOT / "source/v1raw/screens" / m1[mt]["file"], 2)
        h = min(a.shape[0], b.shape[0])
        w = min(a.shape[1], b.shape[1])
        a, b = a[:h, :w], b[:h, :w]
        dy, dx, pct = best_shift(a, b)
        base = float((np.abs(a - b).sum(axis=2) > 24).mean() * 100)
        out.append((slug, mt, dy * 2, dx * 2, base, pct))
        flag = "  <-- SHIFT" if (dy or dx) else ""
        print(f"{slug:26s} vs v1-{mt:26s} dy={dy * 2:+3d} dx={dx * 2:+3d}"
              f"  base {base:6.2f}%  aligned {pct:6.2f}%{flag}")
    return out


def fix(only: str | None) -> int:
    m73p = ROOT / "source/v1raw73/screens/manifest.json"
    m73 = json.loads(m73p.read_text(encoding="utf-8"))
    m1 = {r["slug"]: r for r in json.loads(
        (ROOT / "source/v1raw/screens/manifest.json").read_text(encoding="utf-8"))}
    changed = 0
    for row in m73:
        slug = row["slug"]
        if only and only not in slug:
            continue
        mt = row.get("match")
        if not mt or mt not in m1:
            continue
        p73 = ROOT / "source/v1raw73/screens" / row["file"]
        p1 = ROOT / "source/v1raw/screens" / m1[mt]["file"]
        a = load(p73, 2)
        b = load(p1, 2)
        h = min(a.shape[0], b.shape[0])
        w = min(a.shape[1], b.shape[1])
        dy, dx, _ = best_shift(a[:h, :w], b[:h, :w])
        if not dy and not dx:
            continue
        full = Image.open(p73).convert("RGB")
        sy, sx = -dy * 2, -dx * 2
        W, H = full.size
        # crop with the corrected origin, keeping the twin's extent
        left = max(0, sx)
        top = max(0, sy)
        right = min(W, left + b.shape[1] * 2)
        bottom = min(H, top + b.shape[0] * 2)
        fixed = full.crop((left, top, right, bottom))
        fixed.save(p73)
        row["px"] = [fixed.width, fixed.height]
        row["css"] = [fixed.width // 4, fixed.height // 4]
        print(f"fixed {slug}: was {W}x{H} -> {fixed.width}x{fixed.height} "
              f"(css {row['css']}), shift dy={sy} dx={sx}")
        changed += 1
    m73p.write_text(json.dumps(m73, ensure_ascii=False, indent=1), encoding="utf-8")
    return changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--only", default=None)
    args = ap.parse_args()
    if args.fix:
        n = fix(args.only)
        print(f"fixed {n} screens")
        return 0
    audit(args.only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
