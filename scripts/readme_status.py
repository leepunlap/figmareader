#!/usr/bin/env python3
"""
Write the "Current state" block of README.md from analysis/v1-diff.json.

The block lives between the two markers

    <!-- status:begin -->
    <!-- status:end -->

and is rewritten in place, so the numbers in the README always match the
last measurement.

  python3 scripts/readme_status.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
BEGIN = "<!-- status:begin -->"
END = "<!-- status:end -->"


def main() -> int:
    data = json.loads((ROOT / "analysis" / "v1-diff.json").read_text(encoding="utf-8"))
    vals = []
    for k, v in data.items():
        if isinstance(v, dict):
            v = v.get("diff", v.get("pct"))
        if isinstance(v, (int, float)):
            vals.append((k, float(v)))
    vals.sort(key=lambda kv: -kv[1])
    mean = sum(v for _, v in vals) / len(vals) if vals else 0
    over = [k for k, v in vals if v > 6]
    v1 = [v for k, v in vals if k.startswith("v1-")]
    v73 = [v for k, v in vals if k.startswith("v73-")]

    lines = [BEGIN, ""]
    lines.append("| | screens | mean diff | over the 6 % budget |")
    lines.append("|---|---|---|---|")
    lines.append(f"| v1.0 page | {len(v1)} | {sum(v1)/len(v1):.2f} % | "
                 f"{sum(1 for v in v1 if v > 6)} |")
    lines.append(f"| v1.0 最初版 (7.3) page | {len(v73)} | {sum(v73)/len(v73):.2f} % | "
                 f"{sum(1 for v in v73 if v > 6)} |")
    lines.append(f"| **all** | **{len(vals)}** | **{mean:.2f} %** | **{len(over)}** |")
    lines.append("")
    lines.append(f"Best {min(v for _, v in vals):.2f} %, worst {max(v for _, v in vals):.2f} %.")
    lines.append("")
    if over:
        lines.append("Screens still above the 6 % budget:")
        lines.append("")
        for k, v in vals:
            if v > 6:
                lines.append(f"* `{k}` — {v:.2f} %")
        lines.append("")
        lines.append(
            "These are the text-heavy screens. The residual is glyph "
            "anti-aliasing: the export is a 4× raster that Figma drew with its "
            "own renderer, Chrome rasterises natively at 2×, and even with "
            "identical glyph geometry ~29 % of the pixels of a text row differ "
            "by more than the 24/765 comparison threshold. The typeface, "
            "weight, size, sub-pixel position and the resampling pipeline were "
            "all swept and are already at their best (see *What the v1.0 pages "
            "taught us* above)."
        )
    else:
        lines.append("Every screen is inside the 6 % budget.")
    lines.append("")
    lines.append(END)

    text = README.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        print("[skip] markers not found in README.md")
        return 1
    head = text.split(BEGIN)[0]
    tail = text.split(END)[1]
    README.write_text(head + "\n".join(lines) + tail, encoding="utf-8")
    print(f"[write] README.md — {len(vals)} screens, mean {mean:.2f} %, {len(over)} over 6 %")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
