#!/usr/bin/env python3
"""
Turn a Figma PNG export into CSS-ready geometry.

Designed for 4x exports: the PNG is a 4x-scaled render of a design frame, so every
measured pixel is 1/4 of a CSS pixel. All output is in CSS pixels.

Pipeline
  1. read pixels (Pillow + numpy)
  2. find the page background colour (most common colour)
  3. build an "ink" mask = pixels that differ from the background
  4. segment the screen into horizontal bands (rows containing ink)
  5. segment each band into element boxes (column runs, merged across small gaps)
  6. report each box's dominant colour, edge colour and corner profile
  7. optionally crop regions out of the 4x source

Usage
  python3 scripts/frame_analyze.py source/home.png --scale 4 --out analysis
  python3 scripts/frame_analyze.py source/home.png --scale 4 --crop 120,80,64,64 --out assets/icon.png
  python3 scripts/frame_analyze.py source/home.png --scale 4 --crop-boxes --out analysis/crops
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------- utils

def hex_of(rgb) -> str:
    r, g, b = (int(v) for v in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def dominant_colors(arr: np.ndarray, n: int = 12, quant: int = 16) -> list[dict]:
    """Most common colours, quantised so near-identical shades collapse together."""
    flat = arr.reshape(-1, 3)
    q = flat // quant
    keys = (q[:, 0].astype(np.int32) << 16) | (q[:, 1].astype(np.int32) << 8) | q[:, 2].astype(np.int32)
    vals, counts = np.unique(keys, return_counts=True)
    order = np.argsort(-counts)[:n]
    out = []
    total = len(keys)
    for i in order:
        k = int(vals[i])
        sel = flat[keys == k]
        # exact mean of the bucket -> the true on-screen colour, not a grid centre
        r, g, b = (int(round(float(sel[:, c].mean()))) for c in range(3))
        out.append(
            {
                "hex": hex_of((r, g, b)),
                "rgb": [r, g, b],
                "share": round(float(counts[i]) / total, 5),
            }
        )
    return out


def background_color(arr: np.ndarray) -> np.ndarray:
    """Background = most common colour, but sampled from the border ring only.

    A design frame's outer edge is nearly always the page background, and this
    avoids picking a dominant content colour as the background.
    """
    h, w, _ = arr.shape
    ring = np.concatenate(
        [
            arr[: max(1, h // 100), :, :].reshape(-1, 3),
            arr[-max(1, h // 100) :, :, :].reshape(-1, 3),
            arr[:, : max(1, w // 100), :].reshape(-1, 3),
            arr[:, -max(1, w // 100) :, :].reshape(-1, 3),
        ]
    )
    q = ring  # exact values: the page background is a flat fill, so take the true modal colour
    keys = (q[:, 0].astype(np.int32) << 16) | (q[:, 1].astype(np.int32) << 8) | q[:, 2].astype(np.int32)
    vals, counts = np.unique(keys, return_counts=True)
    k = int(vals[np.argmax(counts)])
    return np.array([(k >> 16) & 0xFF, (k >> 8) & 0xFF, k & 0xFF], dtype=np.int16)


def ink_mask(arr: np.ndarray, bg: np.ndarray, thresh: int = 26) -> np.ndarray:
    d = np.abs(arr.astype(np.int16) - bg).sum(axis=2)
    return d > thresh


def runs_from_profile(profile: np.ndarray, min_frac: float, gap: int) -> list[tuple[int, int]]:
    """Turn a boolean profile into [start, end) runs, merging gaps smaller than `gap`."""
    hits = profile >= min_frac
    out: list[tuple[int, int]] = []
    start = None
    last = None
    for i, v in enumerate(hits):
        if v:
            if start is None:
                start = i
            last = i
        elif start is not None and i - last > gap:
            out.append((start, last + 1))
            start = None
    if start is not None:
        out.append((start, last + 1))
    return out


def corner_profile(patch: np.ndarray, bg: np.ndarray, thresh: int = 26) -> str:
    """'square' | 'rounded' | 'transparent-ish' - inspected from the patch corners."""
    h, w, _ = patch.shape
    k = max(2, min(h, w) // 8)
    corners = [
        patch[:k, :k, :],
        patch[:k, -k:, :],
        patch[-k:, :k, :],
        patch[-k:, -k:, :],
    ]
    corner_bg = 0
    for c in corners:
        c = c.reshape(-1, 3)
        d = np.abs(c.astype(np.int16) - bg).sum(axis=1)
        corner_bg += float((d <= thresh).mean())
    avg = corner_bg / 4
    if avg > 0.85:
        return "rounded-or-empty"
    if avg > 0.25:
        return "rounded"
    return "square"


def edge_color(patch: np.ndarray, bg: np.ndarray) -> str | None:
    """Dominant non-background colour along the patch border (a stroke colour)."""
    h, w, _ = patch.shape
    k = max(1, min(h, w) // 40)
    ring = np.concatenate(
        [
            patch[:k, :, :].reshape(-1, 3),
            patch[-k:, :, :].reshape(-1, 3),
            patch[:, :k, :].reshape(-1, 3),
            patch[:, -k:, :].reshape(-1, 3),
        ]
    )
    d = np.abs(ring.astype(np.int16) - bg).sum(axis=1)
    sel = ring[d > 26]
    if len(sel) < 8:
        return None
    q = sel // 16
    keys = (q[:, 0].astype(np.int32) << 16) | (q[:, 1].astype(np.int32) << 8) | q[:, 2].astype(np.int32)
    vals, counts = np.unique(keys, return_counts=True)
    k2 = int(vals[np.argmax(counts)])
    bucket = sel[keys == k2]
    r, g, b = (int(round(float(bucket[:, c].mean()))) for c in range(3))
    return hex_of((r, g, b))


# ------------------------------------------------------------------ analysis

def analyze(img: Image.Image, scale: int, work_width: int = 1400) -> dict:
    W, H = img.size
    arr_full = np.asarray(img.convert("RGB"))
    bg = background_color(arr_full)

    ratio = work_width / W if W > work_width else 1.0
    if ratio != 1.0:
        small = img.convert("RGB").resize((int(W * ratio), int(H * ratio)), Image.LANCZOS)
        arr = np.asarray(small)
    else:
        arr = arr_full
    h, w, _ = arr.shape

    mask = ink_mask(arr, bg)
    # ignore hairline artefacts
    mask = mask & (np.asarray(arr).astype(np.int16).sum(axis=2) < 255 * 3 - 30)

    rows = mask.mean(axis=1)
    bands = runs_from_profile(rows, min_frac=0.004, gap=max(2, int(h * 0.004)))
    # merge bands separated by a hairline (a rule or divider)
    merged: list[tuple[int, int]] = []
    for b in bands:
        if merged and b[0] - merged[-1][1] <= 2:
            merged[-1] = (merged[-1][0], b[1])
        else:
            merged.append(list(b) and (b[0], b[1]))
    bands = [tuple(b) for b in merged]

    s = 1 / ratio  # work pixels -> full pixels
    to_css = scale / ratio  # full pixels -> css pixels

    box_out = []
    for y0, y1 in bands:
        band = mask[y0:y1, :]
        cols = band.mean(axis=0)
        runs = runs_from_profile(cols, min_frac=0.02, gap=max(2, int(w * 0.006)))
        for x0, x1 in runs:
            fx0, fx1 = int(x0 * s), int(x1 * s)
            fy0, fy1 = int(y0 * s), int(y1 * s)
            patch = arr_full[fy0:fy1, fx0:fx1]
            if patch.size == 0:
                continue
            dom = dominant_colors(patch, n=3)
            box_out.append(
                {
                    "x": round(fx0 / scale, 2),
                    "y": round(fy0 / scale, 2),
                    "w": round((fx1 - fx0) / scale, 2),
                    "h": round((fy1 - fy0) / scale, 2),
                    "px": [fx0, fy0, fx1, fy1],
                    "fill": dom[0]["hex"] if dom else None,
                    "fill_share": dom[0]["share"] if dom else None,
                    "colors": dom,
                    "stroke": edge_color(patch, bg),
                    "corners": corner_profile(patch, bg),
                }
            )

    return {
        "source": {"width": W, "height": H, "scale": scale},
        "css_size": {"width": round(W / scale, 2), "height": round(H / scale, 2)},
        "background": hex_of(bg),
        "palette": dominant_colors(arr_full, n=14),
        "bands": [
            {"y": round(y0 * s / scale, 2), "h": round((y1 - y0) * s / scale, 2)} for y0, y1 in bands
        ],
        "boxes": box_out,
        "_unused": to_css,
    }


def crop(img: Image.Image, box_px, scale: int, out_path: Path, export_scale: int = 2) -> None:
    x, y, w, h = (int(v) for v in box_px)
    patch = img.convert("RGBA").crop((x, y, x + w, y + h))
    target_w = max(1, round(w * export_scale / scale))
    target_h = max(1, round(h * export_scale / scale))
    patch = patch.resize((target_w, target_h), Image.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    patch.save(out_path)
    print(f"[crop] {out_path} ({target_w}x{target_h})")


# ---------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("png", help="Figma PNG export")
    ap.add_argument("--scale", type=int, default=4, help="export scale (2 or 4)")
    ap.add_argument("--out", default="analysis", help="output dir for the analysis json")
    ap.add_argument("--crop", help="x,y,w,h in source pixels -> writes a png")
    ap.add_argument("--crop-boxes", action="store_true", help="crop every detected box")
    ap.add_argument("--export-scale", type=int, default=2, help="output scale for crops (2 = retina)")
    args = ap.parse_args()

    src = Path(args.png)
    if not src.exists():
        print(f"[error] no such file: {src}", file=sys.stderr)
        return 1

    img = Image.open(src)
    print(f"[image] {src} -> {img.size[0]}x{img.size[1]}px  (css {img.size[0]//args.scale}x{img.size[1]//args.scale})")

    out_dir = Path(args.out) if Path(args.out).is_absolute() else ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.crop:
        dest = Path(args.crop) if Path(args.crop).is_absolute() else ROOT / args.crop
        crop(img, args.crop.split(","), args.scale, dest, args.export_scale)
        return 0

    result = analyze(img, args.scale)
    result.pop("_unused", None)
    result["source"]["path"] = str(src)

    js = out_dir / "frame.json"
    js.write_text(json.dumps(result, indent=2))
    print(f"[json]  {js}")
    print(f"[bg]    {result['background']}")
    print(f"[css]   {result['css_size']['width']} x {result['css_size']['height']}")
    print(f"[boxes] {len(result['boxes'])} candidates, {len(result['bands'])} bands")
    for b in result["bands"][:12]:
        print(f"         band y={b['y']} h={b['h']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
