#!/usr/bin/env python3
"""Apply the measured corrections to the four competition-detail screens.

Every value below was measured from the exports themselves: the 4x source and
the 2x render were row-profiled, so the ink boxes of the 活动内容 paragraph
line up line for line.  The four exports share a pixel-identical paragraph
block, so one measurement drives all four screens.

  * every line's `top` is moved by the measured ink offset (dy)
  * the first line of closed / competition2-02 is also moved 4.25px right (dx)
    and gains the trailing 的 it was missing
  * the 拉坯班 line loses the OCR misread 通 -> 適
  * the 拉坯班 / 修坯課 lines gain the spaces the export has, with the
    word-spacing that reproduces their exact advance
  * the 手揑 character the export shows is restored (OCR read it as 手捏)
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

L6_OLD_OK = "拉坯班（1.5小時）：適合9歲或以上兒童，學習"
L6_OLD_BAD = "拉坯班（1.5小時）：通合9歲或以上兒童，學習"
L6_NEW = "拉坯班 （1.5小時）： 適合 9 歲或以上兒童，學習"
L8_OLD = "修坯課（1.5小時）：適合9歲或以上兒童，學習在"
L8_NEW = "修坯課（1.5小時）： 適合 9 歲或以上兒童，學習在"

# per file: list of (old_fragment, new_fragment)
EDITS = {
    "v1-competition-detail-open": [
        # 手揑 in the export, 手捏 in the page
        ("使用泥版、手捏、黏貼的", "使用泥版、手揑、黏貼的"),
        # top corrections (measured dy)
        ('left:40.06px;top:577.74px', 'left:40.06px;top:579.49px'),   # 卡通造型
        ('left:40.05px;top:614.71px', 'left:40.05px;top:615.46px'),   # 品上繪圖
        ('left:39.88px;top:648.76px', 'left:39.88px;top:651.01px'),   # 手腳並用
        ('left:39.73px;top:667.97px', 'left:39.73px;top:668.97px'),   # 修坯課
        # spacing
        (L6_OLD_OK, L6_NEW),
        (L8_OLD, L8_NEW),
        ('font-size:14px;color:#000000">拉坯班 （1.5小時）： 適合 9 歲',
         'font-size:14px;word-spacing:1.75px;color:#000000">拉坯班 （1.5小時）： 適合 9 歲'),
        ('font-size:14px;color:#000000">修坯課（1.5小時）： 適合 9 歲',
         'font-size:14px;word-spacing:0.5px;color:#000000">修坯課（1.5小時）： 適合 9 歲'),
    ],
    "v73-competition2-03": [
        ("使用泥版、手捏、黏貼的", "使用泥版、手揑、黏貼的"),
        ('left:40.05px;top:577.79px', 'left:40.05px;top:579.04px'),   # 卡通造型
        ('left:39.74px;top:614.8px', 'left:39.74px;top:615.05px'),    # 品上繪圖
        ('left:39.8px;top:648.8px', 'left:39.8px;top:651.05px'),      # 手腳並用
        ('left:39.73px;top:667.98px', 'left:39.73px;top:668.98px'),   # 修坯課
        (L6_OLD_OK, L6_NEW),
        (L8_OLD, L8_NEW),
        ('font-size:14px;color:#000000">拉坯班 （1.5小時）： 適合 9 歲',
         'font-size:14px;word-spacing:1.75px;color:#000000">拉坯班 （1.5小時）： 適合 9 歲'),
        ('font-size:14px;color:#000000">修坯課（1.5小時）： 適合 9 歲',
         'font-size:14px;word-spacing:0.5px;color:#000000">修坯課（1.5小時）： 適合 9 歲'),
    ],
    "v1-competition-detail-closed": [
        ('left:40.01px;top:523.81px', 'left:40.01px;top:520.81px'),   # 活動內容
        ('left:35.87px;top:539.95px', 'left:40.07px;top:542.95px'),   # 手捏創作班
        ("使用泥版、手揑、黏貼</p>", "使用泥版、手揑、黏貼的</p>"),
        ('left:40.05px;top:577.81px', 'left:40.05px;top:579.06px'),   # 卡通造型
        ('left:39.08px;top:592.95px', 'left:40.07px;top:596.95px'),   # 釉下彩繪班
        ('left:39.87px;top:647.81px', 'left:39.87px;top:651.06px'),   # 手腳並用
        ('left:39.76px;top:667.95px', 'left:39.76px;top:668.95px'),   # 修坯課
        (L6_OLD_BAD, L6_NEW),
        (L8_OLD, L8_NEW),
        ('font-size:14.0px;color:#000000">拉坯班 （1.5小時）： 適合 9 歲',
         'font-size:14.0px;word-spacing:1.75px;color:#000000">拉坯班 （1.5小時）： 適合 9 歲'),
        ('font-size:14.0px;color:#000000">修坯課（1.5小時）： 適合 9 歲',
         'font-size:14.0px;word-spacing:0.5px;color:#000000">修坯課（1.5小時）： 適合 9 歲'),
    ],
    "v73-competition2-02": [
        ('left:40.01px;top:521.81px', 'left:40.01px;top:520.81px'),   # 活動內容
        ('left:35.87px;top:537.95px', 'left:40.07px;top:542.95px'),   # 手捏創作班
        ("使用泥版、手揑、黏貼</p>", "使用泥版、手揑、黏貼的</p>"),
        ('left:40.08px;top:558.81px', 'left:40.08px;top:561.06px'),   # 技巧造出
        ('left:40.05px;top:575.81px', 'left:40.05px;top:579.06px'),   # 卡通造型
        ('left:39.08px;top:590.95px', 'left:40.07px;top:596.95px'),   # 釉下彩繪班
        ('left:40.02px;top:612.88px', 'left:40.02px;top:615.13px'),   # 品上繪圖
        ('left:40.01px;top:630.95px', 'left:40.01px;top:632.95px'),   # 拉坯班
        ('left:39.87px;top:645.81px', 'left:39.87px;top:651.06px'),   # 手腳並用
        ('left:39.76px;top:665.95px', 'left:39.76px;top:668.95px'),   # 修坯課
        ('left:40.01px;top:684.95px', 'left:40.01px;top:687.20px'),   # 拉坯機上
        (L6_OLD_BAD, L6_NEW),
        (L8_OLD, L8_NEW),
        ('font-size:14.0px;color:#000000">拉坯班 （1.5小時）： 適合 9 歲',
         'font-size:14.0px;word-spacing:1.75px;color:#000000">拉坯班 （1.5小時）： 適合 9 歲'),
        ('font-size:14.0px;color:#000000">修坯課（1.5小時）： 適合 9 歲',
         'font-size:14.0px;word-spacing:0.5px;color:#000000">修坯課（1.5小時）： 適合 9 歲'),
    ],
}


def main():
    for name, edits in EDITS.items():
        page = ROOT / f"{name}.html"
        text = page.read_text(encoding="utf-8")
        for old, new in edits:
            n = text.count(old)
            if n != 1:
                raise SystemExit(f"[error] {name}: {old!r} matched {n} times")
            text = text.replace(old, new)
        page.write_text(text, encoding="utf-8")
        print(f"{name}: applied {len(edits)} edits")


if __name__ == "__main__":
    main()
