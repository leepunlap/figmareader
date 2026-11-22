#!/usr/bin/env python3
"""Nudge every text element of a page so its ink lands where the export put it.

The OCR bounding boxes are padded a couple of pixels above the real ink, and
the font-subset the page renders with does not reproduce the export's
rasterisation exactly, so a text run that was placed from the OCR box ends up
a few pixels too high (or too low).  The fix is mechanical: render the page,
measure the tight ink box of every run in the export and in the render, and
move each element by the difference.

Only the inline `left` / `top` of <p> elements are rewritten -- the stylesheet
is never touched, so this cannot corrupt a shared rule the way the old
`scripts/autofit.py` could.

    python3 scripts/vshift.py v1-home-2              # report only
    python3 scripts/vshift.py v1-home-2 --apply      # rewrite the html
    python3 scripts/vshift.py v1-home-2 --apply --rounds 2
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-render")

P_RE = re.compile(
    r'<p\b[^>]*style="([^"]*)"[^>]*>(.*?)</p>',
    re.S,
)
NUM_RE = re.compile(r"(-?[\d.]+)px")


# --------------------------------------------------------------------- io --

def source_png(slug: str) -> Path:
    if slug.startswith("v73-"):
        return ROOT / "source/v1raw73/screens" / f"{slug}.png"
    return ROOT / "source/v1raw/screens" / f"{slug[3:]}.png"


def page_name(slug: str) -> str:
    return slug if slug.endswith(".html") else f"{slug}.html"


def load_runs(slug: str) -> list[dict]:
    stem = page_name(slug)[:-5]
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
        runs.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1,
                     "text": "\t".join(parts[5:])})
    return runs


def parse_html(html: str) -> list[dict]:
    out = []
    for m in P_RE.finditer(html):
        style, body = m.group(1), m.group(2)
        body = re.sub(r"<[^>]+>", "", body).strip()
        d = {"style": style, "text": body, "start": m.start(1), "end": m.end(1)}
        for prop, val in re.findall(r"([-a-z]+)\s*:\s*(-?[\d.]+)px", style):
            d[prop] = float(val)
        out.append(d)
    return out


# ------------------------------------------------------------- measuring --

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
    return (x0 + int(xs.min()), y0 + int(ys.min()),
            x0 + int(xs.max()) + 1, y0 + int(ys.max()) + 1)


def ink_mask(arr: np.ndarray, x0: int, y0: int, x1: int, y1: int,
             thr: int = 90) -> np.ndarray | None:
    h, w, _ = arr.shape
    x0 = max(0, x0); y0 = max(0, y0); x1 = min(w, x1); y1 = min(h, y1)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    reg = arr[y0:y1, x0:x1]
    corners = np.concatenate([reg[0, :], reg[-1, :], reg[:, 0], reg[:, -1]])
    bg = corners.mean(axis=0)
    return np.abs(reg - bg).sum(axis=2) > thr


def measure_pair(src1x: np.ndarray, ren1x: np.ndarray,
                 run: dict, fs: float) -> tuple[float, float] | None:
    """(correctionTop, correctionLeft) that moves the render onto the export.

    The correction is what has to be ADDED to the element's `top` / `left`.
    """
    x0, y0 = int(run["x0"]), int(run["y0"])
    x1, y1 = int(run["x1"]), int(run["y1"])
    sb = ink_box(src1x, x0 - 3, y0 - 6, x1 + 3, y1 + 3)
    if sb is None:
        return None
    sw, sh = sb[2] - sb[0], sb[3] - sb[1]
    if sw < 3 or sh < 3:
        return None

    pad_x, pad_y = 8, 8
    ws = (sb[0] - 4, sb[1] - 4, sb[2] + 4, sb[3] + 4)
    src_m = ink_mask(src1x, *ws)
    ren_m = ink_mask(ren1x, ws[0] - pad_x, ws[1] - pad_y,
                     ws[2] + pad_x, ws[3] + pad_y)
    if src_m is None or ren_m is None:
        return None
    H, W = src_m.shape
    total = int(src_m.sum())
    if total < 6:
        return None
    scores: list[tuple[float, int, int]] = []
    for dy in range(-pad_y, pad_y + 1):
        for dx in range(-pad_x, pad_x + 1):
            sub = ren_m[pad_y + dy:pad_y + dy + H, pad_x + dx:pad_x + dx + W]
            if sub.shape != src_m.shape:
                continue
            score = float((src_m & sub).sum()) / total
            scores.append((score, dx, dy))
    if not scores:
        return None
    best = max(scores, key=lambda s: s[0])
    if best[0] < 0.55:
        return None
    # among the near-equal solutions prefer the smallest move
    close = [s for s in scores if s[0] >= best[0] * 0.97]
    _, dx, dy = min(close, key=lambda s: abs(s[1]) + abs(s[2]))
    return (-dy, -dx)


# --------------------------------------------------------------- matching --

def match(elements: list[dict], runs: list[dict]) -> list[tuple[dict, dict]]:
    """Pair every <p> that has a position with the OCR run it draws."""
    pairs = []
    used = set()
    for el in elements:
        if "left" not in el or "top" not in el:
            continue
        etxt = el["text"]
        best = None
        for i, run in enumerate(runs):
            if i in used:
                continue
            rtxt = run["text"]
            same = (etxt == rtxt) or (etxt and rtxt and (etxt in rtxt or rtxt in etxt))
            dist = abs(run["x0"] - el["left"]) + abs(run["y0"] - el["top"])
            if not same and dist > 40:
                continue
            score = (0 if same else 1000) + dist
            if best is None or score < best[0]:
                best = (score, i, run)
        if best and best[0] < 120:
            used.add(best[1])
            pairs.append((el, best[2]))
    return pairs


# ----------------------------------------------------------------- main --

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--min-shift", type=float, default=1.0,
                    help="ignore shifts smaller than this many css px")
    ap.add_argument("--max-shift", type=float, default=5.0,
                    help="ignore shifts bigger than this many css px")
    args = ap.parse_args()

    slug = args.slug
    page = ROOT / page_name(slug)
    if not page.exists():
        print(f"[error] {page} does not exist")
        return 1
    shot = WORK / f"{page_name(slug)[:-5]}.png"
    if not shot.exists():
        print(f"[error] no render at {shot}; run scripts/render_check.py {slug} first")
        return 1

    src = Image.open(source_png(slug)).convert("RGB")
    src1x = np.asarray(src.resize((src.width // 4, src.height // 4), Image.LANCZOS)).astype(int)
    ren = Image.open(shot).convert("RGB")
    ren1x = np.asarray(ren.resize((ren.width // 2, ren.height // 2), Image.LANCZOS)).astype(int)

    runs = load_runs(slug)
    html = page.read_text(encoding="utf-8")

    total_dy = 0
    for rnd in range(args.rounds):
        elements = parse_html(html)
        pairs = match(elements, runs)
        moves = []
        for el, run in pairs:
            fs = el.get("font-size", 14.0)
            res = measure_pair(src1x, ren1x, run, fs)
            if res is None:
                continue
            dy, dx = res
            if abs(dy) < args.min_shift and abs(dx) < args.min_shift:
                continue
            # a wild correction means the alignment locked onto the wrong thing
            if abs(dy) > args.max_shift or abs(dx) > args.max_shift:
                print(f"  [skip] out of range dy{dy:+.0f} dx{dx:+.0f} "
                      f"{run['text'][:20]}")
                continue
            moves.append((el, dy, dx, run))
        if not moves:
            break
        # rewrite the html from the end so the offsets stay valid
        edits = []
        for el, dy, dx, run in moves:
            ntop = round(el["top"] + dy, 2)
            nleft = round(el["left"] + dx, 2)
            if abs(ntop - el["top"]) < 0.01 and abs(nleft - el["left"]) < 0.01:
                continue
            style = el["style"]
            style2 = re.sub(r"top:-?[\d.]+px", f"top:{ntop}px", style, count=1)
            style2 = re.sub(r"left:-?[\d.]+px", f"left:{nleft}px", style2, count=1)
            if style2 != style:
                edits.append((el["start"], el["end"], style2))
                total_dy += dy
        for start, end, style2 in sorted(edits, reverse=True):
            html = html[:start] + style2 + html[end:]
        page.write_text(html, encoding="utf-8")
        print(f"round {rnd + 1}: {len(edits)} elements moved")
        if not args.apply:
            break
        # re-render for the next round
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "scripts/render_check.py"), slug],
                       capture_output=True, cwd=ROOT)
        ren = Image.open(shot).convert("RGB")
        ren1x = np.asarray(ren.resize((ren.width // 2, ren.height // 2), Image.LANCZOS)).astype(int)

    for el, dy, dx, run in moves:
        print(f"  dy{dy:+5.1f} dx{dx:+5.1f}  {run['text'][:26]}")
    if args.apply:
        print(f"applied to {page}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
