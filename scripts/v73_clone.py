#!/usr/bin/env python3
"""
Clone a 7.3 screen from its v1.0 twin.

Many artboards on the `v1.0 最初版 - (7.3)` Figma page are byte-identical
copies of an artboard on the big `v1.0` page (the manifest `match` field
names it).  For those, hand-rebuilding the HTML is wasted work: copy the v1
page, rewrite its asset paths, and let `render_check.py` verify.

  python3 scripts/v73_clone.py            # clone everything that qualifies
  python3 scripts/v73_clone.py --dry-run  # just report

Only screens whose source PNGs differ by <= --tol percent of pixels are
cloned; anything else must be built by hand.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent.parent


def pixel_diff(a_path: Path, b_path: Path) -> float:
    a = Image.open(a_path).convert("RGB")
    b = Image.open(b_path).convert("RGB")
    a4 = np.asarray(a.resize((a.width // 4, a.height // 4), Image.LANCZOS), dtype=np.int16)
    b4 = np.asarray(b.resize((b.width // 4, b.height // 4), Image.LANCZOS), dtype=np.int16)
    h = min(a4.shape[0], b4.shape[0])
    w = min(a4.shape[1], b4.shape[1])
    if h < 40 or w < 40:
        return 100.0
    return float((np.abs(a4[:h, :w] - b4[:h, :w]).max(axis=2) > 28).mean() * 100)


def clone(v73_row: dict, v1_row: dict, tol: float) -> tuple[bool, str]:
    key = v73_row["key"]
    src_html = ROOT / f"v1-{v1_row['slug']}.html"
    src_css = ROOT / "assets" / "v1" / f"{v1_row['slug']}.css"
    if not src_html.exists() or not src_css.exists():
        return False, "v1 twin not built yet"

    v73_src = ROOT / "source" / "v1raw73" / "screens" / v73_row["file"]
    v1_src = ROOT / "source" / "v1raw" / "screens" / v1_row["file"]
    d = pixel_diff(v73_src, v1_src)
    if d > tol:
        return False, f"source diff {d:.2f}% > {tol}%"

    html = src_html.read_text(encoding="utf-8")
    css = src_css.read_text(encoding="utf-8")

    # --- rewrite the artboard size -------------------------------------
    w, h = v73_row["css"]
    html = re.sub(
        r'(<div class="v1[^"]*"\s+style=")width:\d+px;height:\d+px(")',
        rf'\g<1>width:{w}px;height:{h}px\g<2>',
        html,
    )

    # --- copy + rename every image this page owns ----------------------
    used = sorted(set(re.findall(r'assets/v1/([A-Za-z0-9_\-]+?\.(?:png|jpg|jpeg|webp|gif))', html)))
    for name in used:
        src = ROOT / "assets" / "v1" / name
        if not src.exists():
            continue
        stem, ext = name.rsplit(".", 1)
        new = f"{key}-{stem.split('-', 1)[-1]}.{ext}" if "-" in stem else f"{key}-{stem}.{ext}"
        shutil.copyfile(src, ROOT / "assets" / "v1" / new)
        html = html.replace(f"assets/v1/{name}", f"assets/v1/{new}")

    # --- per-page css + font subset -------------------------------------
    html = html.replace(f"assets/v1/{v1_row['slug']}.css", f"assets/v1/{key}.css")
    html = html.replace(
        f"assets/v1/v1-{v1_row['slug']}-fonts.css", f"assets/v1/{key}-fonts.css"
    )
    if f"assets/v1/{key}-fonts.css" not in html:
        html = html.replace(
            "</head>",
            f'  <link rel="stylesheet" href="assets/v1/{key}-fonts.css">\n</head>',
        )
    (ROOT / f"{key}.html").write_text(html, encoding="utf-8")
    (ROOT / "assets" / "v1" / f"{key}.css").write_text(css, encoding="utf-8")
    return True, f"cloned from v1-{v1_row['slug']} (src diff {d:.2f}%)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tol", type=float, default=1.0)
    ap.add_argument("--tol-max", type=float, default=None,
                    help="clone up to this source diff (default: --tol)")
    ap.add_argument("--force", action="store_true",
                    help="re-clone screens that already exist")
    ap.add_argument("--only", default=None,
                    help="only clone screens whose key contains this substring")
    args = ap.parse_args()

    m73 = json.loads((ROOT / "source" / "v1raw73" / "screens" / "manifest.json").read_text(encoding="utf-8"))
    m1 = {r["slug"]: r for r in json.loads((ROOT / "source" / "v1raw" / "screens" / "manifest.json").read_text(encoding="utf-8"))}

    done = 0
    for row in m73:
        key = row["key"]
        if args.only and args.only not in key:
            continue
        if (ROOT / f"{key}.html").exists() and not args.force:
            continue
        mt = row.get("match")
        if not mt or mt not in m1:
            continue
        if args.dry_run:
            v73_src = ROOT / "source" / "v1raw73" / "screens" / row["file"]
            v1_src = ROOT / "source" / "v1raw" / "screens" / m1[mt]["file"]
            print(f"{key:28s} match={mt:28s} src diff {pixel_diff(v73_src, v1_src):6.2f}%")
            continue
        ok, msg = clone(row, m1[mt], args.tol_max or args.tol)
        print(f"{key:28s} {'OK ' if ok else 'skip'} {msg}")
        done += ok

    print(f"cloned {done} screens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
