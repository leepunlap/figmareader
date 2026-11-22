#!/usr/bin/env python3
"""
Map the task cards in a list screen (top / bottom / left / right / border
colour) for both the Figma export and the rendered page, so geometry and state
can be compared numerically.

  python3 scripts/card_map.py            # all list screens
  python3 scripts/card_map.py list-027
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RENDER = Path("/tmp/figma-render")

BORDERS = {
    "peach": (255, 221, 213),
    "gray": (235, 235, 240),
}


def load(path: Path) -> tuple[np.ndarray, int]:
    img = Image.open(path).convert("RGB")
    return np.asarray(img).astype(np.int16), img.width // 390


def find_cards(arr: np.ndarray, scale: int, y_from: float) -> list[dict]:
    """a card is a run of border rows: top edge + bottom edge + left/right x"""
    out = []
    for name, target in BORDERS.items():
        t = np.array(target)
        rows = []
        for y in range(int(y_from * scale), arr.shape[0]):
            m = np.all(np.abs(arr[y] - t) <= 4, axis=1)
            if m.sum() > 200:
                idx = np.where(m)[0]
                rows.append((y / scale, int(idx[0] / scale), int(idx[-1] / scale), int(m.sum())))
        if not rows:
            continue
        # group contiguous rows
        groups: list[list] = []
        for r in rows:
            if groups and r[0] - groups[-1][-1][0] <= 0.8:
                groups[-1].append(r)
            else:
                groups.append([r])
        for g in groups:
            out.append(
                {
                    "colour": name,
                    "top": g[0][0],
                    "bottom": g[-1][0],
                    "left": g[0][1],
                    "right": g[0][2],
                    "run": g[0][3],
                }
            )
    return out


def main() -> int:
    screens = sys.argv[1:] or ["list-020", "list-023", "list-027"]
    for screen in screens:
        src, ss = load(ROOT / "source" / f"{screen}.png")
        ren, rs = load(RENDER / f"{screen}.png")
        print(f"\n================ {screen} ================")
        for label, arr, scale in (("SOURCE", src, ss), ("RENDER", ren, rs)):
            cards = find_cards(arr, scale, 430)
            print(f"  {label}")
            for c in cards:
                print(
                    f"    {c['colour']:5s} top={c['top']:7.2f} bottom={c['bottom']:7.2f} "
                    f"h={c['bottom'] - c['top'] + 1:6.2f}  left={c['left']:6.2f} right={c['right']:6.2f} "
                    f"w={c['right'] - c['left'] + 1:6.2f}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
