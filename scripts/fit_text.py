#!/usr/bin/env python3
"""
Fit a typeface / size / tracking to one line of text in a source export.

The full-page diff metric is diluted by everything else on the screen, which
makes font experiments useless.  This tool isolates a single text line:

  * crops the line out of the 4x Figma export (LANCZOS-downscaled to 2x),
  * renders the same string in a candidate font at 2x in headless Chrome,
  * reports the pixel difference over that rectangle only.

  python3 scripts/fit_text.py --source source/lion/lion-11-chat-2.png \
      --rect 73,545,240,14 --text "活動日期係2026年2月28日。內容包括一" \
      --family "PingFang TC" --size 14 --tracking 0

Multiple --family / --size / --tracking combinations are compared in one pass.
"""

from __future__ import annotations

import argparse
import itertools
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def render_lines(cands, text, weight, bg, size_scale=2, cols=4, cell_w=320, cell_h=40,
                 base_png=None, base_px=(0, 0)):
    """Render every candidate in a grid of cells; return (image, cols, cell, scale).

    When `base_png` is given it is used as the cell background so the candidate
    text is composited over the *source* pixels: only the glyphs then differ.
    """
    import base64
    html = ["<html><head><meta charset='utf-8'>"]
    # link the project's self-hosted subsets with *relative* paths: the probe
    # file is written into the workspace so the browser can resolve them
    for sheet in ("assets/fonts/fonts.css", "assets/lion/lion-11-fonts.css",
                  "assets/lion/lion-03-fonts.css"):
        if (ROOT / sheet).exists():
            html.append("<link rel='stylesheet' href='%s'>" % sheet)
    html.append("<style>html,body{margin:0;background:%s}" % bg)
    if base_png is not None:
        data = base64.b64encode(base_png.read_bytes()).decode()
        html.append(
            ".cell{position:absolute;width:%dpx;height:%dpx;"
            "background-image:url(data:image/png;base64,%s);"
            "background-size:%dpx %dpx;background-repeat:no-repeat;}"
            % (base_px[0], base_px[1], data, base_px[0], base_px[1])
        )
    for i, c in enumerate(cands):
        r, col = divmod(i, cols)
        html.append(
            ".c%d{position:absolute;left:%gpx;top:%dpx;font-family:'%s';"
            "font-size:%gpx;font-weight:%d;letter-spacing:%gpx;"
            "white-space:pre;line-height:1;color:#000000;}"
            % (i, col * cell_w + c.get("dxf", 0), r * cell_h + c.get("dy", 0),
               c["family"], c["size"], c["weight"], c["tracking"])
        )
    html.append("</style></head><body>")
    if base_png is not None:
        for r in range((len(cands) + cols - 1) // cols):
            for col in range(cols):
                html.append("<div class='cell' style='left:%dpx;top:%dpx'></div>"
                            % (col * cell_w, r * cell_h))
    for i, c in enumerate(cands):
        html.append("<span class='c%d'>%s</span>" % (i, text))
    html.append("</body></html>")

    rows = (len(cands) + cols - 1) // cols
    # the probe must live in the workspace so the relative font paths resolve
    probe = ROOT / f".fit_text_probe_{os.getpid()}.html"
    try:
        probe.write_text("".join(html), encoding="utf-8")
        prof = Path(tempfile.mkdtemp())
        out = prof / "t.png"
        subprocess.run([
            CHROME, "--headless=new", f"--user-data-dir={prof}", "--no-sandbox",
            "--hide-scrollbars", "--allow-file-access-from-files",
            "--force-device-scale-factor=%d" % size_scale,
            "--virtual-time-budget=3000",
            "--window-size=%d,%d" % (cols * cell_w, rows * cell_h + 40),
            f"--screenshot={out}", probe.as_uri(),
        ], check=False, capture_output=True)
        if not out.exists():
            raise SystemExit("chrome failed to render")
        return Image.open(out).convert("L"), cols, (cell_w, cell_h), size_scale
    finally:
        try:
            probe.unlink()
        except OSError:
            pass
        shutil.rmtree(prof, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--rect", required=True, help="x,y,w,h in css px")
    ap.add_argument("--text", required=True)
    ap.add_argument("--family", action="append", default=[])
    ap.add_argument("--size", action="append", type=float, default=[])
    ap.add_argument("--tracking", action="append", type=float, default=[0])
    ap.add_argument("--weight", action="append", type=int, default=[400])
    ap.add_argument("--dump", default="",
                    help="write a side-by-side PNG of source vs best candidate")
    ap.add_argument("--scale", type=int, default=4,
                    help="render scale; the source is a 4x export")
    ap.add_argument("--dy", action="append", type=float, default=[0],
                    help="vertical offset applied to the candidate (css px)")
    ap.add_argument("--dx", action="append", type=float, default=[0],
                    help="fractional horizontal offset of the candidate (css px)")
    ap.add_argument("--ink-only", action="store_true",
                    help="compare only pixels that are ink in either image")
    ap.add_argument("--bg", default="#ffffff")
    args = ap.parse_args()

    x, y, w, h = [int(v) for v in args.rect.split(",")]
    src = Image.open(ROOT / args.source).convert("L")
    sscale = 4
    sc = src.crop((x * sscale, y * sscale, (x + w) * sscale, (y + h) * sscale))
    if args.scale != sscale:
        sc = sc.resize((w * args.scale, h * args.scale), Image.LANCZOS)
    src_a = np.asarray(sc).astype(int)

    # background = the brightest (mode) value of the source crop
    vals, counts = np.unique(src_a, return_counts=True)
    bg_val = int(vals[np.argmax(counts)])
    bg = "#%02x%02x%02x" % (bg_val, bg_val, bg_val)

    fams = args.family or ["Noto Sans TC"]
    sizes = args.size or [14]
    cands = [{"family": f, "size": s, "tracking": t, "dy": dy, "dxf": dx, "weight": wt}
             for f, s, t, dy, dx, wt in itertools.product(
                 fams, sizes, args.tracking, args.dy, args.dx, args.weight)]
    img, cols, (cell_w, cell_h), scale = render_lines(
        cands, args.text, args.weight, bg, args.scale)

    # source ink bbox ("text" = clearly darker than the background)
    s_thr = bg_val - 40
    sy, sx = np.nonzero(src_a < s_thr)
    if not len(sy):
        raise SystemExit("no ink found in the source rect")
    s_x0, s_x1, s_y0, s_y1 = sx.min(), sx.max(), sy.min(), sy.max()
    s_cy = (s_y0 + s_y1) / 2

    rows = []
    for i, c in enumerate(cands):
        r, col = divmod(i, cols)
        band = img.crop((col * cell_w * scale, r * cell_h * scale,
                         (col + 1) * cell_w * scale, (r + 1) * cell_h * scale))
        a = np.asarray(band).astype(int)
        cy_, cx_ = np.nonzero(a < s_thr)
        if not len(cy_):
            rows.append((999.0, c, None))
            continue
        dx = int(round(s_x0 - cx_.min()))
        dy = int(round(s_cy - (cy_.min() + cy_.max()) / 2))
        shifted = np.roll(np.roll(a, dy, axis=0), dx, axis=1)
        # compare over the source ink band only
        band_h = int(s_y1 - s_y0) + 4
        y0 = max(0, int(s_y0) - 2)
        y1 = min(src_a.shape[0], y0 + band_h)
        x1 = min(src_a.shape[1], shifted.shape[1])
        d = np.abs(src_a[y0:y1, :x1] - shifted[y0:y1, :x1])
        if args.ink_only:
            # ignore pixels that are background in BOTH images, so only the
            # glyph strokes are compared
            ink = (src_a[y0:y1, :x1] < s_thr) | (shifted[y0:y1, :x1] < s_thr)
            if ink.any():
                pct = float((d[ink] > 24).mean()) * 100
            else:
                pct = 0.0
        else:
            pct = float((d > 24).mean()) * 100
        width_ratio = (cx_.max() - cx_.min()) / max(1, (s_x1 - s_x0))
        rows.append((pct, c, (dx, dy, round(float(width_ratio), 3))))

    rows.sort(key=lambda r: r[0])
    print(f"source rect {x},{y},{w},{h} @{args.scale}x  bg=#{bg_val:02x}{bg_val:02x}{bg_val:02x}  "
          f"ink w={s_x1-s_x0+1} h={s_y1-s_y0+1}")
    for pct, c, shift in rows:
        fam, size, tr = c["family"], c["size"], c["tracking"]
        s = f"dx={shift[0]} dy={shift[1]} w_ratio={shift[2]}" if shift else ""
        print(f"  {pct:6.2f}%  {fam:24s} size={size:<6g} weight={c['weight']:<4g} "
              f"track={tr:<6g} dy={c['dy']:<5g} dxf={c['dxf']:<5g} {s}")

    if args.dump and rows and rows[0][1] is not None:
        best_i = cands.index(rows[0][1])
        r, col = divmod(best_i, cols)
        band = img.crop((col * cell_w * scale, r * cell_h * scale,
                         (col + 1) * cell_w * scale, (r + 1) * cell_h * scale))
        a = np.asarray(band).astype(int)
        cy_, cx_ = np.nonzero(a < s_thr)
        dx = int(round(s_x0 - cx_.min()))
        dy = int(round(s_cy - (cy_.min() + cy_.max()) / 2))
        shifted = np.roll(np.roll(a, dy, axis=0), dx, axis=1)
        src_img = Image.fromarray(src_a.astype("uint8"))
        cmp_img = Image.fromarray(shifted.astype("uint8"))
        wpx = min(src_img.width, cmp_img.width)
        hpx = min(src_img.height, cmp_img.height)
        out = Image.new("L", (wpx, hpx * 2 + 6), 255)
        out.paste(src_img.crop((0, 0, wpx, hpx)), (0, 0))
        out.paste(cmp_img.crop((0, 0, wpx, hpx)), (0, hpx + 6))
        out.save(args.dump)
        print(f"wrote {args.dump} (top = source, bottom = candidate)")


if __name__ == "__main__":
    main()
