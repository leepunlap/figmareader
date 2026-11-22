#!/usr/bin/env python3
"""
Which installed CJK face reproduces the Lion export's glyph outlines best?

The export's typeface is unknown, so this compares the source's own crop of a
CJK string against the same string rendered in every candidate family/weight.
Both are cropped to their ink box and normalised, so only the *shape* of the
glyphs is compared — size and position are factored out.

  python3 scripts/glyph_match.py lion-03 --text 有間畫室 --rect 120,189,62,15
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-glyph-match")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_check import SCREENS  # noqa: E402

FAMILIES = [
    ("NotoSansTC", "'Noto Sans TC', sans-serif"),
    ("PingFangTC", "'PingFang TC', sans-serif"),
    ("HeitiTC", "'Heiti TC', sans-serif"),
    ("HiraginoSansGB", "'Hiragino Sans GB', sans-serif"),
    ("HiraginoSansCNS", "'Hiragino Sans CNS', sans-serif"),
    ("LantingheiTC", "'Lantinghei TC', sans-serif"),
    ("SongtiTC", "'Songti TC', sans-serif"),
    ("AppleLiGothic", "'Apple LiGothic', sans-serif"),
    ("ArialUnicodeMS", "'Arial Unicode MS', sans-serif"),
    ("STHeiti", "'STHeiti', sans-serif"),
    ("Yuanti", "'Yuanti SC', sans-serif"),
    ("Wawati", "'Wawati SC', sans-serif"),
    ("Hannotate", "'Hannotate SC', sans-serif"),
    ("Libian", "'Libian SC', sans-serif"),
    ("Weibei", "'Weibei SC', sans-serif"),
    ("Baoli", "'Baoli SC', sans-serif"),
]
WEIGHTS = [400, 500, 600, 700, 800, 900]


def load2x(path: Path) -> Image.Image:
    im = Image.open(path).convert("RGB")
    if im.width // 4 in (390, 402) and im.width % 4 == 0:
        im = im.resize((im.width // 2, im.height // 2), Image.LANCZOS)
    return im


def ink_mask(arr: np.ndarray, bg) -> np.ndarray:
    d = np.abs(arr - np.array(bg, dtype=np.int32)).sum(axis=2)
    return d > 30


def crop_norm(mask: np.ndarray) -> np.ndarray:
    ys, xs = mask.nonzero()
    if len(xs) == 0:
        return np.zeros((64, 64), dtype=np.float32)
    sub = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    im = Image.fromarray((sub * 255).astype(np.uint8)).resize((64, 64), Image.BILINEAR)
    return np.asarray(im).astype(np.float32) / 255.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("screen")
    ap.add_argument("--text", required=True)
    ap.add_argument("--rect", required=True, help="x,y,w,h in css px")
    ap.add_argument("--bg", default="#ffffff")
    ap.add_argument("--sizes", default="")
    args = ap.parse_args()

    x, y, w, h = (int(v) for v in args.rect.split(","))
    hexs = args.bg.lstrip("#")
    bg = tuple(int(hexs[i:i + 2], 16) for i in (0, 2, 4))

    src = load2x(ROOT / SCREENS[args.screen]["source"])
    band = np.asarray(src).astype(np.int32)[y * 2:(y + h) * 2, x * 2:(x + w) * 2]
    smask = ink_mask(band, bg)
    ref = crop_norm(smask)
    ref_ink = float(smask.sum()) / smask.size
    print(f"source ink coverage {ref_ink * 100:.1f} %  (crop {smask.shape[1] // 2}x{smask.shape[0] // 2} css px)")

    sizes = [float(v) for v in args.sizes.split(",")] if args.sizes else [14, 15, 16, 18, 20, 22]
    rows = [(f, stack, wt, sz) for f, stack in FAMILIES for wt in WEIGHTS for sz in sizes]

    WORK.mkdir(parents=True, exist_ok=True)
    html = ["<!DOCTYPE html><html><head><meta charset='utf-8'>",
            f"<link rel='stylesheet' href='file://{ROOT}/assets/fonts/fonts.css'>",
            f"<link rel='stylesheet' href='file://{ROOT}/assets/lion/lion-03-fonts.css'>",
            "<style>html,body{margin:0;background:#fff}"
            "div.t{position:absolute;left:12px;white-space:nowrap;color:#000;line-height:1}</style>",
            "</head><body>"]
    y0 = 0
    spans = []
    for i, (f, stack, wt, sz) in enumerate(rows):
        html.append(f"<div class='t' style='top:{y0}px;font-size:{sz}px;font-weight:{wt};"
                    f"font-family:{stack}'>{args.text}</div>")
        spans.append((i, y0, sz))
        y0 += int(sz * 1.7) + 8
    html.append("</body></html>")
    page = WORK / "cand.html"
    page.write_text("\n".join(html))
    shot = WORK / "cand.png"
    if shot.exists():
        shot.unlink()
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
           "--allow-file-access-from-files", "--force-device-scale-factor=2",
           "--virtual-time-budget=30000", f"--user-data-dir={WORK}/profile",
           "--window-size=520,%d" % (y0 + 60), f"--screenshot={shot}", f"file://{page}"]
    subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if not shot.exists():
        print("chrome produced no screenshot")
        return 1
    img = np.asarray(Image.open(shot).convert("RGB")).astype(np.int32)
    ink = ink_mask(img, (255, 255, 255))

    results = []
    for i, y0, sz in spans:
        band = ink[y0 * 2:(y0 + int(sz * 1.5)) * 2]
        m = crop_norm(band)
        if m.sum() == 0:
            continue
        diff = float(np.abs(m - ref).mean())
        cov = float((band.sum() / max(1, band.size)))
        f, stack, wt, s = rows[i]
        results.append((diff, f, wt, s, cov))
    results.sort()
    print(f"\n{'family':18s} {'wt':>4s} {'size':>5s} {'shape diff':>11s}")
    for diff, f, wt, s, cov in results[:12]:
        print(f"{f:18s} {wt:4d} {s:5g} {diff * 100:10.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
