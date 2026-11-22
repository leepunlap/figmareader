#!/usr/bin/env python3
"""
Assemble a v1/v73 page from a JSON page spec.

The spec holds the structural markup (images, cards, buttons) plus the list of
OCR runs that must be skipped (text that already lives inside an image) and
the text that has to be written by hand.  Every remaining OCR run is emitted
as an absolutely positioned element using the geometry that scripts/ocrfit.py
measured, so the text lands exactly where the Figma export has it.

    python3 scripts/genpage.py specs/competition-detail-open.json

The spec is a normal file, so a page can be re-generated after a tweak.
"""

from __future__ import annotations

import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def dedupe(runs: list[dict]) -> set[int]:
    """Indices of OCR runs that duplicate another run.

    The OCR reports the same line in three different ways: once correctly,
    once with a stray space and once as a garbled mix of the line and its
    neighbour.  Two rules catch them:

    * the texts are nearly the same and the boxes overlap -> the same line,
      the run with the higher confidence (or the longer text) wins;
    * one box sits completely inside another one -> the inner run is a
      garbled reading of the outer line.
    """
    drop = set()
    boxes = [(r["src_x0"], r["src_y0"], r["src_x1"], r["src_y1"]) for r in runs]
    areas = [max(1.0, (b[2] - b[0]) * (b[3] - b[1])) for b in boxes]
    keys = [re.sub(r"\s+", "", r["text"]) for r in runs]
    for i in range(len(runs)):
        if i in drop:
            continue
        for j in range(i + 1, len(runs)):
            if j in drop:
                continue
            ax0, ay0, ax1, ay1 = boxes[i]
            bx0, by0, bx1, by1 = boxes[j]
            ox = min(ax1, bx1) - max(ax0, bx0)
            oy = min(ay1, by1) - max(ay0, by0)
            if ox <= 0 or oy <= 0:
                continue
            inter = ox * oy
            overlap = inter / min(areas[i], areas[j])
            ratio = SequenceMatcher(None, keys[i], keys[j]).ratio()
            if ratio >= 0.85 and overlap >= 0.5:
                # the same line, read twice
                if (runs[j].get("conf", 0), len(keys[j])) > (runs[i].get("conf", 0), len(keys[i])):
                    drop.add(i)
                    break
                drop.add(j)
            elif overlap >= 0.6 and (keys[j].startswith(keys[i]) or keys[i].startswith(keys[j])):
                # one reading is a fragment of the other - keep the long one
                if len(keys[i]) < len(keys[j]):
                    drop.add(i)
                    break
                drop.add(j)
            elif inter / areas[j] >= 0.85 and runs[j].get("conf", 0) <= runs[i].get("conf", 0):
                # a garbled reading inside a correctly read line
                drop.add(j)
            elif inter / areas[i] >= 0.85 and runs[i].get("conf", 0) < runs[j].get("conf", 0):
                drop.add(i)
                break
    return drop


def build(spec: dict) -> str:
    slug = spec["slug"]
    cls = spec["class"]
    art = spec.get("art", cls)
    width = spec["width"]
    height = spec["height"]
    title = spec.get("title", slug)
    fit = json.loads((ROOT / "analysis/ocr" / f"{slug}-fit.json").read_text(encoding="utf-8"))
    skip = set(spec.get("skip", []))
    skip |= dedupe(fit)

    runs = []
    skip_text = spec.get("skip_text", [])
    skip_y = spec.get("skip_y", [])
    for i, r in enumerate(fit):
        if i in skip:
            continue
        if any(t in r["text"] for t in skip_text):
            continue
        if any(y0 <= r["src_y0"] <= y1 for y0, y1 in skip_y):
            continue
        f = r.get("fit")
        if not f:
            continue
        w = f.get("weight", 400)
        wtxt = f"font-weight:{w};" if w != 400 else ""
        runs.append(
            f'  <p class="{cls}__t" style="left:{f["left"]}px;top:{f["top"]}px;'
            f'font-size:{f["fs"]}px;{wtxt}color:{f["color"]}">{esc(r["text"])}</p>'
        )

    manual = []
    for m in spec.get("manual", []):
        extra = "".join(f'{k}:{v};' for k, v in m.get("style", {}).items())
        cls_m = m.get("class", f"{cls}__t")
        manual.append(
            f'  <p class="{cls_m}" style="left:{m["left"]}px;top:{m["top"]}px;'
            f'font-size:{m["fs"]}px;color:{m.get("color", "#000")};{extra}">{esc(m["text"])}</p>'
        )

    links = "\n".join(
        f'<link rel="stylesheet" href="{href}">' for href in spec.get("links", [])
    )
    body = spec["body"].rstrip()
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width={width}, initial-scale=1">
<title>{esc(title)}</title>
{links}
</head>
<body>
<div class="v1 {art}" style="width:{width}px;height:{height}px">
{body}

{chr(10).join(manual)}

{chr(10).join(runs)}
</div>
</body>
</html>
"""


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    for p in sys.argv[1:]:
        spec_path = Path(p)
        if not spec_path.is_absolute():
            spec_path = ROOT / "specs" / p
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        out = ROOT / spec["out"]
        out.write_text(build(spec), encoding="utf-8")
        print(f"{spec['out']}  <- {spec_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
