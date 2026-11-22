#!/usr/bin/env python3
"""Compare the ink of every text run between the Figma export and the render.

This is the diagnostic that answers "why does this screen differ": for each
OCR run it measures the tight ink box in the export and in the render and
prints the difference in left, top, width and height.

  * a horizontal shift means the run is misplaced
  * a width difference means the font size or the typeface is wrong
  * a height difference means the font size is wrong

    python3 scripts/inkcmp.py v1-vip-membership-yearly
    python3 scripts/inkcmp.py v1-vip-membership-yearly --top 30
    python3 scripts/inkcmp.py --all --worst 20
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
WORK = Path("/tmp/figma-render")


def manifest() -> list[tuple[str, Path, int]]:
    rows = []
    for folder, pref in (("v1raw", "v1"), ("v1raw73", "v73")):
        m = ROOT / "source" / folder / "screens" / "manifest.json"
        if not m.exists():
            continue
        for r in json.loads(m.read_text(encoding="utf-8")):
            slug = r["slug"]
            page = r.get("page") or f"v1-{slug}.html"
            src = ROOT / "source" / folder / "screens" / r["file"]
            rows.append((page, src, r["css"][0]))
    return rows


def load_runs(page: str) -> list[dict]:
    stem = page[:-5] if page.endswith(".html") else page
    p = ROOT / "analysis" / "ocr" / f"{stem}.tsv"
    if not p.exists():
        return []
    runs = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        try:
            x0, y0, x1, y1 = (float(parts[i]) for i in range(4))
        except ValueError:
            continue
        runs.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1, "text": parts[5]})
    return runs


def ink_box(arr: np.ndarray, x0: int, y0: int, x1: int, y1: int,
            thr: int = 90) -> tuple[int, int, int, int] | None:
    h, w, _ = arr.shape
    x0 = max(0, x0); y0 = max(0, y0); x1 = min(w, x1); y1 = min(h, y1)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    reg = arr[y0:y1, x0:x1]
    corners = np.concatenate([reg[0, :], reg[-1, :], reg[:, 0], reg[:, -1]])
    bg = corners.mean(axis=0)
    mask = np.abs(reg - bg).sum(axis=2) > thr
    if not mask.any():
        return None
    ys, xs = np.where(mask)
    return (x0 + xs.min(), y0 + ys.min(), x0 + xs.max() + 1, y0 + ys.max() + 1)


def compare(page: str, src: Path) -> list[dict]:
    shot = WORK / f"{page[:-5]}.png"
    if not shot.exists():
        return []
    runs = load_runs(page)
    if not runs:
        return []
    # both images are brought to 1x css pixels
    s = np.array(Image.open(src).convert("RGB").resize(
        (Image.open(src).size[0] // 4, Image.open(src).size[1] // 4),
        Image.LANCZOS)).astype(int)
    r = np.array(Image.open(shot).convert("RGB").resize(
        (Image.open(shot).size[0] // 2, Image.open(shot).size[1] // 2),
        Image.LANCZOS)).astype(int)
    out = []
    for run in runs:
        x0, y0 = int(run["x0"]), int(run["y0"])
        x1, y1 = int(run["x1"]), int(run["y1"])
        sb = ink_box(s, x0 - 2, y0 - 2, x1 + 2, y1 + 2)
        # the render may be shifted; search a small window around the source
        rb = None
        for dy in (0, -2, -1, 1, 2, -3, 3):
            for dx in (0, -2, -1, 1, 2, -3, 3):
                rb = ink_box(r, x0 + dx - 2, y0 + dy - 2, x1 + dx + 2, y1 + dy + 2)
                if rb is not None:
                    break
            if rb is not None:
                break
        if sb is None or rb is None:
            continue
        sw, sh = sb[2] - sb[0], sb[3] - sb[1]
        rw, rh = rb[2] - rb[0], rb[3] - rb[1]
        out.append({
            "text": run["text"],
            "dL": rb[0] - sb[0], "dT": rb[1] - sb[1],
            "dW": rw - sw, "dH": rh - sh,
            "sw": sw, "rw": rw, "sh": sh, "rh": rh,
            "y": y0,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pages", nargs="*", default=[])
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--worst", type=int, default=20)
    args = ap.parse_args()

    wanted = set()
    for p in args.pages:
        wanted.add(p if p.endswith(".html") else p + ".html")

    if args.all:
        rows = []
        for page, src, _w in manifest():
            if not (ROOT / page).exists():
                continue
            try:
                cmp_rows = compare(page, src)
            except Exception as exc:  # noqa: BLE001
                print(f"[warn] {page}: {exc}", file=sys.stderr)
                continue
            bad = [c for c in cmp_rows
                   if abs(c["dW"]) >= 3 or abs(c["dH"]) >= 3
                   or abs(c["dL"]) >= 3 or abs(c["dT"]) >= 3]
            if bad:
                worst = max(bad, key=lambda c: max(abs(c["dW"]), abs(c["dH"]),
                                                  abs(c["dL"]), abs(c["dT"])))
                rows.append((len(bad), page, worst))
        rows.sort(reverse=True)
        print(f"{'bad':>5}  screen")
        for n, page, w in rows[: args.worst]:
            print(f"{n:5d}  {page:34s} dL{w['dL']:+4d} dT{w['dT']:+4d} "
                  f"dW{w['dW']:+4d} dH{w['dH']:+4d}  {w['text'][:22]}")
        return 0

    if not wanted:
        print("give a page name, or --all")
        return 1

    for page, src, _w in manifest():
        if page not in wanted:
            continue
        rows = compare(page, src)
        if not rows:
            print(f"{page}: no render yet (run render_check.py {page[:-5]})")
            continue
        bad = [c for c in rows if abs(c["dW"]) >= 3 or abs(c["dH"]) >= 3
               or abs(c["dL"]) >= 3 or abs(c["dT"]) >= 3]
        print(f"{page}: {len(rows)} runs, {len(bad)} off by >2 px")
        print(f"{'dL':>5} {'dT':>5} {'dW':>5} {'dH':>5}  {'y':>5}  text")
        for c in sorted(bad, key=lambda c: -max(abs(c["dW"]), abs(c["dH"]),
                                                abs(c["dL"]), abs(c["dT"])))[: args.top]:
            print(f"{c['dL']:5d} {c['dT']:5d} {c['dW']:5d} {c['dH']:5d}  "
                  f"{c['y']:5.0f}  {c['text'][:30]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
