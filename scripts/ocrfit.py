#!/usr/bin/env python3
"""
Fit CSS geometry to the OCR boxes of a screen.

The Vision OCR dump gives a box per text run, but not the font size and not
the exact baseline: the same string rendered in the self-hosted web font has a
different ink box than the PingFang SC used in the Figma export.

This tool closes that gap.  It

  1. reads the OCR runs of a screen,
  2. measures the *real* ink box of every run in the 4x export,
  3. renders a calibration page where every string is drawn once per weight
     in the same web font and measures its ink box there,
  4. derives for every run the font size, the left and the top that reproduce
     the source ink box exactly, and the ink colour,
  5. prints the HTML snippet for the page.

    python3 scripts/ocrfit.py v1-competition-detail-open
    python3 scripts/ocrfit.py v1-competition-detail-open --fit geo --tag span

The result is a JSON file in analysis/ocr/<slug>-fit.json so the page can be
rebuilt with the same numbers later.

Measurement rules that matter
-----------------------------
* The source export is measured at its native 4x, never downsampled.  A
  LANCZOS downsample adds a pixel of ringing on every side of the ink, which
  is a ~3% error on a 14px line - enough to move the glyphs a pixel.
* The calibration is rendered at 4x too, so the ink mask of the source and
  the ink mask of the calibration are produced by the same rule at the same
  device scale and can be compared directly.
* Regular and bold copy are told apart by the *fill factor* (ink area over
  the ink bounding box).  It is scale free, so the probe size does not matter,
  and CJK ideographs are full width in every weight, so neither the advance
  nor the ink height can separate the weights.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-render")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

PROBE_FS = 50.0          # probe font size, css px
ROW = 110                # row height of the calibration page, css px
SCALE = 4                # device scale of both the source and the calibration
ROWS_PER_CHUNK = 8       # calibration rows per chrome render


# --------------------------------------------------------------------- io --

def source_png(slug: str) -> Path:
    if slug.startswith("v73-"):
        return ROOT / "source/v1raw73/screens" / f"{slug}.png"
    return ROOT / "source/v1raw/screens" / f"{slug[3:]}.png"


def load_source(slug: str):
    """The export at its native 4x."""
    return np.asarray(Image.open(source_png(slug)).convert("RGB"))


def load_runs(slug: str) -> list[dict]:
    p = ROOT / "analysis/ocr" / f"{slug}.tsv"
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        x0, y0, x1, y1, conf, text = parts[0], parts[1], parts[2], parts[3], parts[4], "\t".join(parts[5:])
        out.append({
            "x0": int(x0), "y0": int(y0), "x1": int(x1), "y1": int(y1),
            "conf": float(conf), "text": text.strip(),
        })
    out.sort(key=lambda r: (r["y0"], r["x0"]))
    return out


# --------------------------------------------------------------- measuring --

def ink_mask(reg: np.ndarray, k: int = 8, thr: int = 40):
    """Ink mask of a region, with the background estimated per row.

    The background is taken from the leftmost and rightmost columns of the
    region, so a gradient header or a photo behind the text does not read as
    ink.
    """
    if reg.shape[0] < 2 or reg.shape[1] < 2 * k + 2:
        return None
    edge = np.concatenate([reg[:, :k], reg[:, -k:]], axis=1).astype(int)
    bgs = np.median(edge, axis=1)
    d = np.abs(reg.astype(int) - bgs[:, None, :]).max(axis=2)
    return d > thr


def ink_bands(mask: np.ndarray, gap: int = 6):
    """Row bands of ink, with small gaps merged.

    The OCR box of a line of text often reaches into the line above or
    below, so the raw ink of the region covers two lines.  The lines of a
    text block are separated by a clear gap, while the strokes inside one
    line are only a pixel or two apart, so the bands of a single line merge
    and the bands of two lines stay apart.
    """
    prof = mask.sum(axis=1)
    rows = np.nonzero(prof > 0)[0]
    if len(rows) == 0:
        return []
    bands = []
    start = prev = int(rows[0])
    for r in rows[1:]:
        r = int(r)
        if r - prev <= gap:
            prev = r
            continue
        bands.append((start, prev))
        start = prev = r
    bands.append((start, prev))
    return bands


def measure(arr: np.ndarray, x0: int, y0: int, x1: int, y1: int, pad: int = 4):
    """Tight ink box + fill factor of one line of text inside a region.

    Returns device-pixel numbers plus the css box.
    """
    h, w, _ = arr.shape
    x0 = max(0, x0 - pad); y0 = max(0, y0 - pad)
    x1 = min(w, x1 + pad); y1 = min(h, y1 + pad)
    if x1 <= x0 or y1 <= y0:
        return None
    reg = arr[y0:y1, x0:x1]
    m = ink_mask(reg, k=4)
    if m is None or not m.any():
        return None
    bands = ink_bands(m)
    if not bands:
        return None
    # the line of text is the band with the most ink
    b = max(bands, key=lambda bb: int(m[bb[0]:bb[1] + 1].sum()))
    sub = m[b[0]:b[1] + 1]
    ys, xs = np.nonzero(sub)
    bx0, bx1 = int(xs.min()), int(xs.max())
    by0, by1 = int(ys.min()), int(ys.max())
    area = int(sub.sum())
    bw = bx1 - bx0 + 1
    bh = by1 - by0 + 1
    return {
        "x0": bx0 + x0, "y0": by0 + y0, "x1": bx1 + x0, "y1": by1 + y0,
        "w": bw, "h": bh, "area": area,
        "fill": area / float(bw * bh),
    }


def ink_colour(arr: np.ndarray, box: dict, bgc: np.ndarray):
    """Darkest core colour of the ink inside a measured box."""
    reg = arr[box["y0"]:box["y1"] + 1, box["x0"]:box["x1"] + 1].reshape(-1, 3)
    d = np.abs(reg.astype(int) - bgc).max(axis=1)
    ink = reg[d > 40]
    if len(ink) == 0:
        return "#000000"
    dd = np.abs(ink.astype(int) - bgc).max(axis=1)
    core = ink[dd >= dd.max() * 0.55]
    c, n = np.unique(core, axis=0, return_counts=True)
    c = c[int(np.argmax(n))]
    return "#%02x%02x%02x" % tuple(int(v) for v in c)


def background_colour(arr: np.ndarray, box: dict, pad: int = 10):
    """Background colour sampled from a ring *outside* the ink box."""
    h, w, _ = arr.shape
    ry0, ry1 = max(0, box["y0"] - pad), min(h, box["y1"] + 1 + pad)
    rx0, rx1 = max(0, box["x0"] - pad), min(w, box["x1"] + 1 + pad)
    if ry1 <= ry0 or rx1 <= rx0:
        return np.array([255, 255, 255])
    ring = arr[ry0:ry1, rx0:rx1].reshape(-1, 3).astype(int)
    inner = np.ones((ry1 - ry0, rx1 - rx0), bool)
    inner[box["y0"] - ry0:box["y1"] - ry0 + 1,
          box["x0"] - rx0:box["x1"] - rx0 + 1] = False
    ring = ring[inner.ravel()]
    if len(ring) == 0:
        return np.array([255, 255, 255])
    return np.median(ring, axis=0)


def render(html: str, width: int, height: int, name: str, scale: int = SCALE) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    page = WORK / name
    page.write_text(html, encoding="utf-8")
    out = WORK / (name.replace(".html", ".png"))
    profile = WORK / f"profile-{name.replace('.html', '')}"
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
        "--virtual-time-budget=12000",
        "--user-data-dir=%s" % profile,
        "--window-size=%d,%d" % (width, height),
        "--screenshot=%s" % out,
        "file://%s" % page,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    shutil.rmtree(profile, ignore_errors=True)
    if not out.exists():
        print(res.stdout[-1500:], res.stderr[-1500:])
        raise SystemExit("[error] chrome produced no screenshot")
    return out


# ------------------------------------------------------------------ fitting --

def calibrate(runs: list[dict], stack: str, fontcss: str | None = None,
              weights=(400, 500, 600, 700)) -> list[dict]:
    """Render every string once per weight and measure its ink box.

    One cell per row: the cells of a wide screen can be wider than any
    sensible column, and a string that overflows its column bleeds into the
    next one and destroys the measurement.  The page is rendered in chunks
    because chrome cannot draw a very tall document.
    """
    nw = len(weights)
    # the widest cell decides the width of the page
    width = int(max((len(r["text"]) for r in runs), default=10) * PROBE_FS * 1.2) + 120

    link = ""
    for css in (fontcss, ROOT / "assets/fonts/fonts.css", ROOT / "assets/v1/noto-latin.css"):
        if css and Path(css).exists():
            link += f"<link rel='stylesheet' href='file://{css}'>"

    def cell_html(runs_chunk):
        out = []
        # the font names have to use single quotes: a double quote would end
        # the style attribute and the cell would fall back to the default font
        fam = stack.replace('"', "'")
        for i, r in enumerate(runs_chunk):
            txt = (r["text"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            for wi, w in enumerate(weights):
                out.append(
                    f'<div style="position:absolute;left:40px;'
                    f'top:{30 + (i * nw + wi) * ROW}px;'
                    f'font-size:{PROBE_FS}px;line-height:1;white-space:pre;color:#000;'
                    f"font-weight:{w};font-family:{fam};'>{txt}</div>"
                )
        return out

    images = []
    for c0 in range(0, len(runs), ROWS_PER_CHUNK):
        chunk = runs[c0:c0 + ROWS_PER_CHUNK]
        html = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>" + link +
            "<style>html,body{margin:0;background:#fff;}</style></head><body>"
            + "".join(cell_html(chunk)) + "</body></html>"
        )
        png = render(html, width, ROW * len(chunk) * nw + 80, f"_ocrcal{c0}.html")
        images.append((c0, np.asarray(Image.open(png).convert("RGB"))))

    im_map = dict(images)
    for i, r in enumerate(runs):
        chunk_base = (i // ROWS_PER_CHUNK) * ROWS_PER_CHUNK
        local = i - chunk_base
        im = im_map[chunk_base]
        best = None
        for wi, w in enumerate(weights):
            top = 30 + (local * nw + wi) * ROW
            y0 = max(0, int((top - 10) * SCALE))
            y1 = min(im.shape[0], int((top + PROBE_FS + 30) * SCALE))
            reg = im[y0:y1, :]
            if reg.shape[0] < 2 or reg.shape[1] < 4:
                continue
            m = ink_mask(reg, k=4)
            if m is None or not m.any():
                continue
            bands = ink_bands(m)
            if not bands:
                continue
            b = max(bands, key=lambda bb: int(m[bb[0]:bb[1] + 1].sum()))
            sub = m[b[0]:b[1] + 1]
            ys, xs = np.nonzero(sub)
            bx0, bx1 = int(xs.min()), int(xs.max())
            # `sub` starts at the first row of the band, so the ink's row inside
            # the region has to be counted from the band's own offset
            by0, by1 = b[0] + int(ys.min()), b[0] + int(ys.max())
            area = int(sub.sum())
            bw, bh = bx1 - bx0 + 1, by1 - by0 + 1
            bearing = (bx0 / SCALE) - 40
            offset = (by0 / SCALE) + y0 / SCALE - top
            # a cell whose ink starts outside the text box means the cell was
            # measured wrong - skip it instead of writing a nonsense position
            if bearing < -10 or bearing > PROBE_FS or offset < -10 or offset > PROBE_FS:
                continue
            c = {
                "w": bw / SCALE,
                "h": bh / SCALE,
                "bearing": bearing,
                "offset": offset,
                "area": area,
                "fill": area / float(bw * bh),
                "weight": w,
            }
            # the fill factor is scale free, so it can be compared with the
            # fill factor measured in the export directly
            c["err"] = abs(np.log(max(r.get("src_fill", 1e-6), 1e-6) / max(c["fill"], 1e-6)))
            if best is None or c["err"] < best["err"]:
                best = c
        r["calib"] = best
    return runs


def fit(runs: list[dict], mode: str = "width") -> list[dict]:
    for r in runs:
        c = r.get("calib")
        if not c or c["w"] <= 0:
            r["fit"] = None
            continue
        if mode == "height":
            fs = PROBE_FS * (r["src_h"] / c["h"]) if c["h"] else PROBE_FS
        elif mode == "geo":
            fw = PROBE_FS * (r["src_w"] / c["w"])
            fh = PROBE_FS * (r["src_h"] / c["h"]) if c["h"] else fw
            fs = (fw * fh) ** 0.5
        else:
            fs = PROBE_FS * (r["src_w"] / c["w"])
        k = fs / PROBE_FS
        r["fit"] = {
            "fs": round(fs, 2),
            "left": round(r["src_x0"] - c["bearing"] * k, 2),
            "top": round(r["src_y0"] - c["offset"] * k, 2),
            "color": r["ink"],
            "weight": c.get("weight", 400),
            "fill_err": round(c.get("err", 0), 3),
        }
    return runs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--fit", default="width", choices=["width", "height", "geo"])
    ap.add_argument("--stack", default='"Noto Sans TC Latin", "Noto Sans TC", sans-serif')
    ap.add_argument("--fontcss", default=None)
    ap.add_argument("--cls", default="t")
    ap.add_argument("--tag", default="p")
    ap.add_argument("--y0", type=int, default=-1)
    ap.add_argument("--y1", type=int, default=10 ** 9)
    ap.add_argument("--json", action="store_true", help="only write the json file")
    ap.add_argument("--out", default=None, help="write the fit json somewhere else")
    args = ap.parse_args()

    arr = load_source(args.slug)
    runs = load_runs(args.slug)
    for r in runs:
        box = measure(arr, r["x0"] * SCALE, r["y0"] * SCALE,
                      r["x1"] * SCALE, r["y1"] * SCALE)
        if box is None:
            box = {"x0": r["x0"] * SCALE, "y0": r["y0"] * SCALE,
                   "x1": r["x1"] * SCALE, "y1": r["y1"] * SCALE,
                   "w": (r["x1"] - r["x0"] + 1) * SCALE,
                   "h": (r["y1"] - r["y0"] + 1) * SCALE,
                   "area": 0, "fill": 0.25}
        r["src_x0"] = box["x0"] / SCALE
        r["src_y0"] = box["y0"] / SCALE
        r["src_x1"] = box["x1"] / SCALE
        r["src_y1"] = box["y1"] / SCALE
        r["src_w"] = box["w"] / SCALE
        r["src_h"] = box["h"] / SCALE
        r["src_fill"] = box["fill"]
        bgc = background_colour(arr, box)
        r["ink"] = ink_colour(arr, box, bgc)
        r["bg"] = "#%02x%02x%02x" % tuple(int(v) for v in bgc)

    fontcss = args.fontcss
    if fontcss is None:
        cand = ROOT / "assets/v1" / f"{args.slug}-fonts.css"
        fontcss = str(cand) if cand.exists() else None
    runs = calibrate(runs, args.stack, fontcss)
    runs = fit(runs, args.fit)

    keep = [r for r in runs if args.y0 <= r["src_y0"] <= args.y1]
    out = Path(args.out) if args.out else ROOT / "analysis/ocr" / f"{args.slug}-fit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(runs, ensure_ascii=False, indent=1), encoding="utf-8")

    for r in keep:
        f = r.get("fit")
        if not f:
            print(f"<!-- no fit: {r['text']!r} -->")
            continue
        w = f.get("weight", 400)
        wtxt = f"font-weight:{w};" if w != 400 else ""
        print(f'<{args.tag} class="{args.cls}" style="left:{f["left"]}px;'
              f'top:{f["top"]}px;font-size:{f["fs"]}px;{wtxt}color:{f["color"]}">{r["text"]}</{args.tag}>')
    print(f"\n# {len(keep)} runs, json -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
