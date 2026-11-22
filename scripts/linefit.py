#!/usr/bin/env python3
"""Align every text line of a page to the export, one line at a time.

The OCR box tells us where the export's glyphs are, but the subset font puts
its ink at a different offset inside the line box, so a line placed straight
from the OCR box can sit a couple of pixels off -- and a couple of pixels is
enough to make every stroke of that line "hot" in the pixel diff.

This measures each line independently, by correlating the export's ink
profile with the render's, and rewrites the inline `left` / `top` of the
matching <p> so the glyphs land on the export's pixels.

    python3 scripts/linefit.py v1-competition-detail-closed            # report
    python3 scripts/linefit.py v1-competition-detail-closed --apply
    python3 scripts/linefit.py v1-competition-detail-closed --apply --rounds 2

Only inline left/top of <p> elements are rewritten; stylesheets are never
touched.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-render")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

TAG_RE = re.compile(r"<p\b[^>]*>")
STYLE_RE = re.compile(r'style="([^"]*)"')
LEFT_RE = re.compile(r"(left:\s*)(-?[\d.]+)px")
TOP_RE = re.compile(r"(top:\s*)(-?[\d.]+)px")


def source_png(slug: str) -> Path:
    if slug.startswith("v73-"):
        return ROOT / "source/v1raw73/screens" / f"{slug}.png"
    return ROOT / "source/v1raw/screens" / f"{slug[3:]}.png"


def prepare(page: Path) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    out = WORK / page.name
    html = page.read_text(encoding="utf-8")
    html = html.replace("<body>", '<body class="render">')
    html = html.replace("<head>", '<head>\n<base href="file://%s/">' % ROOT, 1)
    out.write_text(html, encoding="utf-8")
    return out


def render(page: Path, width: int, height: int, out: Path) -> None:
    profile = WORK / f"lf-{__import__('os').getpid()}"
    shutil.rmtree(profile, ignore_errors=True)
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--no-first-run", "--no-default-browser-check", "--disable-extensions",
           "--allow-file-access-from-files", "--force-device-scale-factor=2",
           "--virtual-time-budget=12000", "--user-data-dir=%s" % profile,
           "--window-size=%d,%d" % (width, height),
           "--screenshot=%s" % out, "file://%s" % page]
    subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    shutil.rmtree(profile, ignore_errors=True)


def ink_profile(img: np.ndarray, y0: int, y1: int, x0: int, x1: int):
    """Row ink profile (sum of darkness) of a region, plus the ink column profile."""
    reg = img[y0 * 2:y1 * 2, x0 * 2:x1 * 2]
    if reg.size == 0:
        return None, None
    dark = (255 - reg.mean(axis=2)).clip(0)
    return dark.sum(axis=1), dark.sum(axis=0)


def best_shift(src_prof, ren_prof, radius: int):
    """Shift (in css px) that best matches two 1-D profiles."""
    if src_prof is None or ren_prof is None or len(src_prof) == 0:
        return 0
    s = src_prof.astype(float)
    s = s - s.mean()
    sn = np.linalg.norm(s)
    best = (0.0, 0)
    for k in range(-radius, radius + 1):
        # ren shifted by k css px == 2k device rows
        j = 2 * k
        if j >= 0:
            r = ren_prof[j:j + len(s)]
            if len(r) < len(s):
                continue
        else:
            r = ren_prof[0:len(s) + j]
            if len(r) < len(s):
                continue
        r = r.astype(float)
        r = r - r.mean()
        d = np.linalg.norm(r)
        if sn == 0 or d == 0:
            continue
        c = float((s * r).sum() / (sn * d))
        if c > best[0]:
            best = (c, k)
    return best[1]


def band_hot(src: np.ndarray, ren: np.ndarray, y0: int, y1: int, x0: int, x1: int,
             dx: float = 0.0, dy: float = 0.0) -> float:
    """Hot fraction of a band, with the render shifted by (dx, dy) css px."""
    reg = ren[y0 * 2:y1 * 2, x0 * 2:x1 * 2]
    if reg.size == 0:
        return 1.0
    if dx or dy:
        img = Image.fromarray(reg.astype(np.uint8))
        img = img.transform(img.size, Image.AFFINE, (1, 0, -dx * 2, 0, 1, -dy * 2),
                            resample=Image.BICUBIC)
        reg = np.asarray(img).astype(int)
    a = src[y0 * 2:y1 * 2, x0 * 2:x1 * 2]
    return float((np.abs(a - reg).sum(axis=2) > 24).mean())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--radius", type=int, default=7)
    ap.add_argument("--work", default=WORK, help="scratch dir for the render")
    args = ap.parse_args()

    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    globals()["WORK"] = work

    slug = args.slug
    page = ROOT / f"{slug}.html"
    runs = json.load(open(ROOT / "analysis/ocr" / f"{slug}-fit.json"))
    src_im = Image.open(source_png(slug)).convert("RGB")
    w, h = src_im.size[0] // 4, src_im.size[1] // 4

    # the <p> elements that carry an inline left/top, in document order
    html = page.read_text(encoding="utf-8")

    def collect(text: str):
        out = []
        for m in TAG_RE.finditer(text):
            tag = m.group(0)
            sm = STYLE_RE.search(tag)
            if not sm:
                continue
            style = sm.group(1)
            if "left:" not in style or "top:" not in style:
                continue
            lm = LEFT_RE.search(style)
            tm = TOP_RE.search(style)
            if not lm or not tm:
                continue
            out.append((m.start(), m.end(), float(lm.group(2)), float(tm.group(2))))
        return out

    for rnd in range(args.rounds):
        prepared = prepare(page)
        out_png = WORK / f"{slug}.png"
        if out_png.exists():
            out_png.unlink()
        render(prepared, w, h, out_png)
        if not out_png.exists():
            raise SystemExit("[error] render failed")
        ren = np.asarray(Image.open(out_png).convert("RGB")).astype(int)
        src = np.asarray(src_im.resize((w * 2, h * 2), Image.LANCZOS)).astype(int)

        ps = collect(html)
        moves = []
        for idx, (s0, e0, left, top) in enumerate(ps):
            # find the OCR run that sits at this position
            run = None
            for r in runs:
                if abs(float(r["fit"]["left"]) - left) < 3 and abs(float(r["fit"]["top"]) - top) < 6:
                    run = r
                    break
            if run is None:
                continue
            rx0 = int(run["src_x0"]); rx1 = int(run["src_x1"])
            ry0 = int(run["src_y0"]); ry1 = int(run["src_y1"])
            # The render's window must START at the same row as the source's,
            # otherwise the correlation is biased by half the search radius.
            sy0 = max(0, ry0 - 2); sy1 = min(h, ry1 + 2)
            wy0 = sy0
            wy1 = min(h, sy1 + 2 * args.radius)
            wx0 = max(0, rx0 - 6); wx1 = min(w, rx1 + 6)
            sp, _ = ink_profile(src, sy0, sy1, wx0, wx1)
            rp, _ = ink_profile(ren, wy0, wy1, wx0, wx1)
            if sp is None or rp is None:
                continue
            dy = best_shift(sp, rp, args.radius)
            # now the horizontal shift, using the rows of the source line
            ry0b = max(0, sy0 + dy); ry1b = min(h, sy1 + dy)
            _, sc = ink_profile(src, sy0, sy1, wx0, wx1)
            _, rc = ink_profile(ren, ry0b, ry1b, wx0, wx1)
            dx = best_shift(sc, rc, args.radius) if sc is not None and rc is not None else 0
            if not (dx or dy):
                continue
            # only keep a move that measurably improves the band
            bx0 = max(0, rx0 - 4); bx1 = min(w, rx1 + 4)
            by0 = max(0, ry0 - 3); by1 = min(h, ry1 + 3)
            before = band_hot(src, ren, by0, by1, bx0, bx1)
            after = band_hot(src, ren, by0, by1, bx0, bx1, dx, dy)
            if after < before - 0.002:
                moves.append((s0, e0, left, top, dx, dy, run["text"],
                              (before, after)))
            else:
                print("   skip  %-34s  hot %.3f -> %.3f (no better)"
                      % (run["text"][:34], before * 100, after * 100))

        print("round %d: %d runs to move" % (rnd + 1, len(moves)))
        for s0, e0, left, top, dx, dy, text, (b, a) in moves:
            print("   dx %+d dy %+d  hot %.3f -> %.3f  %s" % (dx, dy, b * 100, a * 100, text[:36]))

        if not args.apply:
            if rnd + 1 < args.rounds:
                print("(report mode: no change written)")
            break

        # apply, back to front so the offsets stay valid
        for s0, e0, left, top, dx, dy, text, _ba in reversed(moves):
            tag = html[s0:e0]
            sm = STYLE_RE.search(tag)
            style = sm.group(1)
            new = LEFT_RE.sub(lambda m: "%s%.2fpx" % (m.group(1), float(m.group(2)) + dx), style)
            new = TOP_RE.sub(lambda m: "%s%.2fpx" % (m.group(1), float(m.group(2)) + dy), new)
            html = html[:s0] + tag[:sm.start()] + 'style="%s"' % new + tag[sm.end():] + html[e0:]
        page.write_text(html, encoding="utf-8")
        print("   applied")


if __name__ == "__main__":
    main()
