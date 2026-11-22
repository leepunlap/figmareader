#!/usr/bin/env python3
"""
Probe the anti-aliasing / resampling hypothesis.

The Figma export is a 4x raster.  The current pipeline compares

    Chrome rendered natively at 2x   vs   LANCZOS(export 4x -> 2x)

so the export side carries Lanczos ringing while the Chrome side does not.
This script measures several alternatives on one screen so the cheapest
representation that matches the export can be chosen:

    base      chrome2              vs lanczos(src4)
    lz4       lanczos(chrome4)     vs lanczos(src4)
    box4      box(chrome4)        vs lanczos(src4)
    area4     area(chrome4)       vs lanczos(src4)
    bic4      bicubic(chrome4)    vs lanczos(src4)
    raw4      chrome4              vs src4

It also prints a text-band breakdown so the effect on glyph pixels can be
separated from the effect on flat areas.

  python3 scripts/aa_probe.py v1-competition-detail-closed
  python3 scripts/aa_probe.py v1-home --bands 120-140
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/aa-probe")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# reuse the manifest-driven screen table from render_check
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


def shoot(page: str, height: int, width: int, scale: int,
          extra: list[str] | None = None) -> Path:
    out = WORK / page.replace(".html", ".png")
    profile = WORK / f"profile-{os.getpid()}-{scale}"
    if profile.exists():
        shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    cmd = [
        CHROME,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--allow-file-access-from-files",
        "--force-device-scale-factor=%d" % scale,
        "--virtual-time-budget=12000",
        "--user-data-dir=%s" % profile,
        "--window-size=%d,%d" % (width, height),
        "--screenshot=%s" % out,
    ] + (extra or []) + ["file://%s" % (WORK / page)]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    shutil.rmtree(profile, ignore_errors=True)
    if not out.exists():
        raise SystemExit(f"[error] chrome produced no screenshot for {page}\n"
                         f"{res.stdout[-1500:]}\n{res.stderr[-1500:]}")
    return out


def diff(a: Image.Image, b: Image.Image) -> tuple[float, float, np.ndarray]:
    A = np.asarray(a.convert("RGB")).astype(np.int16)
    B = np.asarray(b.convert("RGB")).astype(np.int16)
    d = np.abs(A - B).sum(axis=2)
    return float((d > 24).mean()) * 100, float(d.mean()) / 3.0, d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("screen")
    ap.add_argument("--bands", default="",
                    help="css 'y0-y1' bands to break the result down")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    name = args.screen
    if name not in SCREENS:
        raise SystemExit(f"unknown screen {name}")
    spec = SCREENS[name]
    page = spec["page"]
    h = HEIGHTS[name]
    w = WIDTHS.get(name, 390)

    prepare(page)
    src4 = Image.open(ROOT / spec["source"]).convert("RGB")
    ref2 = src4.resize((src4.size[0] // 2, src4.size[1] // 2), Image.LANCZOS)

    print(f"[{name}] {w}x{h} css   source {src4.size}")

    chrome2 = Image.open(shoot(page, h, w, 2)).convert("RGB")
    chrome4 = Image.open(shoot(page, h, w, 4)).convert("RGB")
    chrome4nh = Image.open(
        shoot(page, h, w, 4, ["--font-render-hinting=none"])).convert("RGB")

    variants: dict[str, tuple[Image.Image, Image.Image]] = {
        "base   chrome2       vs lanczos(src4)": (chrome2, ref2),
        "lz4    lanczos(c4)   vs lanczos(src4)":
            (chrome4.resize(ref2.size, Image.LANCZOS), ref2),
        "box4   box(c4)       vs lanczos(src4)":
            (chrome4.resize(ref2.size, Image.BOX), ref2),
        "area4  area(c4)      vs lanczos(src4)":
            (chrome4.resize(ref2.size, Image.BOX), ref2),
        "bic4   bicubic(c4)   vs lanczos(src4)":
            (chrome4.resize(ref2.size, Image.BICUBIC), ref2),
        "lz4nh  lanczos(c4nh) vs lanczos(src4)":
            (chrome4nh.resize(ref2.size, Image.LANCZOS), ref2),
        "raw4   chrome4       vs src4": (chrome4, src4),
    }

    bands = []
    if args.bands:
        for chunk in args.bands.split(","):
            a, b = chunk.split("-")
            bands.append((int(a), int(b)))

    print(f"{'variant':40s} {'diff %':>8s} {'mean':>7s}   bands")
    for label, (a, b) in variants.items():
        pct, mean, d = diff(a, b)
        extra = ""
        if bands:
            parts = []
            for y0, y1 in bands:
                band = d[y0 * 2:y1 * 2]
                parts.append("%d-%d:%.2f%%" % (y0, y1, (band > 24).mean() * 100))
            extra = "   " + " ".join(parts)
        print(f"{label:40s} {pct:7.2f}% {mean:7.2f}{extra}")

    if args.out:
        Image.fromarray(
            np.asarray(chrome4.resize(ref2.size, Image.LANCZOS))).save(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
