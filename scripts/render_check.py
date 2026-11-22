#!/usr/bin/env python3
"""
Render the generated pages in headless Chrome and diff them against the
original 4x Figma exports.

  python3 scripts/render_check.py                 # render + diff every screen
  python3 scripts/render_check.py home list-020  # only some screens
  python3 scripts/render_check.py --keep          # keep the rendered PNGs

Output:
  * /tmp/figma-render/<screen>.png   rendered at 4x, same pixel size as source
  * /tmp/figma-render/<screen>-diff.png  red/green overlay of the difference
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
WORK = Path("/tmp/figma-render")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

SCREENS = {
    "home":     {"page": "home.html",     "source": "source/home.png"},
    "list-020": {"page": "list-020.html", "source": "source/list-020.png"},
    "list-023": {"page": "list-023.html", "source": "source/list-023.png"},
    "list-027": {"page": "list-027.html", "source": "source/list-027.png"},
    # --- "Lion" page -------------------------------------------------
    "lion-01": {"page": "lion-01.html", "source": "source/lion/lion-01-activity-feed.png"},
    "lion-02": {"page": "lion-02.html", "source": "source/lion/lion-02-activity-filter.png"},
    "lion-03": {"page": "lion-03.html", "source": "source/lion/lion-03-org-feed-a.png"},
    "lion-04": {"page": "lion-04.html", "source": "source/lion/lion-04-org-feed-b.png"},
    "lion-05": {"page": "lion-05.html", "source": "source/lion/lion-05-org-filter.png"},
    "lion-06": {"page": "lion-06.html", "source": "source/lion/lion-06-org-detail-lionsclub.png"},
    "lion-07": {"page": "lion-07.html", "source": "source/lion/lion-07-event-detail-rosewood.png"},
    "lion-08": {"page": "lion-08.html", "source": "source/lion/lion-08-chat-1.png"},
    "lion-09": {"page": "lion-09.html", "source": "source/lion/lion-09-org-detail-lionshk.png"},
    "lion-10": {"page": "lion-10.html", "source": "source/lion/lion-10-event-detail-lionshk.png"},
    "lion-11": {"page": "lion-11.html", "source": "source/lion/lion-11-chat-2.png"},
}

HEIGHTS = {
    "home": 1196, "list-020": 1074, "list-023": 1032, "list-027": 990,
    "lion-01": 874, "lion-02": 874, "lion-03": 848, "lion-04": 848, "lion-05": 848,
    "lion-06": 1428, "lion-07": 1918, "lion-08": 928, "lion-09": 1428,
    "lion-10": 1918, "lion-11": 928,
}


def _load_v1_screens():
    """The v1.0 / v1.0-7.3 pages are generated from a manifest, so their screen
    list is read from disk instead of being hard-coded."""
    out = {}
    for folder in ("v1raw", "v1raw73"):
        m = ROOT / "source" / folder / "screens" / "manifest.json"
        if not m.exists():
            continue
        for row in json.loads(m.read_text(encoding="utf-8")):
            slug = row["slug"]
            key = row.get("key") or f"v1-{slug}"
            out[key] = {
                "page": row.get("page") or f"v1-{slug}.html",
                "source": f"source/{folder}/screens/{row['file']}",
                "h": row["css"][1],
                "w": row["css"][0],
            }
    return out



# artboard width in css px (most screens are 390; the 402-wide ones are not)
WIDTHS = {
    "lion-07": 402, "lion-10": 402,
}

SCREENS.update(_load_v1_screens())
for _k, _v in list(SCREENS.items()):
    if _k.startswith(("v1-", "v73-")):
        HEIGHTS[_k] = _v.get("h", 844)
        WIDTHS[_k] = _v.get("w", 390)



def prepare(page: str) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    html = (ROOT / page).read_text(encoding="utf-8")
    html = html.replace("<body>", '<body class="render">')
    html = html.replace(
        "<head>",
        f'<head>\n<base href="file://{ROOT}/">',
        1,
    )
    out = WORK / page
    out.write_text(html, encoding="utf-8")
    return out


def shoot(page: str, height: int, scale: int = 2, width: int = 390) -> Path:
    out = WORK / page.replace(".html", ".png")
    # A per-process profile: several agents verify screens in parallel and a
    # shared profile makes Chrome fail to start (the screenshot then silently
    # keeps the previous run's file).
    profile = WORK / f"profile-{os.getpid()}"
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
        # fonts live next to the pages on disk; without this Chrome treats the
        # file:// document as an opaque origin and silently drops the woff2
        "--allow-file-access-from-files",
        "--force-device-scale-factor=%d" % scale,
        "--virtual-time-budget=12000",
        "--user-data-dir=%s" % profile,
        "--window-size=%d,%d" % (width, height),
        "--screenshot=%s" % out,
        "file://%s" % (WORK / page),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    shutil.rmtree(profile, ignore_errors=True)
    if not out.exists():
        print(res.stdout[-2000:], res.stderr[-2000:])
        raise SystemExit(f"[error] chrome produced no screenshot for {page}")
    return out


def compare(render: Path, source: Path, name: str, scale: int = 2) -> dict:
    a = Image.open(render).convert("RGB")
    b = Image.open(source).convert("RGB")
    if a.size != b.size:
        # the export is 4x; bring it to the render's scale the same way the
        # image assets were built
        b = b.resize(a.size, Image.LANCZOS)
    A = np.asarray(a).astype(np.int16)
    B = np.asarray(b).astype(np.int16)
    d = np.abs(A - B).sum(axis=2)
    pct = float((d > 24).mean()) * 100
    mean = float(d.mean()) / 3.0

    # overlay: original in grey, differences in magenta
    base = (B // 3 + 140).clip(0, 255).astype(np.uint8)
    hot = (d > 24)[..., None]
    out = np.where(hot, np.array([255, 0, 90], dtype=np.uint8), base)
    Image.fromarray(out.astype(np.uint8)).save(WORK / f"{name}-diff.png")
    _ = None
    return {"pct": pct, "mean": mean, "render": a.size, "source": b.size}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("screens", nargs="*", default=[])
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--scale", type=int, default=2,
                    help="render scale; 4 renders at 4x and downsamples the "
                         "source to match the export's own pixel grid")
    args = ap.parse_args()

    names = args.screens or list(SCREENS)
    heights = HEIGHTS

    print(f"{'screen':10s} {'render':>12s} {'source':>12s} {'diff px %':>10s} {'mean ch':>9s}")
    for name in names:
        if name not in SCREENS:
            print(f"[skip] unknown screen {name}")
            continue
        spec = SCREENS[name]
        if not (ROOT / spec["page"]).exists():
            print(f"[skip] {name} (not built yet)")
            continue
        prepare(spec["page"])
        shot = shoot(spec["page"], heights[name], width=WIDTHS.get(name, 390),
                     scale=args.scale)
        res = compare(shot, ROOT / spec["source"], name, args.scale)
        print(
            f"{name:10s} {str(res['render']):>12s} {str(res['source']):>12s} "
            f"{res['pct']:9.2f}% {res['mean']:9.2f}"
        )

    if not args.keep:
        for prof in WORK.glob("profile*"):
            shutil.rmtree(prof, ignore_errors=True)
    print(f"\nrendered + diffs in {WORK}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
