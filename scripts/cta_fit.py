#!/usr/bin/env python3
"""
Fit a CTA button out of the 4x Figma export and write it out as a 2x bitmap.

The quota modal's orange CTA is not a plain CSS gradient: the export draws a
soft orange glow around the pill, the fill runs on a slight diagonal, and
the pill itself is 62 px tall where the stylesheet had 55.  Reproducing all
three in CSS needs a fitted bitmap, the same way the header gradients
already ship.

  python3 scripts/cta_fit.py v1-quota-exhausted-ssvip
  python3 scripts/cta_fit.py v1-quota-exhausted-ssvip --btn 139 737 227 62.25
  python3 scripts/cta_fit.py v1-quota-exhausted-ssvip --crop 128 722 252 92

Steps
  * find the button's solid pixels (saturated orange) inside the search band
  * fit the fill: colour = a + b*x + c*y, fitted on the non-white pixels
  * rebuild the button body from that fit, so the white label baked into the
    export is removed and can be drawn live on top
  * keep the export's glow pixels outside the button untouched
  * downsample the whole crop with LANCZOS to 2x and write it out

The label is removed only well inside the pill, so the pill's own edge
anti-aliasing survives.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent


def source_for(page: str) -> Path:
    stem = page[:-5] if page.endswith(".html") else page
    cand = ROOT / "source/v1raw73/screens" / f"{stem}.png"
    if cand.exists():
        return cand
    return ROOT / "source/v1raw/screens" / f"{stem.removeprefix('v1-')}.png"


def erode(mask: np.ndarray, px: int) -> np.ndarray:
    if px <= 0:
        return mask
    img = Image.fromarray((mask * 255).astype(np.uint8))
    for _ in range(px):
        img = img.filter(ImageFilter.MinFilter(3))
    return np.asarray(img) > 127


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("page")
    ap.add_argument("--btn", nargs=4, type=float,
                    metavar=("X", "Y", "W", "H"),
                    help="button rect in css px; default: detected")
    ap.add_argument("--search", nargs=4, type=float, default=(600, 844, 0, 390),
                    metavar=("Y0", "Y1", "X0", "X1"),
                    help="css band to look for the button in")
    ap.add_argument("--crop", nargs=4, type=float, default=(),
                    metavar=("X", "Y", "W", "H"),
                    help="css crop to write; default: the button plus a glow pad")
    ap.add_argument("--pad", type=float, default=14.0,
                    help="css px of glow to keep around the button")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    src = source_for(args.page)
    im = Image.open(src).convert("RGB")
    A = np.asarray(im).astype(np.float64)
    sc = A.shape[1] / 390.0

    if args.btn and any(args.btn):
        x, y, w, h = args.btn
    else:
        y0, y1, x0, x1 = args.search
        reg = A[int(y0 * sc):int(y1 * sc), int(x0 * sc):int(x1 * sc)]
        sat = reg.max(axis=2) - reg.min(axis=2)
        mask = (reg[:, :, 0] > 240) & (sat > 60) & (reg[:, :, 2] < 180)
        ys, xs = np.nonzero(mask)
        if len(xs) == 0:
            raise SystemExit("[error] no saturated pixels found")
        x = (xs.min() + x0 * sc) / sc
        y = (ys.min() + y0 * sc) / sc
        w = (xs.max() - xs.min() + 1) / sc
        h = (ys.max() - ys.min() + 1) / sc
        print(f"[detect] button x={x:.2f} y={y:.2f} w={w:.2f} h={h:.2f}")

    # ---- fit the fill on the pixels that are not the white label ----------
    bx0, bx1 = int(round(x * sc)), int(round((x + w) * sc))
    by0, by1 = int(round(y * sc)), int(round((y + h) * sc))
    patch = A[by0:by1, bx0:bx1]
    yy, xx = np.mgrid[by0:by1, bx0:bx1]
    xs_, ys_ = (xx / sc).ravel(), (yy / sc).ravel()
    flat = patch.reshape(-1, 3)

    keep = flat.min(axis=1) < 200          # drop the white label
    M = np.vstack([np.ones(int(keep.sum())), xs_[keep], ys_[keep]]).T
    coef = {}
    for ci, ch in enumerate("RGB"):
        c, *_ = np.linalg.lstsq(M, flat[keep][:, ci], rcond=None)
        coef[ch] = c.tolist()
    print("[fit]", {k: [round(v, 4) for v in c] for k, c in coef.items()})

    # ---- express the fill as a CSS linear-gradient ----------------------
    bg, cg = coef["G"][1], coef["G"][2]
    th = math.degrees(math.atan2(bg, -cg))
    L = abs(w * math.sin(math.radians(th))) + abs(h * math.cos(math.radians(th)))
    cx, cy = x + w / 2.0, y + h / 2.0
    d = (math.sin(math.radians(th)), -math.cos(math.radians(th)))
    p0 = (cx - d[0] * L / 2.0, cy - d[1] * L / 2.0)
    p1 = (cx + d[0] * L / 2.0, cy + d[1] * L / 2.0)

    def at(ch, px, py):
        a_, b_, c_ = coef[ch]
        return a_ + b_ * px + c_ * py

    c0 = [round(at(ch, *p0)) for ch in "RGB"]
    c1 = [round(at(ch, *p1)) for ch in "RGB"]
    css_grad = (f"linear-gradient({th:.2f}deg, "
                f"rgb({c0[0]},{c0[1]},{c0[2]}) 0%, "
                f"rgb({c1[0]},{c1[1]},{c1[2]}) 100%)")
    print(f"[css] angle={th:.2f}deg  {css_grad}")

    model = np.stack([
        coef["R"][0] + coef["R"][1] * xs_ + coef["R"][2] * ys_,
        coef["G"][0] + coef["G"][1] * xs_ + coef["G"][2] * ys_,
        coef["B"][0] + coef["B"][1] * xs_ + coef["B"][2] * ys_,
    ], axis=1)
    cov = (flat[:, 1] - model[:, 1]) / np.maximum(255.0 - model[:, 1], 1e-6)

    # ---- rebuild the button body ----------------------------------------
    # "inside the pill" = the saturated pixels, eroded so the pill's own edge
    # anti-aliasing is never touched.
    sat = patch.max(axis=2) - patch.min(axis=2)
    solid = (patch[:, :, 0] > 235) & (sat > 45) & (patch[:, :, 2] < 190)
    inside = erode(solid, 3).ravel()
    hit = inside & (cov > 0.03)
    rebuilt = flat.copy()
    rebuilt[hit] = model[hit]
    print(f"[inpaint] removed {int(hit.sum())} label pixels")

    out = A.copy()
    out[by0:by1, bx0:bx1] = rebuilt.reshape(patch.shape)

    # ---- crop ------------------------------------------------------------
    if args.crop:
        kx, ky, kw, kh = args.crop
        cx0, cy0 = int(kx * sc), int(ky * sc)
        cx1, cy1 = int((kx + kw) * sc), int((ky + kh) * sc)
    else:
        cx0 = int((x - args.pad) * sc)
        cx1 = int((x + w + args.pad) * sc)
        cy0 = int((y - args.pad) * sc)
        cy1 = int((y + h + args.pad) * sc)
    crop = out[cy0:cy1, cx0:cx1]
    crop_img = Image.fromarray(crop.astype(np.uint8)).resize(
        (crop.shape[1] // 2, crop.shape[0] // 2), Image.LANCZOS)

    stem = args.page[:-5] if args.page.endswith(".html") else args.page
    name = args.out or f"{stem}-cta"
    dest = ROOT / "assets/v1" / f"{name}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    crop_img.save(dest)
    meta = {
        "page": args.page,
        "asset": str(dest.relative_to(ROOT)),
        "crop_css": [cx0 / sc, cy0 / sc, (cx1 - cx0) / sc, (cy1 - cy0) / sc],
        "button_css": [x, y, w, h],
        "fill": coef,
        "css_gradient": css_grad,
    }
    (ROOT / "assets/v1" / f"{name}.json").write_text(
        json.dumps(meta, indent=1), encoding="utf-8")
    print(f"[write] {dest} {crop_img.size} crop_css={meta['crop_css']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
