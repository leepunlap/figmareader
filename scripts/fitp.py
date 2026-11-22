#!/usr/bin/env python3
"""Emit <p> elements for the fitted OCR runs of a screen.

usage: fitp.py <slug> [--out FILE] [--include y0,y1 ...] [--exclude-text a,b]

Runs whose text falls outside the included y ranges are skipped, so that text
baked into a cropped image is not also rendered as live text.
"""
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--out")
    ap.add_argument("--include", action="append", default=[],
                    help="css y range to include, repeatable")
    ap.add_argument("--exclude-text", default="",
                    help="comma separated substrings; matching runs are skipped")
    args = ap.parse_args()

    path = os.path.join(ROOT, "analysis/ocr", f"{args.slug}-fit.json")
    runs = json.load(open(path))

    ranges = []
    for spec in args.include:
        a, b = spec.split(",")
        ranges.append((float(a), float(b)))
    excl = [s for s in args.exclude_text.split(",") if s]

    out = []
    for r in runs:
        fit = r.get("fit")
        if not fit:
            continue
        y = r["y0"]
        if ranges and not any(a <= y <= b for a, b in ranges):
            continue
        if any(e in r["text"] for e in excl):
            continue
        style = (f"left:{fit['left']}px;top:{fit['top']}px;"
                 f"font-size:{fit['fs']}px;color:{fit['color']}")
        if fit.get("weight", 400) != 400:
            style += f";font-weight:{fit['weight']}"
        out.append(f'  <p class="cdc__t" style="{style}">{r["text"]}</p>')

    body = "\n".join(out)
    if args.out:
        open(args.out, "w").write(body + "\n")
        print(args.out, len(out), "runs")
    else:
        print(body)


if __name__ == "__main__":
    main()
