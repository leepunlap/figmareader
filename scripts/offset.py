#!/usr/bin/env python3
"""List the text of a page whose rendered position differs from the export.

For every OCR run the script measures the ink in the export and in the
render and reports the offset.  Runs are then matched to the CSS rule that
draws them, so the output names the rule that has to change.

    python3 scripts/offset.py v1-vip-membership-yearly
    python3 scripts/offset.py --all --worst 25
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-render")


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


def ink_box(arr, x0, y0, x1, y1, thr=90):
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


def arrays(src: Path, shot: Path):
    si = Image.open(src).convert("RGB")
    s = np.array(si.resize((si.size[0] // 4, si.size[1] // 4), Image.LANCZOS)).astype(int)
    ri = Image.open(shot).convert("RGB")
    r = np.array(ri.resize((ri.size[0] // 2, ri.size[1] // 2), Image.LANCZOS)).astype(int)
    return s, r


def norm(s):
    return re.sub(r"\s+", "", s)


def page_classes(page: str) -> dict[str, str]:
    """class -> the text the first element with that class carries."""
    html = (ROOT / page).read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for m in re.finditer(
        r'<(?:p|span|h[1-6]|div|li|td|th)\b[^>]*class="([^"]+)"[^>]*>([^<]*)</',
        html,
    ):
        text = m.group(2).strip()
        if not text:
            continue
        for c in m.group(1).split():
            out.setdefault(c, text)
    return out


def report(page: str, src: Path) -> list[dict]:
    shot = WORK / f"{page[:-5]}.png"
    if not shot.exists():
        return []
    runs = load_runs(page)
    if not runs:
        return []
    s, r = arrays(src, shot)
    classes = page_classes(page)
    out = []
    for run in runs:
        x0, y0 = int(run["x0"]), int(run["y0"])
        x1, y1 = int(run["x1"]), int(run["y1"])
        sb = ink_box(s, x0 - 2, y0 - 2, x1 + 2, y1 + 2)
        rb = None
        for dy in (0, -2, -1, 1, 2, -3, 3, -4, 4):
            for dx in (0, -2, -1, 1, 2, -3, 3, -4, 4):
                rb = ink_box(r, x0 + dx - 2, y0 + dy - 2, x1 + dx + 2, y1 + dy + 2)
                if rb is not None:
                    break
            if rb is not None:
                break
        if sb is None or rb is None:
            continue
        dL, dT = rb[0] - sb[0], rb[1] - sb[1]
        dW = (rb[2] - rb[0]) - (sb[2] - sb[0])
        dH = (rb[3] - rb[1]) - (sb[3] - sb[1])
        if abs(dL) < 2 and abs(dT) < 2 and abs(dW) < 2 and abs(dH) < 2:
            continue
        # which class draws this text?
        best = None
        for cls, txt in classes.items():
            sim = SequenceMatcher(None, norm(txt), norm(run["text"])).ratio()
            if best is None or sim > best[0]:
                best = (sim, cls)
        out.append({"dL": dL, "dT": dT, "dW": dW, "dH": dH,
                    "y": y0, "text": run["text"],
                    "class": best[1] if best and best[0] > 0.5 else "?"})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pages", nargs="*", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--worst", type=int, default=25)
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
                worst = max(rep, key=lambda c: max(abs(c["dL"]), abs(c["dT"]),
                                                    abs(c["dW"]), abs(c["dH"])))
                rows.append((len(rep), spec["page"], worst))
        rows.sort(reverse=True)
        print(f"{'off':>4}  screen")
        for n, page, w in rows[: args.worst]:
            print(f"{n:4d}  {page:34s} dL{w['dL']:+4d} dT{w['dT']:+4d} "
                  f"dW{w['dW']:+4d} dH{w['dH']:+4d}  {w['class']:22s} {w['text'][:18]}")
        return 0

    for page, src in ((p["page"], p["src"]) for p in manifest()):
        if page not in wanted:
            continue
        rep = report(page, src)
        if not rep:
            print(f"{page}: no render or nothing off")
            continue
        print(f"{page}: {len(rep)} runs off")
        print(f"{'dL':>5} {'dT':>5} {'dW':>5} {'dH':>5}  {'y':>5}  {'class':22s} text")
        for c in sorted(rep, key=lambda c: -max(abs(c["dL"]), abs(c["dT"]),
                                                abs(c["dW"]), abs(c["dH"]))):
            print(f"{c['dL']:5d} {c['dT']:5d} {c['dW']:5d} {c['dH']:5d}  "
                  f"{c['y']:5.0f}  {c['class']:22s} {c['text'][:26]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
