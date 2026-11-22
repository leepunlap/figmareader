#!/usr/bin/env python3
"""
Check every OCR text line of a screen against the export.

The page fitter solved each line's font size from the line's *ink* width.
That breaks when the OCR text of a line is truncated - the ink looks
narrower, so the fitter inflates the size and then adds letter-spacing to
make the line reach the right edge again.  Two independent measurements
expose that:

  * the CJK advance (distance between two glyph centres) is exactly 1 em
    for full-width glyphs, so  advance = font-size + letter-spacing
  * the ink height of a dense CJK glyph scales with the font size alone,
    so  ink height ratio = font-size ratio

Comparing both tells you the real font size and the real letter-spacing.

  python3 scripts/advcheck.py v1-quota-exhausted-ssvip
  python3 scripts/advcheck.py v1-home --all
  python3 scripts/advcheck.py v1-home --min 1200 --max 1700
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT / "scripts"))
from render_check import WIDTHS  # noqa: E402
CJK = re.compile(r"[一-鿿]")


def source_for(page: str) -> Path:
    stem = page[:-5] if page.endswith(".html") else page
    cand = ROOT / "source/v1raw73/screens" / f"{stem}.png"
    if cand.exists():
        return cand
    return ROOT / "source/v1raw/screens" / f"{stem.removeprefix('v1-')}.png"


def runs_from(mask: np.ndarray) -> list[tuple[int, int]]:
    prof = mask.sum(axis=0)
    out, cur = [], None
    for i, v in enumerate(prof):
        if v > 0 and cur is None:
            cur = i
        elif v == 0 and cur is not None:
            out.append((cur, i - 1))
            cur = None
    if cur is not None:
        out.append((cur, len(prof) - 1))
    return out


def mode(v: list[float]) -> float:
    if not v:
        return 0.0
    u, c = np.unique(np.round(v, 1), return_counts=True)
    return float(u[c.argmax()])


def ink_of(A: np.ndarray, r0: int, r1: int, c0: int, c1: int):
    """Ink geometry of a rect: per-glyph runs, ink box."""
    band = A[r0:r1, c0:c1]
    if band.size == 0:
        return None
    g = band.min(axis=2)
    vals, counts = np.unique(g, return_counts=True)
    bg = int(vals[counts.argmax()])
    mask = np.abs(g.astype(int) - bg) > 40
    if not mask.any():
        return None
    ys, xs = np.nonzero(mask)
    runs = runs_from(mask)
    mid = [(a + b) / 2.0 for a, b in runs]
    adv = [mid[i + 1] - mid[i] for i in range(len(mid) - 1)]
    return {"adv": adv, "ink_h": ys.max() - ys.min() + 1,
            "ink_w": xs.max() - xs.min() + 1, "runs": len(runs)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("page")
    ap.add_argument("--src", default="")
    ap.add_argument("--render", default="")
    ap.add_argument("--min", type=float, default=0.0, help="css y lower bound")
    ap.add_argument("--max", type=float, default=1e9, help="css y upper bound")
    ap.add_argument("--all", action="store_true", help="report every line")
    args = ap.parse_args()

    stem = args.page[:-5] if args.page.endswith(".html") else args.page
    src_path = Path(args.src) if args.src else source_for(args.page)
    ren_path = Path(args.render) if args.render else Path(f"/tmp/figma-render/{stem}.png")
    tsv = ROOT / "analysis/ocr" / f"{stem}.tsv"
    if not ren_path.exists():
        raise SystemExit(f"[error] no render at {ren_path}; run render_check first")
    if not tsv.exists():
        raise SystemExit(f"[error] no OCR at {tsv}")

    S = np.asarray(Image.open(src_path).convert("RGB")).astype(int)
    R = np.asarray(Image.open(ren_path).convert("RGB")).astype(int)
    # the artboard is not always 390 css wide (375 / 390 / 402 / 403 / 404)
    width = WIDTHS.get(stem, 390)
    ss = S.shape[1] / width
    rs = R.shape[1] / width
    print(f"source {src_path.name} ({S.shape[1]}px, {ss:g}x)   "
          f"render {ren_path.name} ({R.shape[1]}px, {rs:g}x)")

    print(f"{'css y':>13} {'srcAdv':>7} {'renAdv':>7} {'srcH':>6} {'renH':>6} "
          f"{'size x':>7}  text")
    for line in tsv.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        x1, y1, x2, y2 = (float(v) for v in parts[:4])
        x, y, w, h = x1, y1, x2 - x1, y2 - y1
        text = parts[5].strip()
        if not text or len(CJK.findall(text)) < 3:
            continue
        if y < args.min or y > args.max:
            continue
        # source rect, in css, padded a little
        sx0, sy0 = int((x - 2) * ss), int((y - 4) * ss)
        sx1, sy1 = int((x + w + 2) * ss), int((y + h + 4) * ss)
        rx0, ry0 = int((x - 2) * rs), int((y - 4) * rs)
        rx1, ry1 = int((x + w + 2) * rs), int((y + h + 4) * rs)
        sb = ink_of(S, sy0, sy1, sx0, sx1)
        rb = ink_of(R, ry0, ry1, rx0, rx1)
        if not sb or not rb:
            continue
        s_adv = mode(sb["adv"]) / ss
        r_adv = mode(rb["adv"]) / rs
        s_h = sb["ink_h"] / ss
        r_h = rb["ink_h"] / rs
        if s_h <= 0 or r_h <= 0 or s_adv <= 0 or r_adv <= 0:
            continue
        ratio = s_h / r_h
        adv_ratio = s_adv / r_adv
        note = ""
        if abs(ratio - 1) > 0.015:
            note = f"SIZE x{ratio:.3f}"
            if abs(adv_ratio - ratio) > 0.015:
                note += f"  adv x{adv_ratio:.3f}"
        if not args.all and not note:
            continue
        print(f"{y:6.0f}..{y + h:6.0f} {s_adv:7.2f} {r_adv:7.2f} "
              f"{s_h:6.2f} {r_h:6.2f} {ratio:7.3f}  {note}  {text[:24]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
