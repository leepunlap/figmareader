#!/usr/bin/env python3
"""
Find the (family, size, weight) that reproduces a piece of the Figma export.

For each sample we know the source's ink bounding box, ink height and stroke
coverage.  We render the same string in every candidate configuration and pick
the configuration whose ink box / height / coverage land closest.

  python3 scripts/type_match.py lion-03 --samples samples.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/figma-type-match")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_check import SCREENS  # noqa: E402


def load2x(p: Path) -> np.ndarray:
    im = Image.open(p).convert("RGB")
    if im.width // 4 in (390, 402) and im.width % 4 == 0:
        im = im.resize((im.width // 2, im.height // 2), Image.LANCZOS)
    return np.asarray(im).astype(np.int32)


def ink_metrics(a: np.ndarray, rect, bg, tol: int):
    x0, x1, y0, y1 = rect
    band = a[y0 * 2:y1 * 2, x0 * 2:x1 * 2]
    d = np.abs(band - np.array(bg, dtype=np.int32)).sum(axis=2)
    m = d > tol
    ys, xs = m.nonzero()
    if len(xs) == 0:
        return None
    w = (xs.max() + 1 - xs.min()) / 2
    h = (ys.max() + 1 - ys.min()) / 2
    area = (xs.max() + 1 - xs.min()) * (ys.max() + 1 - ys.min())
    return {"w": w, "h": h, "ink": int(m.sum()), "cov": m.sum() / area * 100}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("screen")
    ap.add_argument("--samples", required=True, help="json: [{name,rect,bg,tol,text}]")
    ap.add_argument("--out")
    args = ap.parse_args()

    samples = json.loads(Path(args.samples).read_text())
    src = load2x(ROOT / SCREENS[args.screen]["source"])

    targets = []
    for s in samples:
        hexs = s["bg"].lstrip("#")
        bg = tuple(int(hexs[i:i + 2], 16) for i in (0, 2, 4))
        m = ink_metrics(src, s["rect"], bg, s.get("tol", 30))
        targets.append({**s, "bg_rgb": bg, "target": m})
        print(f"{s['name']:16s} target {m}")

    # ---- candidate grid -------------------------------------------------
    families = [
        ("Helvetica", "Helvetica, Arial, sans-serif"),
        ("HelveticaNeue", "'Helvetica Neue', Helvetica, sans-serif"),
        ("Arial", "Arial, sans-serif"),
        ("Poppins", "'Poppins', sans-serif"),
        ("PingFang", "'PingFang TC', sans-serif"),
        ("NotoSansTC", "'Noto Sans TC', sans-serif"),
        ("Avenir", "'Avenir Next', sans-serif"),
    ]
    sizes = [11, 12, 13, 14, 15, 16, 17]
    weights = [400, 500, 700]

    WORK.mkdir(parents=True, exist_ok=True)
    rows = []
    for t in targets:
        for fam, stack in families:
            for sz in sizes:
                for wt in weights:
                    rows.append((t["name"], fam, stack, sz, wt, t["text"]))

    html = ["<!DOCTYPE html><html><head><meta charset='utf-8'>",
            f"<link rel='stylesheet' href='file://{ROOT}/assets/fonts/fonts.css'>",
            f"<link rel='stylesheet' href='file://{ROOT}/assets/lion/lion-03-fonts.css'>",
            "<style>html,body{margin:0;background:#fff}"
            "div.t{position:absolute;left:12px;white-space:nowrap;color:#000;line-height:1}</style>",
            "</head><body>"]
    y = 0
    spans = []
    for i, (name, fam, stack, sz, wt, text) in enumerate(rows):
        html.append(f"<div class='t' id='s{i}' style='top:{y}px;font-size:{sz}px;"
                    f"font-weight:{wt};font-family:{stack}'>{text}</div>")
        spans.append((i, int(y), int(sz)))
        y += int(sz * 1.6) + 6
    html.append("</body></html>")
    page = WORK / "cand.html"
    page.write_text("\n".join(html))

    shot = WORK / "cand.png"
    if shot.exists():
        shot.unlink()
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--no-first-run", "--allow-file-access-from-files",
           "--force-device-scale-factor=2", "--virtual-time-budget=20000",
           f"--user-data-dir={WORK}/profile", "--window-size=420,%d" % (int(y) + 60),
           f"--screenshot={shot}", f"file://{page}"]
    subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if not shot.exists():
        print("chrome produced no screenshot")
        return 1
    img = np.asarray(Image.open(shot).convert("RGB")).astype(np.int32)
    ink = (img.sum(axis=2) < 690)

    # split the screenshot into rows by detecting the div baselines
    per = {}
    for i, y0, sz in spans:
        band = ink[y0 * 2:(y0 + int(sz * 1.8)) * 2]
        ys, xs = band.nonzero()
        if len(xs) == 0:
            continue
        x0 = xs.min() / 2
        x1 = (xs.max() + 1) / 2
        yy0 = ys.min() / 2 + y0
        yy1 = (ys.max() + 1) / 2 + y0
        area = (xs.max() + 1 - xs.min()) * (ys.max() + 1 - ys.min())
        per[i] = {"w": x1 - x0, "h": yy1 - yy0, "cov": band.sum() / area * 100}

    # ---- score ----------------------------------------------------------
    scored = {}
    for idx, (name, fam, stack, sz, wt, text) in enumerate(rows):
        r = per.get(idx)
        if not r:
            continue
        tg = next(t for t in targets if t["name"] == name)["target"]
        if not tg:
            continue
        dw = abs(r["w"] - tg["w"])
        dh = abs(r["h"] - tg["h"])
        dc = abs(r["cov"] - tg["cov"]) / 4
        score = dw + dh * 1.5 + dc
        scored.setdefault(name, []).append((score, fam, sz, wt, r, tg))
    for k in scored:
        scored[k].sort(key=lambda x: x[0])
    best = {k: v[0] for k, v in scored.items()}

    print()
    for t in targets:
        if t["name"] not in best:
            continue
        score, fam, sz, wt, r, tg = best[t["name"]]
        print(f"{t['name']:16s} -> {fam:14s} {sz:5}px w{wt}  "
              f"w {r['w']:6.1f} (t {tg['w']:6.1f})  h {r['h']:5.1f} (t {tg['h']:5.1f})  "
              f"cov {r['cov']:5.1f} (t {tg['cov']:5.1f})  score {score:.2f}")
        for sc, fm, s2, w2, r2, t2 in scored[t["name"]][1:9]:
            print(f"{'':16s}    alt {fm:14s} {s2:5}px w{w2}  "
                  f"w {r2['w']:6.1f}  h {r2['h']:5.1f}  cov {r2['cov']:5.1f}  score {sc:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
