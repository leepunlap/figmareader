#!/usr/bin/env python3
"""Compare text bands of the export and the render, registered in sub-pixel.

The bands in a text row differ for three reasons: the glyphs sit in the wrong
place, they are the wrong weight, or the rasteriser disagrees.  This tool
removes the placement question first -- it shifts the render by a fraction of
a pixel (bicubic resample) until it lines up with the export, and only then
reports how much of the band still differs.

  python3 scripts/bandfit.py v1-competition-detail-closed --bands 540-560,660-680
  python3 scripts/bandfit.py v1-competition-detail-closed --bands 540-560 --compare-weights 400,500
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-render")
# a private work directory keeps the tool from stepping on another agent's
# render while a worker is measuring the same slug
if os.environ.get("BANDFIT_WORK"):
    WORK = Path(os.environ["BANDFIT_WORK"])
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def load(slug: str):
    p = ROOT / "source/v1raw/screens" / f"{slug.replace('v1-', '')}.png"
    if not p.exists():
        p = ROOT / "source/v1raw73/screens" / f"{slug}.png"
    src = Image.open(p).convert("RGB")
    r = Image.open(WORK / f"{slug}.png").convert("RGB")
    if r.size != src.size:
        src = src.resize(r.size, Image.LANCZOS)
    return np.asarray(src).astype(int), np.asarray(r).astype(int)


def shift(img: Image.Image, dx: float, dy: float) -> Image.Image:
    """Shift by (dx, dy) css pixels using a bicubic resample."""
    if dx == 0 and dy == 0:
        return img
    w, h = img.size
    return img.transform((w, h), Image.AFFINE, (1, 0, -dx * 2, 0, 1, -dy * 2),
                          resample=Image.BICUBIC)


def best_band(src_img: Image.Image, ren_img: Image.Image, y0: int, y1: int,
              x0: int = 0, x1: int = 402, step: float = 0.5, reach: int = 4):
    """Best registered hot fraction for one band, searching a sub-pixel shift."""
    # crop first -- resampling the whole page per shift is far too slow
    pad = int(reach * 2) + 4
    sy0 = max(0, y0 * 2 - pad)
    sy1 = min(src_img.size[1], y1 * 2 + pad)
    sx0 = max(0, x0 * 2)
    sx1 = min(src_img.size[0], x1 * 2)
    a = np.asarray(src_img.crop((sx0, sy0, sx1, sy1))).astype(int)

    # the band's own rows inside the crop
    by0 = y0 * 2 - sy0
    by1 = y1 * 2 - sy0
    best = (1.0, 0.0, 0.0)
    for dy in np.arange(-reach, reach + 0.001, step):
        for dx in np.arange(-reach, reach + 0.001, step):
            r = np.asarray(shift(ren_img.crop((sx0, sy0, sx1, sy1)), dx, dy)).astype(int)
            d = (np.abs(a[by0:by1] - r[by0:by1]).sum(axis=2) > 24).mean()
            if d < best[0]:
                best = (d, dx, dy)
    return best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--bands", required=True)
    ap.add_argument("--compare-weights", default="")
    ap.add_argument("--variants", default="", help="name=css;;name=css  extra CSS per variant")
    ap.add_argument("--css", default="")
    ap.add_argument("--sel", default="")
    args = ap.parse_args()

    slug = args.slug
    bands = []
    for part in args.bands.split(","):
        y0, y1 = (int(v) for v in part.split("-"))
        bands.append((y0, y1))

    if args.compare_weights or args.variants:
        css_path = ROOT / args.css
        page = ROOT / f"{slug}.html"
        orig_css = css_path.read_text(encoding="utf-8")
        orig_html = page.read_text(encoding="utf-8")
        html = orig_html.replace("<body>", '<body class="render">').replace(
            "<head>", '<head>\n<base href="file://%s/">' % ROOT, 1)
        p2 = WORK / f"{slug}.html"
        src_im = Image.open(ROOT / ("source/v1raw73/screens/%s.png" % slug if slug.startswith("v73-")
                                   else "source/v1raw/screens/%s.png" % slug[3:])).convert("RGB")
        w, h = src_im.size[0] // 4, src_im.size[1] // 4

        if args.variants:
            trials = []
            for part in args.variants.split(";;"):
                name, _, css = part.partition("=")
                trials.append((name, css))
        else:
            trials = [("weight %d" % wt, "%s { font-weight: %d !important; }" % (args.sel, wt))
                      for wt in (int(v) for v in args.compare_weights.split(","))]

        try:
            for name, extra_css in trials:
                # inject the override into the rendered copy only -- never touch
                # the stylesheet on disk, so an interrupted run cannot leave it
                # modified
                p2.write_text(html.replace("</head>",
                                           "<style>%s</style>\n</head>" % extra_css),
                              encoding="utf-8")
                out = WORK / f"{slug}.png"
                if out.exists():
                    out.unlink()
                prof = WORK / f"bf-{__import__('os').getpid()}"
                cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                       "--no-first-run", "--no-default-browser-check", "--disable-extensions",
                       "--allow-file-access-from-files", "--force-device-scale-factor=2",
                       "--virtual-time-budget=12000", "--user-data-dir=%s" % prof,
                       "--window-size=%d,%d" % (w, h), "--screenshot=%s" % out,
                       "file://%s" % p2]
                subprocess.run(cmd, capture_output=True, text=True, timeout=180)
                shutil.rmtree(prof, ignore_errors=True)
                ren = Image.open(out).convert("RGB")
                src2 = src_im.resize(ren.size, Image.LANCZOS)
                A = np.asarray(src2).astype(int)
                R = np.asarray(ren).astype(int)
                page_pct = float((np.abs(A - R).sum(axis=2) > 24).mean() * 100)
                tot = 0.0
                print("variant: %s   page diff %.2f%%" % (name, page_pct))
                for (y0, y1) in bands:
                    d, dx, dy = best_band(src2, ren, y0, y1)
                    tot += d
                    print("   band %5d-%5d  hot %5.2f%%  (registered dx %+.1f dy %+.1f)"
                          % (y0, y1, d * 100, dx, dy))
                print("   mean band hot %.2f%%" % (tot / len(bands) * 100))
        finally:
            page.write_text(orig_html, encoding="utf-8")
        return

    src, ren = load(slug)
    src_img = Image.fromarray(src.astype(np.uint8))
    ren_img = Image.fromarray(ren.astype(np.uint8))
    for (y0, y1) in bands:
        d, dx, dy = best_band(src_img, ren_img, y0, y1)
        print("band %5d-%5d  hot %5.2f%%  (registered dx %+.1f dy %+.1f)"
              % (y0, y1, d * 100, dx, dy))


if __name__ == "__main__":
    main()
