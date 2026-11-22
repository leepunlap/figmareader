#!/usr/bin/env python3
"""
Produce a pixel-precise layout spec for a v1 screen using the Matrix vision
connector, so a worker can build a screen without loading a 4x PNG into its
own context (the child's image-viewing budget is rationed).

  python3 scripts/vision_spec.py v1-order-normal
  python3 scripts/vision_spec.py order-normal --folder v1raw

Writes analysis/vision/<slug>.md (the spec) and prints a short summary.
The 1x preview it feeds the model is left in /tmp/<slug>-1x.png so a worker
can also crop regions of it for detail.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
Image = None

PROMPT = """This is a 1x mobile app screen ({w} x {h} CSS px) exported from a Figma design.
Describe it as a precise implementation spec for an HTML/CSS rebuild. Be literal and exhaustive:
- Top to bottom: every visible block, its exact vertical position in CSS px (measured from the top),
  its height, its width, and its background colour.
- For each text line: the EXACT text (including Chinese characters, spaces and punctuation),
  its left position in CSS px, its font size in px, its weight and its colour.
- Every card/panel: left, top, width, height, border radius, border colour, padding.
- Every photo, illustration, icon or QR graphic: its exact bounding box in CSS px.
- Any gradient: the two or more colour stops and their angle.
- Any shadow: the approximate blur and offset.
Report positions as numbers. Do not say "approximately" for the main blocks."""


def downscale(src: Path, out: Path) -> tuple[int, int]:
    global Image
    from PIL import Image as PILImage
    Image = PILImage
    im = PILImage.open(src).convert("RGB")
    w, h = im.size
    nw, nh = w // 4, h // 4
    im.resize((nw, nh), PILImage.LANCZOS).save(out)
    return nw, nh


def upload(path: Path) -> str:
    r = subprocess.run(["mcode-tools", "upload_temp_url", str(path)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"upload failed: {r.stderr[-500:]}")
    return json.loads(r.stdout)["temp_url"]


def describe(url: str, prompt: str) -> str:
    args = {"image_info": [{"url": url, "prompt": prompt}]}
    args_path = Path("/tmp/vision-args.json")
    args_path.write_text(json.dumps(args, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(
        ["mcode-tools", "connector", "call",
         "connector__matrix__describe_images", "--args-file", str(args_path)],
        capture_output=True, text=True, timeout=600,
    )
    if r.returncode != 0:
        raise SystemExit(f"describe failed: {r.stderr[-800:]}")
    data = json.loads(r.stdout)
    res = data.get("results") or []
    if not res or not res[0].get("success"):
        raise SystemExit(f"describe returned no result: {r.stdout[:500]}")
    return res[0].get("description", "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--folder", default=None,
                    help="source folder: v1raw (big page) or v1raw73 (7.3 page)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    slug = args.slug
    prefix, name = (slug.split("-", 1) if slug.startswith(("v1-", "v73-")) else ("v1", slug))
    if prefix == "v73" and name.startswith("v73-"):
        name = name[4:]
    folder = args.folder or ("v1raw73" if prefix == "v73" else "v1raw")
    src = ROOT / "source" / folder / "screens" / f"{name}.png"
    if not src.exists():
        raise SystemExit(f"missing source {src}")

    preview = Path(f"/tmp/{name}-1x.png")
    w, h = downscale(src, preview)
    url = upload(preview)
    spec = describe(url, PROMPT.format(w=w, h=h))

    out = Path(args.out) if args.out else ROOT / "analysis/vision" / f"{slug}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        f"# {slug} — {w} x {h} css px\n"
        f"source: source/{folder}/screens/{name}.png (4x export)\n"
        f"1x preview: {preview}\n\n{spec}\n",
        encoding="utf-8",
    )
    print(f"[vision] {slug}  {w}x{h}  -> {out.relative_to(ROOT)}  ({len(spec)} chars)")
    print(f"[vision] preview at {preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
