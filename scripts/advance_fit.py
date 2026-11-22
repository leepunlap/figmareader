#!/usr/bin/env python3
"""Measure the true CJK advance of every OCR run in a 4x export.

The auto-fitter estimates a font size from the OCR box width, which is skewed
when the source sets fullwidth punctuation with extra advance.  The CJK
advance, on the other hand, is exactly 1 em in every weight, so the mode of the
gaps between consecutive glyph ink runs recovers the real font size.

usage: advance_fit.py <slug> [--src source/v1raw/screens/<slug>.png]
"""
import argparse
import json
import os
from collections import Counter

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_source(slug):
    names = [slug]
    for pre in ("v1-", "v73-"):
        if slug.startswith(pre):
            names.append(slug[len(pre):])
    for n in names:
        for d in ("source/v1raw/screens", "source/v1raw73/screens"):
            p = os.path.join(ROOT, d, f"{n}.png")
            if os.path.exists(p):
                return p
    raise SystemExit(f"no source for {slug}")


def ink_runs(img, x0, x1, y0, y1, bg, thresh=60):
    a = np.asarray(img).astype(int)[y0:y1, x0:x1]
    d = np.abs(a - np.asarray(bg)).sum(axis=2)
    cols = (d > thresh).sum(axis=0)
    runs = []
    s = None
    for i, v in enumerate(cols):
        if v > 0 and s is None:
            s = i
        elif v == 0 and s is not None:
            runs.append(x0 + s)
            s = None
    if s is not None:
        runs.append(x0 + s)
    return runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--src")
    args = ap.parse_args()

    src = Image.open(args.src or find_source(args.slug)).convert("RGB")
    src = src.resize((src.size[0] // 2, src.size[1] // 2), Image.LANCZOS)

    path = os.path.join(ROOT, "analysis/ocr", f"{args.slug}-fit.json")
    runs = json.load(open(path))

    out = []
    for r in runs:
        f = r.get("fit")
        if not f:
            continue
        # sample a band through the middle of the ink
        y0 = max(0, int(r["src_y0"]) * 2 - 4)
        y1 = min(src.size[1], int(r["src_y1"]) * 2 + 4)
        bgt = (255, 255, 255)
        x0 = max(0, int(r["src_x0"]) * 2 - 8)
        x1 = min(src.size[0], int(r["src_x1"]) * 2 + 8)
        try:
            ir = ink_runs(src, x0, x1, y0, y1, bgt)
        except Exception:
            continue
        deltas = [ir[i + 1] - ir[i] for i in range(len(ir) - 1)]
        # the CJK advance is the most common gap in a plausible range
        cand = [d for d in deltas if 6.0 < d < 26.0]
        mode = Counter(cand).most_common(1)[0][0] if cand else 0
        out.append({
            "text": r["text"],
            "y0": r["y0"],
            "fit_fs": f["fs"],
            "advance": mode,
            "n_runs": len(ir),
            "weight": f.get("weight", 400),
        })

    print(f"# {args.slug}")
    for o in out:
        flag = "  <-- differs" if o["advance"] and abs(o["advance"] - o["fit_fs"]) > 1.2 else ""
        print(f"y {o['y0']:5d}  fit {o['fit_fs']:6.2f}  adv {o['advance']:5.2f} "
              f"n {o['n_runs']:2d} w{o['weight']}  {o['text'][:40]}{flag}")


if __name__ == "__main__":
    main()
