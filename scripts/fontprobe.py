#!/usr/bin/env python3
"""
Measure the real ink metrics of the self-hosted web fonts.

Renders a probe page with known strings at a known font size in headless
Chrome and measures the resulting ink bounding boxes.  The numbers it prints
(ink height / font-size, ink top offset / font-size, advance width per
character) let the page generators convert an OCR box into an exact CSS
position and font size.

    python3 scripts/fontprobe.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-render")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

SAMPLES = [
    ("cjk8", "中國語文菁英計劃"),
    ("cjk4", "報名截止"),
    ("cjk1", "賽"),
    ("digits", "9:41"),
    ("caps", "POTTERYO"),
    ("caps2", "FOR KIDS"),
    ("mixed", "1.5小時"),
    ("latin", "ABCdefg"),
    ("latin2", "North Point"),
    ("paren", "）報名截止：4月22日22:00"),
    ("space", "星期一至日09：30-22：00 内自选时段（预约"),
]

FS = 100.0
ROW = 160


def build() -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    h = ROW * len(SAMPLES) + 40
    parts = []
    for i, (_, s) in enumerate(SAMPLES):
        parts.append(
            f'<div style="position:absolute;left:20px;top:{20 + i * ROW}px;'
            f'font-size:{FS}px;line-height:1;white-space:pre;color:#000;'
            f'font-family:\'Noto Sans TC\',sans-serif;">{s}</div>'
        )
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<link rel='stylesheet' href='assets/fonts/fonts.css'>"
        "<style>html,body{margin:0;background:#fff;}</style></head><body>"
        + "".join(parts)
        + "</body></html>"
    )
    p = WORK / "_probe.html"
    p.write_text(html, encoding="utf-8")
    return p


def shoot(page: Path, height: int, scale: int = 2) -> Path:
    out = WORK / "_probe.png"
    profile = WORK / "profile-probe"
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
        "--virtual-time-budget=8000",
        "--user-data-dir=%s" % profile,
        "--window-size=900,%d" % height,
        "--screenshot=%s" % out,
        "file://%s" % page,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    shutil.rmtree(profile, ignore_errors=True)
    if not out.exists():
        print(res.stdout[-1500:], res.stderr[-1500:])
        raise SystemExit("[error] probe render failed")
    return out


def main() -> None:
    page = build()
    h = ROW * len(SAMPLES) + 40
    png = shoot(page, h)
    im = np.asarray(Image.open(png).convert("RGB"))
    print("render size", im.shape[1], im.shape[0], "scale 2")
    print(f"{'name':10s} {'inkTop':>7s} {'inkBot':>7s} {'inkH':>7s} "
          f"{'h/F':>6s} {'top/F':>6s} {'inkW':>7s} {'w/char':>8s}")
    for i, (name, s) in enumerate(SAMPLES):
        y0 = (20 + i * ROW) * 2
        y1 = y0 + ROW * 2
        reg = im[y0:y1]
        if reg.size == 0:
            continue
        flat = reg.reshape(-1, 3)
        mask = flat.min(axis=1) < 200
        if not mask.any():
            print(f"{name:10s}  (no ink)")
            continue
        ys, xs = np.nonzero(mask.reshape(reg.shape[:2]))
        itop = ys.min() / 2 + 20 + i * ROW
        ibot = ys.max() / 2 + 20 + i * ROW
        il = xs.min() / 2 + 20
        ir = xs.max() / 2 + 20
        print(f"{name:10s} {itop:7.2f} {ibot:7.2f} {ibot - itop + 1:7.2f} "
              f"{(ibot - itop + 1) / FS:6.3f} {(itop - (20 + i * ROW)) / FS:6.3f} "
              f"{ir - il + 1:7.1f} {(ir - il + 1) / max(1, len(s)):8.3f}")


if __name__ == "__main__":
    sys.exit(main())
