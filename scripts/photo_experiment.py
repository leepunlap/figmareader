#!/usr/bin/env python3
"""
Experiment: find the photo-asset pipeline that best matches the verifier.

The verifier downsamples the whole 4x export with PIL LANCZOS to 2x and then
compares it with the browser render (captured at device scale 2).

For a photo placed at CSS (x, y) with size w x h, the browser draws the asset
1:1 in device pixels when the asset is already w*2 x h*2, at device position
(x*2, y*2).  The truth region is src2.crop((x*2, y*2, x*2+w*2, y*2+h*2)).

Strategies tested:
  A  crop 4x, then LANCZOS the crop down to 2x
  B  prescale the whole frame to 2x, then crop  (== the verifier exactly)
  C  crop 4x at 4x size, let Chrome downscale 4x->2x
  D  integer vs fractional CSS position

Usage: python3 scripts/photo_experiment.py
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/photo-exp")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SRC = ROOT / "source/lion/lion-03-org-feed-a.png"

PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8">
<style>html,body{{margin:0;padding:0;background:#fff8f4;}}
.p{{position:absolute;left:{left}px;top:{top}px;width:{w}px;height:{h}px;
border-radius:16px;overflow:hidden;}}
.p img{{display:block;width:100%;height:100%;}}</style></head>
<body><div class="p"><img src="file://{asset}"></div></body></html>"""


def src2() -> Image.Image:
    im = Image.open(SRC).convert("RGB")
    return im.resize((im.width // 2, im.height // 2), Image.LANCZOS)


def render(page: Path, out: Path) -> Image.Image:
    cmd = [
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--no-first-run", "--no-default-browser-check", "--disable-extensions",
        "--allow-file-access-from-files", "--force-device-scale-factor=2",
        "--virtual-time-budget=4000", "--user-data-dir=%s/profile" % WORK,
        "--window-size=390,400", "--screenshot=%s" % out, "file://%s" % page,
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    return Image.open(out).convert("RGB")


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    s2 = src2()
    src4 = Image.open(SRC).convert("RGB")

    # photo position measured from the design: card x 19.25 + 10.5 etc.
    for x, y, w, h in [(29.75, 185.75, 78, 78), (30, 186, 78, 78),
                       (29.5, 185.5, 78, 78), (29, 185, 78, 78)]:
        truth = np.asarray(s2.crop((int(x * 2), int(y * 2),
                                    int(x * 2) + w * 2, int(y * 2) + h * 2))).astype(int)
        variants = {}

        # A: crop 4x then downscale the crop
        c4 = src4.crop((int(x * 4), int(y * 4), int((x + w) * 4), int((y + h) * 4)))
        variants["A_crop4x_then_resize"] = c4.resize((w * 2, h * 2), Image.LANCZOS)

        # B: prescale the whole frame then crop
        variants["B_prescale2_then_crop"] = s2.crop(
            (int(x * 2), int(y * 2), int(x * 2) + w * 2, int(y * 2) + h * 2))

        # C: keep 4x, let Chrome downscale
        variants["C_crop4x_native"] = c4

        for name, im in variants.items():
            ap = WORK / f"a_{name}.png"
            im.save(ap)
            page = WORK / "p.html"
            page.write_text(PAGE.format(left=x, top=y, w=w, h=h, asset=ap))
            out = WORK / "shot.png"
            render(page, out)
            got = np.asarray(Image.open(out).convert("RGB")).astype(int)
            dx = int(x * 2)
            dy = int(y * 2)
            reg = got[dy:dy + h * 2, dx:dx + w * 2]
            if reg.shape != truth.shape:
                print(f"  x={x} y={y} {name}: shape {reg.shape} != {truth.shape}")
                continue
            d = np.abs(reg - truth).sum(axis=2)
            print(f"  x={x:6.2f} y={y:6.2f} {name:24s} mismatch {(d>24).mean()*100:6.2f}%  "
                  f"mean {d.mean()/3:6.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
