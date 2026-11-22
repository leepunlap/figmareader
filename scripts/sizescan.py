#!/usr/bin/env python3
"""Measure the implied CJK font-size of every text element on a built screen
and compare it with the font-size declared in the page's own CSS.

CJK ideographs advance exactly 1 em in both PingFang SC and Noto Sans TC, so
the start-to-start distance of two adjacent CJK glyphs *is* the font size.
That makes it a direct, font-independent readout of the size Figma used --
no rendering required.

Usage:
    python3 scripts/sizescan.py v1-vip-membership-yearly
    python3 scripts/sizescan.py v1-... --top 30
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

# --- CJK ideograph ranges (the ones Figma sets full-width) -----------------
CJK = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3005\u3007]"
)


def load_runs(slug: str) -> list[dict]:
    """OCR runs for a screen, keyed by the file naming actually on disk."""
    for name in (f"{slug}.tsv", f"v1-{slug}.tsv", f"v73-{slug}.tsv"):
        p = ROOT / "analysis" / "ocr" / name
        if p.exists():
            rows = []
            for line in p.read_text(encoding="utf-8").splitlines():
                if not line.strip() or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) < 6:
                    continue
                try:
                    x0, y0, x1, y1, conf = (float(parts[i]) for i in range(5))
                except ValueError:
                    continue
                rows.append(
                    {"x0": x0, "y0": y0, "x1": x1, "y1": y1,
                     "conf": conf, "text": parts[5]}
                )
            return rows
    return []


def source_path(slug: str) -> Path | None:
    """Accept either the page name (v1-foo) or the bare slug (foo)."""
    bare = slug
    for pref in ("v1-", "v73-"):
        if bare.startswith(pref):
            bare = bare[len(pref):]
            break
    for base, pref in (("source/v1raw/screens", "v1"),
                       ("source/v1raw73/screens", "v73")):
        for cand in (f"{bare}.png", f"{pref}-{bare}.png"):
            p = ROOT / base / cand
            if p.exists():
                return p
    return None


def ink_columns(img: Image.Image, x0: int, y0: int, x1: int, y1: int,
                thr: int = 90) -> list[tuple[int, int]]:
    """Column runs of ink inside a region (device px)."""
    a = np.array(img.convert("RGB")).astype(int)
    reg = a[y0:y1, x0:x1]
    if reg.size == 0:
        return []
    corners = np.concatenate([reg[0, :], reg[-1, :], reg[:, 0], reg[:, -1]])
    bg = corners.mean(axis=0)
    mask = np.abs(reg - bg).sum(axis=2) > thr
    cols = mask.any(axis=0)
    runs, start = [], None
    for i, v in enumerate(cols):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start + x0, i + x0))
            start = None
    if start is not None:
        runs.append((start + x0, len(cols) + x0))
    return runs


def implied_fs(img: Image.Image, run: dict, scale: float) -> float | None:
    """Font size implied by the CJK advance inside one OCR run."""
    x0 = int(run["x0"] * scale) - 2
    y0 = int(run["y0"] * scale) - 2
    x1 = int(run["x1"] * scale) + 2
    y1 = int(run["y1"] * scale) + 2
    cols = ink_columns(img, x0, y0, x1, y1)
    if len(cols) < 2:
        return None
    # count how many CJK chars the run holds
    n_cjk = len(CJK.findall(run["text"]))
    if n_cjk < 2:
        return None
    # walk the column runs; a CJK glyph occupies ~0.92 em of ink but the
    # start-to-start pitch of two consecutive CJK glyphs is exactly 1 em.
    starts = [c[0] for c in cols]
    gaps = [starts[i + 1] - starts[i] for i in range(len(starts) - 1)]
    # the CJK pitch is the most common gap in the upper part of the run
    # (CJK glyphs come first in most labels); use the median of gaps that
    # look like a full em (>= 0.7 * max gap)
    if not gaps:
        return None
    big = [g for g in gaps if g >= 0.72 * max(gaps)]
    if not big:
        return None
    pitch = float(np.median(big))
    return pitch / scale


def declared_fonts(css_path: Path) -> list[tuple[str, float]]:
    """(selector, font-size) pairs from a stylesheet."""
    if not css_path.exists():
        return []
    out = []
    text = css_path.read_text(encoding="utf-8")
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
        sel, body = m.group(1).strip(), m.group(2)
        fs = re.search(r"font-size:\s*([\d.]+)px", body)
        if fs:
            out.append((sel, float(fs.group(1))))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    slug = args.slug
    src = source_path(slug)
    if not src:
        print(f"no source png for {slug}")
        return 1
    img = Image.open(src)
    scale = img.size[0] / 402.0 / 4.0 * 4.0 / 4.0
    # source is 4x for v1/v73 exports -> css = device / 4
    scale = 4.0

    runs = load_runs(slug)
    if not runs:
        print(f"no OCR runs for {slug}")
        return 1

    rows = []
    for r in runs:
        if r["conf"] < 0.9:
            continue
        fs = implied_fs(img, r, scale)
        if fs is None or fs < 6 or fs > 60:
            continue
        rows.append({"text": r["text"], "implied_fs": round(fs, 1),
                     "y0": r["y0"], "x0": r["x0"]})

    rows.sort(key=lambda r: -r["implied_fs"])
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0

    print(f"{slug}: {len(rows)} runs with a measurable CJK pitch")
    print(f"{'implied fs':>10}  {'x':>6} {'y':>6}  text")
    for r in rows[: args.top]:
        print(f"{r['implied_fs']:10.1f}  {r['x0']:6.0f} {r['y0']:6.0f}  {r['text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
