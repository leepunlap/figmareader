#!/usr/bin/env python3
"""Copy the source's sheet-edge rows into the gradient-band PNG.

The cream sheet starts at css 373.75, so the source's 4x rows 1494/1495 are a
blend of the band and the sheet.  The band's polynomial fit cannot reproduce
that edge, and Chrome snaps the sheet's background rect to whole device
pixels, so the blend has to live in the band asset itself: the checker
downsamples the 4x export 2:1, and the two rows average to exactly the
source's 2x row 747.

    python3 scripts/patch_band_edge.py 06 09
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = {"06": "source/lion/lion-06-org-detail-lionsclub.png",
       "09": "source/lion/lion-09-org-detail-lionshk.png"}

BAND_TOP = 221        # css, top of the band png
SRC_ROWS = (1494, 1495)   # 4x rows: the sheet's antialiased top edge


def patch(tag: str) -> None:
    src = np.asarray(Image.open(ROOT / SRC[tag]).convert("RGB"))
    path = ROOT / f"assets/lion/lion-{tag}-band.png"
    band = np.asarray(Image.open(path).convert("RGBA")).copy()

    for row in SRC_ROWS:
        idx = row - BAND_TOP * 4
        band[idx, :, :3] = src[row, :, :3]

    Image.fromarray(band, "RGBA").save(path)
    idx = ", ".join(str(r - BAND_TOP * 4) for r in SRC_ROWS)
    print(f"{tag}: patched {path.name} rows {idx} -> {band[SRC_ROWS[-1] - BAND_TOP * 4, 800, :3]}")


if __name__ == "__main__":
    for t in (sys.argv[1:] or ["06", "09"]):
        patch(t)
