#!/usr/bin/env python3
"""
Parent-side render + diff in a private work directory.

scripts/render_check.py and scripts/bandfit.py both write into
/tmp/figma-render, which the background measurement and the parallel
workers also use.  This tool keeps its own directory so the parent can
inspect a screen while everything else is running.

  python3 scripts/prender.py v1-competition-detail-open
  python3 scripts/prender.py v1-home --hot 25
  python3 scripts/prender.py v1-home --hot 25 --grid

It prints the overall diff, the hottest horizontal bands (css px), and a
coarse grid map of where the differences are.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/parent-render")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

sys.path.insert(0, str(ROOT / "scripts"))
from render_check import SCREENS, WIDTHS, HEIGHTS  # noqa: E402


def prepare(page: str) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    html = (ROOT / page).read_text(encoding="utf-8")
    html = html.replace("<body>", '<body class="render">')
    html = html.replace("<head>", f'<head>\n<base href="file://{ROOT}/">', 1)
    out = WORK / page
    out.write_text(html, encoding="utf-8")
    return out


def shoot(page: str, height: int, width: int, scale: int = 2) -> Path:
    out = WORK / page.replace(".html", ".png")
    profile = WORK / f"profile-{os.getpid()}"
    if profile.exists():
        shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    cmd = [
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--no-first-run", "--no-default-browser-check", "--disable-extensions",
        "--allow-file-access-from-files",
        "--force-device-scale-factor=%d" % scale,
        "--virtual-time-budget=12000",
        "--user-data-dir=%s" % profile,
        "--window-size=%d,%d" % (width, height),
        "--screenshot=%s" % out,
        "file://%s" % (WORK / page),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    shutil.rmtree(profile, ignore_errors=True)
    if not out.exists():
        raise SystemExit(f"[error] chrome produced no screenshot: {res.stderr[-1200:]}")
    return out


def hot_bands(d: np.ndarray, top: int, row_h: int = 20) -> list[tuple[int, int, float]]:
    """Group differing rows into css-px bands."""
    rows = (d > 24).any(axis=1)
    bands: list[tuple[int, int, float]] = []
    y = 0
    n = len(rows)
    while y < n:
        if not rows[y]:
            y += 1
            continue
        start = y
        while y < n and rows[y]:
            y += 1
        # merge tiny gaps so a card edge and its text form one band
        bands.append((start, y, float((d[start:y] > 24).mean()) * 100))
    merged: list[tuple[int, int, float]] = []
    for s, e, p in bands:
        if merged and s - merged[-1][1] < row_h * 2:
            ps, pe, pp = merged[-1]
            merged[-1] = (ps, e, max(pp, p))
        else:
            merged.append((s, e, p))
    merged.sort(key=lambda t: -(t[1] - t[0]) * t[2])
    return merged[:top]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("screen")
    ap.add_argument("--hot", type=int, default=20)
    ap.add_argument("--grid", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    name = args.screen
    if name not in SCREENS:
        raise SystemExit(f"unknown screen {name}")
    spec = SCREENS[name]
    h, w = HEIGHTS[name], WIDTHS.get(name, 390)

    prepare(spec["page"])
    shot = shoot(spec["page"], h, w)
    a = Image.open(shot).convert("RGB")
    b = Image.open(ROOT / spec["source"]).convert("RGB")
    if a.size != b.size:
        b = b.resize(a.size, Image.LANCZOS)
    A = np.asarray(a).astype(np.int16)
    B = np.asarray(b).astype(np.int16)
    d = np.abs(A - B).sum(axis=2)
    hot = d > 24
    pct = float(hot.mean()) * 100

    print(f"[{name}] {w}x{h} css  render={a.size}  diff={pct:.2f}%  mean={d.mean()/3:.2f}")

    bands = hot_bands(d, args.hot)
    print("hot bands (css px):")
    for s, e, p in bands:
        print(f"   y {s/2:7.1f} .. {e/2:7.1f}   {p:5.1f}% of the band differs"
              f"   ({e-s} render rows)")

    if args.grid:
        rows, cols = 16, 6
        hh, ww = hot.shape[0] // rows, hot.shape[1] // cols
        print("grid (row% of hot pixels):")
        for r in range(rows):
            line = []
            for c in range(cols):
                cell = hot[r * hh:(r + 1) * hh, c * ww:(c + 1) * ww]
                line.append(f"{cell.mean()*100:5.1f}")
            print("   " + " ".join(line))

    if args.out:
        base = (B // 3 + 140).clip(0, 255).astype(np.uint8)
        overlay = np.where(hot[..., None], np.array([255, 0, 90], dtype=np.uint8), base)
        Image.fromarray(overlay.astype(np.uint8)).save(args.out)
        print(f"overlay -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
