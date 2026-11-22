#!/usr/bin/env python3
"""
Sweep CSS overrides for one Lion screen and report the resulting diff.

Renders the page in headless Chrome once per candidate and diffs it against
the 4x Figma export, exactly like scripts/render_check.py, so a candidate can
be accepted only if it actually improves the number.

  python3 scripts/sweep.py lion-08 \
      --cand ".rbubble p{font-size:13.6px}" \
      --cand ".rbubble{padding-top:45.25px}" \
      --cand ".rbubble p{font-size:13.6px}" ".rbubble{padding-top:45.25px}"

The overrides are injected as a <style> right before </head>, so they win over
the page's own rules but never touch the source files.

  --dry-run    list the candidates without rendering
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_check import HEIGHTS, SCREENS, WIDTHS  # noqa: E402


def render(page: str, height: int, width: int, css: str, tmp: Path) -> Path:
    html = (ROOT / page).read_text(encoding="utf-8")
    html = html.replace("<body>", '<body class="render">')
    html = html.replace(
        "<head>", f'<head>\n<base href="file://{ROOT}/">', 1
    )
    if css:
        html = html.replace("</head>", f"<style>{css}</style></head>", 1)
    doc = tmp / page
    doc.write_text(html, encoding="utf-8")

    out = tmp / (page.replace(".html", ".png"))
    profile = tmp / f"profile-{os.getpid()}"
    if profile.exists():
        shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    cmd = [
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--no-first-run", "--no-default-browser-check", "--disable-extensions",
        "--allow-file-access-from-files",
        "--force-device-scale-factor=2",
        "--virtual-time-budget=12000",
        f"--user-data-dir={profile}",
        f"--window-size={width},{height}",
        f"--screenshot={out}",
        f"file://{doc}",
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    shutil.rmtree(profile, ignore_errors=True)
    if not out.exists():
        raise SystemExit(f"[error] chrome produced no screenshot for {page}")
    return out


def diff(render_png: Path, source_png: Path, region=None) -> tuple[float, float]:
    a = Image.open(render_png).convert("RGB")
    b = Image.open(source_png).convert("RGB")
    if a.size != b.size:
        b = b.resize(a.size, Image.LANCZOS)
    A = np.asarray(a).astype(np.int16)
    B = np.asarray(b).astype(np.int16)
    if region:
        x, y, w, h = region
        A = A[y * 2:(y + h) * 2, x * 2:(x + w) * 2]
        B = B[y * 2:(y + h) * 2, x * 2:(x + w) * 2]
    d = np.abs(A - B).sum(axis=2)
    return float((d > 24).mean()) * 100, float(d.mean()) / 3.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("screen")
    ap.add_argument("--cand", nargs="+", action="append",
                    help="a list of CSS rules forming one candidate")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--region", default="",
                    help="x,y,w,h in css px; report the diff of that rect only")
    args = ap.parse_args()

    region = None
    if args.region:
        region = tuple(int(v) for v in args.region.split(","))

    name = args.screen
    if name not in SCREENS:
        raise SystemExit(f"[error] unknown screen {name}")
    spec = SCREENS[name]
    height = HEIGHTS[name]
    width = WIDTHS.get(name, 390)

    cands: list[str] = [""] + [" ".join(c) for c in args.cand]
    if args.dry_run:
        for i, c in enumerate(cands):
            print(i, "|", c or "(baseline)")
        return 0

    source = ROOT / spec["source"]
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        base = None
        for i, css in enumerate(cands):
            shot = render(spec["page"], height, width, css, tmp)
            pct, mean = diff(shot, source, region)
            delta = ""
            if i == 0:
                base = pct
            else:
                delta = f"  ({pct - base:+.2f} vs baseline)"
            label = css or "(baseline)"
            print(f"[{i}] {pct:6.2f}%  mean {mean:5.2f}{delta}   {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
