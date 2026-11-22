#!/usr/bin/env python3
"""
Extract every text run from a v1/v73 screen with the macOS Vision OCR.

The AI vision specs are good at layout but they hallucinate Chinese copy.
OCR gives the real characters plus their exact pixel boxes, which is what the
pixel-diff metric actually cares about.

    python3 scripts/ocr_screen.py v1-competition-detail-open
    python3 scripts/ocr_screen.py --all            # every screen in both pages
    python3 scripts/ocr_screen.py v73-mine-01 --scale 2

Output: analysis/ocr/<slug>.md   (markdown, 1x css coordinates)
        analysis/ocr/<slug>.tsv   (raw boxes)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent.parent
OCR = ROOT / "scripts" / "ocr.swift"


def load_manifests() -> dict:
    out = {}
    for page, mfile, prefix in (
        ("v1", ROOT / "source/v1raw/screens/manifest.json", "v1-"),
        ("v73", ROOT / "source/v1raw73/screens/manifest.json", ""),
    ):
        for row in json.loads(mfile.read_text()):
            slug = prefix + row["slug"]
            out[slug] = {"page": page, "row": row}
    return out


def find_source(slug: str, page: str) -> Path:
    if page == "v1":
        # v1 exports are stored under the bare slug
        return ROOT / "source/v1raw/screens" / f"{slug[3:]}.png"
    # v73 exports already carry the v73- prefix in their file name
    return ROOT / "source/v1raw73/screens" / f"{slug}.png"


def _ocr_file(tmp: Path, min_conf: float) -> list[tuple]:
    proc = subprocess.run(
        ["swift", str(OCR), str(tmp), "--min", str(min_conf)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ocr failed")
    rows = []
    for line in proc.stdout.splitlines():
        parts = line.split(" ", 5)
        if len(parts) < 6:
            continue
        x0, y0, x1, y1 = (int(float(v)) for v in parts[:4])
        rows.append((x0, y0, x1, y1, float(parts[4]), parts[5]))
    return rows


def run_ocr(png: Path, scale: int, min_conf: float = 0.30, tile: int = 0) -> list[tuple]:
    """Downsample the 4x export to `scale`x css size, then OCR it.

    With `tile` > 0 the image is also cut into horizontal strips of that many
    css pixels (with an overlap).  Vision recognises far more lines when the
    page is not one very tall image, and the overlap makes sure no line is
    lost at a tile border.
    """
    im = Image.open(png).convert("RGB")
    w, h = im.size
    # the export is 4x, so 1x css size is w//4 and 2x css size is w//2
    div = 4 // scale
    small = im.resize((w // div, h // div), Image.LANCZOS)
    tmp = Path(f"/tmp/ocr-in-{os.getpid()}.png")

    rows: list[tuple] = []
    if tile <= 0:
        small.save(tmp)
        for x0, y0, x1, y1, conf, text in _ocr_file(tmp, min_conf):
            rows.append((x0 // scale, y0 // scale, x1 // scale, y1 // scale, conf, text))
    else:
        W, H = small.size
        step = tile * scale
        overlap = 60 * scale
        y = 0
        while y < H:
            y0 = max(0, y - (overlap if y else 0))
            y1 = min(H, y + step + overlap)
            crop = small.crop((0, y0, W, y1))
            crop.save(tmp)
            for x0, y1_, x2, y2, conf, text in _ocr_file(tmp, min_conf):
                rows.append((x0 // scale, (y0 + y1_) // scale,
                             x2 // scale, (y0 + y2) // scale, conf, text))
            y += step

    # de-duplicate: the tile overlap reports a line twice
    rows.sort(key=lambda r: (r[1], r[0]))
    out = []
    for r in rows:
        dup = False
        for o in out:
            if o[5] != r[5]:
                continue
            if (abs(o[0] - r[0]) <= 3 and abs(o[1] - r[1]) <= 3
                    and abs(o[2] - r[2]) <= 3 and abs(o[3] - r[3]) <= 3):
                dup = True
                break
        if not dup:
            out.append(r)
    return out


def write_outputs(slug: str, rows: list[tuple], meta: dict) -> None:
    od = ROOT / "analysis" / "ocr"
    od.mkdir(parents=True, exist_ok=True)
    row = meta["row"]
    w, h = row["css"]
    lines = [
        f"# OCR — {slug} ({w} x {h} css px)",
        f"source: {meta['page']} export, boxes in 1x css pixels",
        "",
        "| x0 | y0 | x1 | y1 | conf | text |",
        "|---|---|---|---|---|---|",
    ]
    for x0, y0, x1, y1, conf, text in rows:
        t = text.replace("|", "\\|")
        lines.append(f"| {x0} | {y0} | {x1} | {y1} | {conf:.2f} | {t} |")
    (od / f"{slug}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    with open(od / f"{slug}.tsv", "w", encoding="utf-8") as fh:
        for x0, y0, x1, y1, conf, text in rows:
            fh.write(f"{x0}\t{y0}\t{x1}\t{y1}\t{conf:.2f}\t{text}\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--scale", type=int, default=1, choices=(1, 2))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--min", type=float, default=0.30)
    ap.add_argument("--tile", type=int, default=0)
    args = ap.parse_args()

    manifests = load_manifests()
    if args.all:
        todo = sorted(manifests)
    else:
        todo = []
        for s in args.slugs:
            if s in manifests:
                todo.append(s)
                continue
            base = s[3:] if s.startswith("v1-") else s
            cand = [k for k in manifests if k == "v1-" + base]
            if not cand:
                print(f"?? unknown slug {s}")
                continue
            todo.extend(cand)
        todo = list(dict.fromkeys(todo))

    for slug in todo:
        out = ROOT / "analysis" / "ocr" / f"{slug}.md"
        if out.exists() and not args.force:
            continue
        meta = manifests[slug]
        src = find_source(slug, meta["page"])
        if not src.exists():
            print(f"?? missing source for {slug}")
            continue
        try:
            rows = run_ocr(src, args.scale, args.min, args.tile)
        except Exception as exc:  # noqa: BLE001
            print(f"!! {slug}: {exc}")
            continue
        write_outputs(slug, rows, meta)
        print(f"-> {slug}: {len(rows)} runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
