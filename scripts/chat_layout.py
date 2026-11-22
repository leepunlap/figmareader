#!/usr/bin/env python3
"""
Measure the Lion chat screens (08 / 11) element by element.

  python3 scripts/chat_layout.py source/lion/lion-08-chat-1.png
"""

from __future__ import annotations

import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def hexs(rgb) -> str:
    r, g, b = (int(v) for v in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def load(path):
    im = Image.open(path).convert("RGB")
    return np.asarray(im).astype(np.int32), 4


def band_rows(reg, ref, thr=40):
    ink = (np.abs(reg - np.array(ref)).sum(axis=2) > thr)
    rows = ink.sum(axis=1)
    on = rows > 0
    out = []
    i = 0
    while i < len(on):
        if on[i]:
            j = i
            while j + 1 < len(on) and on[j + 1]:
                j += 1
            out.append((i, j + 1))
            i = j + 1
        else:
            i += 1
    return out, ink


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "source/lion/lion-08-chat-1.png"
    a, s = load(path)
    WHITE = (255, 255, 255)

    def rows(x0, y0, x1, y1, thr=40, ref=WHITE):
        reg = a[y0 * s:y1 * s, x0 * s:x1 * s]
        bands, ink = band_rows(reg, ref, thr)
        return [(round(y0 + i / s, 2), round(y0 + j / s, 2)) for i, j in bands]

    def cols(y0, y1, x0, x1, thr=40, ref=WHITE):
        reg = a[y0 * s:y1 * s, x0 * s:x1 * s]
        _, ink = band_rows(reg, ref, thr)
        c = ink.sum(axis=0)
        on = c > 0
        out = []
        i = 0
        while i < len(on):
            if on[i]:
                j = i
                while j + 1 < len(on) and on[j + 1]:
                    j += 1
                out.append((round(x0 + i / s, 2), round(x0 + (j + 1) / s, 2)))
                i = j + 1
            else:
                i += 1
        return out

    def pt(x, y):
        return hexs(a[int(y * s), int(x * s)])

    print("### status bar")
    print("  time ink cols y20-40 x40-100:", cols(20, 40, 40, 100, 60, (255, 255, 255)))
    print("  time ink rows x60-90:", rows(60, 90, 10, 45, 60, (255, 255, 255)))
    print("  signal cols:", cols(18, 38, 270, 306, 60, (255, 255, 255)))
    print("  wifi   cols:", cols(18, 38, 306, 330, 60, (255, 255, 255)))
    print("  battery cols:", cols(18, 38, 330, 370, 60, (255, 255, 255)))

    print("### back chevron")
    print("  cols y70-100 x25-55:", cols(70, 100, 25, 55, 60, (255, 255, 255)))
    print("  rows x30-45:", rows(30, 45, 60, 105, 60, (255, 255, 255)))

    print("### header pill")
    print("  rows x70-215:", rows(70, 215, 50, 120, 12, (255, 255, 255)))
    print("  cols y60-112 x55-230:", cols(60, 112, 55, 230, 12, (255, 255, 255)))
    print("  pill fill pt(180,70):", pt(180, 70), " pt(120,105):", pt(120, 105))
    print("  behind pill pt(180,55):", pt(180, 55))

    print("### lion avatar (pill)")
    print("  rows x72-112:", rows(72, 112, 55, 120, 20, (255, 255, 255)))
    print("  cols y65-108 x60-120:", cols(65, 108, 60, 120, 20, (255, 255, 255)))

    print("### pill label")
    print("  cols y70-100 x118-215:", cols(70, 100, 118, 215, 60, (255, 255, 255)))
    print("  rows x120-190:", rows(120, 190, 65, 105, 60, (255, 255, 255)))

    print("### mommy")
    print("  avatar rows x260-295:", rows(260, 295, 60, 105, 20, (255, 255, 255)))
    print("  avatar cols y70-100 x255-300:", cols(70, 100, 255, 300, 20, (255, 255, 255)))
    print("  text cols y70-100 x290-345:", cols(70, 100, 290, 345, 60, (255, 255, 255)))
    print("  caret cols y70-100 x345-375:", cols(70, 100, 345, 375, 60, (255, 255, 255)))
    print("  text rows x295-340:", rows(295, 340, 70, 100, 60, (255, 255, 255)))

    print("### sheet")
    print("  sheet top row at x=195:", "white?", pt(195, 137), pt(195, 138), pt(195, 139))

    print("### greeting")
    print("  Hello cols y164-187 x20-240:", cols(164, 187, 20, 240, 60))
    print("  Hello rows x30-60:", rows(30, 60, 160, 195, 60))
    print("  Hoiyi cols y164-187 x120-240:", cols(164, 187, 120, 240, 60))
    print("  Lucy cols y193-212 x20-240:", cols(193, 212, 20, 240, 60))
    print("  line2 cols y210-228 x20-240:", cols(210, 228, 20, 240, 60))
    print("  Lucy rows x30-70:", rows(30, 70, 190, 215, 60))
    print("  line2 rows x30-60:", rows(30, 60, 208, 232, 60))

    print("### suggestions")
    print("  heading cols y250-275 x30-240:", cols(250, 275, 30, 240, 60))
    print("  heading rows x45-200:", rows(45, 200, 248, 278, 60))
    print("  chip1 cols y280-308 x30-240:", cols(280, 308, 30, 240, 12))
    print("  chip2 cols y312-340 x30-240:", cols(312, 340, 30, 240, 12))
    print("  chip3 cols y344-372 x30-240:", cols(344, 372, 30, 240, 12))
    print("  chip1 text cols y282-304:", cols(282, 304, 45, 240, 60))
    print("  more cols y374-396 x30-240:", cols(374, 396, 30, 240, 60))
    print("  more rows x40-100:", rows(40, 100, 372, 398, 60))
    print("  right card1 rows x270-390:", rows(270, 390, 240, 320, 10))
    print("  right card2 rows x270-390:", rows(270, 390, 310, 405, 10))
    print("  right card1 cols y250-310:", cols(250, 310, 260, 390, 10))
    print("  icon circle1 rows x300-350:", rows(300, 350, 245, 315, 20))
    print("  label1 cols y312-332 x290-370:", cols(312, 332, 290, 370, 60))
    print("  icon circle2 rows x300-350:", rows(300, 350, 320, 390, 20))
    print("  label2 cols y374-396 x290-370:", cols(374, 396, 290, 370, 60))

    print("### user bubble")
    print("  bubble rows x200-350:", rows(200, 350, 425, 490, 20))
    print("  bubble cols y440-470 x150-390:", cols(440, 470, 150, 390, 20))
    print("  bubble text cols y442-470 x180-370:", cols(442, 470, 180, 370, 60))
    print("  bubble text rows x200-250:", rows(200, 250, 438, 475, 60))
    print("  grad pt(190,440):", pt(190, 440), " pt(300,440):", pt(300, 440),
          " pt(360,440):", pt(360, 440))

    print("### agent label + avatar")
    print("  label cols y478-495 x40-200:", cols(478, 495, 40, 200, 40))
    print("  avatar rows x18-50:", rows(18, 50, 470, 540, 20))
    print("  avatar cols y490-530 x10-60:", cols(490, 530, 10, 60, 20))

    print("### reply bubble")
    print("  bubble rows x60-330:", rows(60, 330, 480, 780, 8))
    print("  bubble cols y500-720 x40-360:", cols(500, 720, 40, 360, 8))
    print("  text1 rows x60-330:", rows(60, 330, 620, 660, 60))
    print("  text2 rows x60-330:", rows(60, 330, 660, 700, 60))
    print("  text3 rows x60-330:", rows(60, 330, 700, 740, 60))
    print("  text4 rows x60-330:", rows(60, 330, 740, 780, 60))

    print("### reactions")
    print("  thumb rows x40-110:", rows(40, 110, 730, 775, 40))
    print("  thumbs cols y735-765 x30-110:", cols(735, 765, 30, 110, 40))

    print("### input bar")
    print("  bar rows x60-340:", rows(60, 340, 815, 905, 8))
    print("  bar cols y830-895 x0-390:", cols(830, 895, 0, 390, 8))
    print("  placeholder cols y845-875 x20-200:", cols(845, 875, 20, 200, 40))
    print("  placeholder rows x30-120:", rows(30, 120, 840, 880, 40))
    print("  send btn rows x320-370:", rows(320, 370, 815, 905, 12))
    print("  send btn cols y830-895 x300-390:", cols(830, 895, 300, 390, 12))
    print("  send grad pt(330,845):", pt(330, 845), " pt(365,845):", pt(365, 845))

    print("### home indicator")
    print("  rows x100-290:", rows(100, 290, 905, 928, 20))
    print("  cols y912-924:", cols(912, 924, 100, 290, 20))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
