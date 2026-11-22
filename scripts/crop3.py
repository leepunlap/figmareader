#!/usr/bin/env python3
"""Stack source | render | diff for a CSS rect and optionally upload for VQA."""
import argparse, sys, json, subprocess
from pathlib import Path
from PIL import Image
ROOT = Path("/Users/blee/src/figma")
sys.path.insert(0, str(ROOT / "scripts"))
from render_check import SCREENS

ap = argparse.ArgumentParser()
ap.add_argument("screen")
ap.add_argument("--rect", required=True, help="x0,y0,x1,y1 in css px")
ap.add_argument("--scale", type=float, default=2.0)
ap.add_argument("--out", default=None)
a = ap.parse_args()
x0, y0, x1, y1 = [float(v) for v in a.rect.split(",")]
spec = SCREENS[a.screen]
ren = Image.open(Path("/tmp/figma-render") / (Path(spec["page"]).stem + ".png")).convert("RGB")
src = Image.open(ROOT / spec["source"]).convert("RGB")
if src.size != ren.size:
    src = src.resize(ren.size, Image.LANCZOS)
box = (int(x0*2), int(y0*2), int(x1*2), int(y1*2))
s = src.crop(box); r = ren.crop(box)
gap = 12
out = Image.new("RGB", (s.width, s.height*3 + gap*2), (255, 0, 255))
out.paste(s, (0,0)); out.paste(r, (0, s.height+gap))
# diff visualization: src grey, differing magenta
import numpy as np
sa = np.asarray(s).astype(int); ra = np.asarray(r).astype(int)
d = (np.abs(sa-ra).sum(2) > 24)
gray = np.asarray(s.convert("L")).astype(int)
vis = np.stack([gray, gray, gray], 2).astype(np.uint8)
vis[d] = [255,0,255]
out.paste(Image.fromarray(vis), (0, (s.height+gap)*2))
if a.scale != 1.0:
    out = out.resize((int(out.width*a.scale), int(out.height*a.scale)), Image.LANCZOS)
p = a.out or f"/tmp/crop-{a.screen}.png"
out.save(p)
print(p, out.size)
