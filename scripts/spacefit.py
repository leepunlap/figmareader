#!/usr/bin/env python3
"""Solve the *spacing* of one source text line.

The Figma export lays its paragraphs out in PingFang SC, where the ASCII space
is wider than the space of the self-hosted Noto Sans TC Latin face, so a line
whose text has no spaces comes out visibly shorter than the export.  Instead
of guessing those gap widths, this tool solves for them: a set of candidate
strings (with optional spaces at chosen character slots) is rendered in one
Chrome pass and every candidate is scored against the real source band with
the same metric as render_check.py (summed |dRGB| > 24).

  python3 scripts/spacefit.py \
      --src source/v1raw/screens/competition-detail-open.png \
      --y0 632 --y1 650 --x0 30 --x1 360 \
      --base "拉坯班（1.5小時）：適合9歲或以上兒童，學習" \
      --slots 3,11,13,14,21 \
      --fontcss assets/v1/competition-detail-open-fonts.css

`--slots` lists the character indices a space may be inserted *before*.
"""
import argparse
import itertools
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
WORK = Path("/tmp/spacefit")


def build_html(lines, fontcss, left, top0, lineh):
    head = ["<html><head><meta charset='utf-8'>",
            "<base href='file:///Users/blee/src/figma/'>",
            "<link rel='stylesheet' href='assets/fonts/fonts.css'>",
            "<link rel='stylesheet' href='styles-v1.css'>",
            "<link rel='stylesheet' href='assets/v1/noto-latin.css'>"]
    for f in fontcss:
        head.append("<link rel='stylesheet' href='%s'>" % f)
    head += ["<style>", "body{margin:0;background:#fff;}",
             "p{position:absolute;margin:0;",
             "  font-family:'Noto Sans TC Latin','Noto Sans TC',sans-serif;",
             "  font-size:14px;color:#000;white-space:pre;line-height:1;left:%fpx;}" % left,
             "</style></head><body>"]
    for i, (txt, ws) in enumerate(lines):
        head.append("<p style='top:%fpx;word-spacing:%fpx'>%s</p>"
                    % (top0 + i * lineh, ws, txt))
    head.append("</body></html>")
    return "\n".join(head)


def render(html, out_png, width, height):
    WORK.mkdir(parents=True, exist_ok=True)
    page = WORK / "probe.html"
    page.write_text(html, encoding="utf-8")
    if out_png.exists():
        out_png.unlink()
    prof = WORK / "prof"
    shutil.rmtree(prof, ignore_errors=True)
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
           "--no-default-browser-check", "--disable-extensions", "--allow-file-access-from-files",
           "--force-device-scale-factor=2", "--virtual-time-budget=20000",
           f"--user-data-dir={prof}", f"--window-size={width},{height}",
           f"--screenshot={out_png}", f"file://{page}"]
    subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    shutil.rmtree(prof, ignore_errors=True)
    return out_png.exists()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--y0", type=float, required=True)
    ap.add_argument("--y1", type=float, required=True)
    ap.add_argument("--ink-top", type=float, default=0.0,
                    help="css y of the source ink top; the probe line is placed so its "
                         "ink lands on the same row (0 if --y0 is already that row)")
    ap.add_argument("--x0", type=float, default=30)
    ap.add_argument("--x1", type=float, default=360)
    ap.add_argument("--base", required=True)
    ap.add_argument("--slots", default="",
                    help="comma separated character indices to insert a space before")
    ap.add_argument("--fontcss", default="assets/v1/competition-detail-open-fonts.css")
    ap.add_argument("--left", type=float, default=39.82)
    ap.add_argument("--ws", default="0,0.5,1.0,1.25,1.5,1.75,2.0,2.5")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    src4 = Image.open(args.src).convert("RGB")
    s2 = np.asarray(src4.resize((src4.width // 2, src4.height // 2), Image.LANCZOS))
    band_h = args.y1 - args.y0
    # The source band and the probe band must start at the same offset inside
    # the line box, otherwise a 1 px vertical shift hides the real optimum.
    top0 = args.ink_top - 0.99 if args.ink_top else args.y0
    src_top = top0
    y0, y1 = int(src_top * 2), int((src_top + band_h) * 2)
    x0, x1 = int(args.x0 * 2), int(args.x1 * 2)
    src_band = s2[y0:y1, x0:x1]

    slots = [int(s) for s in args.slots.split(",") if s.strip() != ""]
    ws_list = [float(w) for w in args.ws.split(",")]

    cands = []
    for mask in itertools.product([0, 1], repeat=len(slots)):
        chars = list(args.base)
        for si, has in sorted(zip(slots, mask), reverse=True):
            if has:
                chars.insert(si, " ")
        s = "".join(chars)
        for ws in ws_list:
            cands.append((s, ws))
    print("candidates:", len(cands))

    LINEH = 26.0
    TOP0 = top0
    out_png = WORK / "probe.png"
    results = []
    CHUNK = 36
    for st in range(0, len(cands), CHUNK):
        sub = cands[st:st + CHUNK]
        html = build_html(sub, [args.fontcss], args.left, TOP0, LINEH)
        height = int(TOP0 + len(sub) * LINEH + 60)
        if not render(html, out_png, 700, height):
            print("[error] chrome produced no screenshot")
            return 1
        a = np.asarray(Image.open(out_png).convert("RGB"))
        for i, (txt, ws) in enumerate(sub):
            band = a[int((TOP0 + i * LINEH) * 2):int((TOP0 + i * LINEH + 18) * 2), x0:x1]
            d = np.abs(src_band.astype(int) - band.astype(int)).sum(axis=2)
            results.append((float((d > 24).mean() * 100), txt, ws))
        print("  ...%d/%d" % (min(st + CHUNK, len(cands)), len(cands)))

    results.sort(key=lambda r: r[0])
    print("\nTOP 10:")
    for sc, txt, ws in results[:10]:
        print("  %6.2f%%  ws=%-5s %s" % (sc, ws, txt))
    if args.out:
        Path(args.out).write_text(json.dumps(
            [{"pct": r[0], "text": r[1], "word_spacing": r[2]} for r in results[:20]],
            ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
