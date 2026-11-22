#!/usr/bin/env python3
"""Compare the stroke weight of every text run between the export and the render.

A text run's *fill factor* - the ink area divided by the area of its ink box -
depends only on the typeface and the weight, not on the size or the position.
Comparing the fill factor of the export with the fill factor of the render
therefore says whether the page draws that run too bold or too light.

The script prints, for every run that differs, the fill factor of the source,
the fill factor of the render, and the weight that the render would need in
order to match.

    python3 scripts/weightcmp.py v1-vip-membership-yearly
    python3 scripts/weightcmp.py --all --worst 20
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

# fill factor of Noto Sans TC, measured by rendering the same string at each
# weight (see scripts/weightcmp.py --calibrate)
NOTO_FILL = {400: 0.423, 500: 0.495, 600: 0.545, 700: 0.587}


def manifest() -> list[dict]:
    rows = []
    for folder, pref in (("v1raw", "v1"), ("v1raw73", "v73")):
        m = ROOT / "source" / folder / "screens" / "manifest.json"
        if not m.exists():
            continue
        for r in json.loads(m.read_text(encoding="utf-8")):
            slug = r["slug"]
            rows.append({
                "page": r.get("page") or f"v1-{slug}.html",
                "src": ROOT / "source" / folder / "screens" / r["file"],
            })
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


def fill(arr, x0, y0, x1, y1, thr=90, core_thr=200):
    """(core fill, soft fill, box w, box h) of the ink in a region."""
    h, w, _ = arr.shape
    x0 = max(0, x0); y0 = max(0, y0); x1 = min(w, x1); y1 = min(h, y1)
    if x1 - x0 < 3 or y1 - y0 < 3:
        return None
    reg = arr[y0:y1, x0:x1]
    corners = np.concatenate([reg[0, :], reg[-1, :], reg[:, 0], reg[:, -1]])
    bg = corners.mean(axis=0)
    d = np.abs(reg - bg).sum(axis=2)
    soft = d > thr
    if soft.sum() < 20:
        return None
    ys, xs = np.where(soft)
    bw = xs.max() - xs.min() + 1
    bh = ys.max() - ys.min() + 1
    box = bw * bh
    return (float((d > core_thr).sum()) / box,
            float(soft.sum()) / box, int(bw), int(bh))


def arrays(src: Path, shot: Path):
    si = Image.open(src).convert("RGB")
    s = np.array(si.resize((si.size[0] // 4, si.size[1] // 4), Image.LANCZOS)).astype(int)
    ri = Image.open(shot).convert("RGB")
    r = np.array(ri.resize((ri.size[0] // 2, ri.size[1] // 2), Image.LANCZOS)).astype(int)
    return s, r


def nearest_weight(f: float) -> int:
    return min(NOTO_FILL, key=lambda w: abs(NOTO_FILL[w] - f))


def report(page: str, src: Path) -> list[dict]:
    shot = WORK / f"{page[:-5]}.png"
    if not shot.exists():
        return []
    runs = load_runs(page)
    if not runs:
        return []
    s, r = arrays(src, shot)
    out = []
    for run in runs:
        x0, y0 = int(run["x0"]), int(run["y0"])
        x1, y1 = int(run["x1"]), int(run["y1"])
        sf = fill(s, x0 - 2, y0 - 2, x1 + 2, y1 + 2)
        rf = None
        for dy in (0, -2, -1, 1, 2, -3, 3):
            for dx in (0, -2, -1, 1, 2, -3, 3):
                rf = fill(r, x0 + dx - 2, y0 + dy - 2, x1 + dx + 2, y1 + dy + 2)
                if rf is not None:
                    break
            if rf is not None:
                break
        if sf is None or rf is None:
            continue
        if sf[3] < 8 or rf[3] < 8:
            continue
        if abs(sf[0] - rf[0]) < 0.035:
            continue
        out.append({
            "text": run["text"], "y": y0,
            "src_fill": round(sf[0], 3), "ren_fill": round(rf[0], 3),
            "src_w": sf[2], "ren_w": rf[2],
            "want": nearest_weight(sf[0]),
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pages", nargs="*", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--worst", type=int, default=20)
    args = ap.parse_args()

    wanted = set()
    for p in args.pages:
        wanted.add(p if p.endswith(".html") else p + ".html")

    if args.all:
        rows = []
        for spec in manifest():
            if not (ROOT / spec["page"]).exists():
                continue
            try:
                rep = report(spec["page"], spec["src"])
            except Exception as exc:  # noqa: BLE001
                print(f"[warn] {spec['page']}: {exc}", file=sys.stderr)
                continue
            if rep:
                rows.append((len(rep), spec["page"], rep))
        rows.sort(reverse=True)
        print(f"{'off':>4}  screen")
        for n, page, rep in rows[: args.worst]:
            w = max(rep, key=lambda c: abs(c["src_fill"] - c["ren_fill"]))
            print(f"{n:4d}  {page:34s} src{w['src_fill']:.3f} ren{w['ren_fill']:.3f} "
                  f"want w{w['want']}  {w['text'][:20]}")
        return 0

    for page, src in ((p["page"], p["src"]) for p in manifest()):
        if page not in wanted:
            continue
        rep = report(page, src)
        print(f"{page}: {len(rep)} runs with a different weight")
        print(f"{'src':>7} {'ren':>7} {'want':>6}  {'y':>5}  text")
        for c in sorted(rep, key=lambda c: -abs(c["src_fill"] - c["ren_fill"])):
            print(f"{c['src_fill']:7.3f} {c['ren_fill']:7.3f} {c['want']:6d}  "
                  f"{c['y']:5.0f}  {c['text'][:30]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
