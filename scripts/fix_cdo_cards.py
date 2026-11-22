#!/usr/bin/env python3
"""
Repair the two competition-detail pages that never rendered their cards.

v1-competition-detail-open and v73-competition2-03 are the same design.  Both
were missing cards 3, 4, 5 and 7, and both drew the card box 3 px too narrow
(the export puts the 1 px hairline at x=20 and the white face from 21 to
380.75, so the card is 361.75 wide starting at 20).

  python3 scripts/fix_cdo_cards.py v1-competition-detail-open v73-competition2-03
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# card box: left 20, width 361.75
CSS_CARD = (
    (".v1--cdo .cdo__card {\n  left: 23px;\n  width: 355px;",
     ".v1--cdo .cdo__card {\n  left: 20px;\n  width: 361.75px;"),
    # every child of a card is positioned against the card, so the card moving
    # 3 px left has to be compensated or the children drift with it
    (".v1--cdo .cdo__poster {\n  left: 17px;",
     ".v1--cdo .cdo__poster {\n  left: 20px;"),
    (".v1--cdo .cdo__pill--1 { left: 17px;",  ".v1--cdo .cdo__pill--1 { left: 20px;"),
    (".v1--cdo .cdo__pill--2 { left: 73px;",  ".v1--cdo .cdo__pill--2 { left: 76px;"),
    (".v1--cdo .cdo__pill--3 { left: 149px;", ".v1--cdo .cdo__pill--3 { left: 152px;"),
    (".v1--cdo .cdo__pill--4 { left: 197px;", ".v1--cdo .cdo__pill--4 { left: 200px;"),
    (".v1--cdo .cdo__pill--5 { left: 245px;", ".v1--cdo .cdo__pill--5 { left: 248px;"),
    (".v1--cdo .cdo__badge {\n  left: 17px;\n  top: 56px;\n  width: 72px;\n  height: 23px;\n  border-radius: 11.5px;",
     ".v1--cdo .cdo__badge {\n  left: 20px;\n  top: 54px;\n  width: 72px;\n  height: 25.75px;\n  border-radius: 12.875px;"),
    (".v1--cdo .cdo__org--1 { left: 17px;", ".v1--cdo .cdo__org--1 { left: 20px;"),
    (".v1--cdo .cdo__org--2 { left: 17px;", ".v1--cdo .cdo__org--2 { left: 20px;"),
    (".v1--cdo .cdo__soc--fb1 { left: 93px;",  ".v1--cdo .cdo__soc--fb1 { left: 96px;"),
    (".v1--cdo .cdo__soc--ig1 { left: 125px;", ".v1--cdo .cdo__soc--ig1 { left: 128px;"),
    (".v1--cdo .cdo__soc--gl1 { left: 157.75px;", ".v1--cdo .cdo__soc--gl1 { left: 160.75px;"),
    (".v1--cdo .cdo__soc--fb2 { left: 93px;",  ".v1--cdo .cdo__soc--fb2 { left: 96px;"),
    (".v1--cdo .cdo__soc--ig2 { left: 125px;", ".v1--cdo .cdo__soc--ig2 { left: 128px;"),
    (".v1--cdo .cdo__soc--gl2 { left: 157.75px;", ".v1--cdo .cdo__soc--gl2 { left: 160.75px;"),
    (".v1--cdo .cdo__guest--1 { left: 25px;",  ".v1--cdo .cdo__guest--1 { left: 28px;"),
    (".v1--cdo .cdo__guest--2 { left: 117px;", ".v1--cdo .cdo__guest--2 { left: 120px;"),
    (".v1--cdo .cdo__guest--3 { left: 209px;", ".v1--cdo .cdo__guest--3 { left: 212px;"),
    (".v1--cdo .cdo__guest--4 { left: 301px;", ".v1--cdo .cdo__guest--4 { left: 304px;"),
    (""".v1--cdo .cdo__chev {
  left: 326px;
  top: 26.5px;
  z-index: 3;
}""",
     """.v1--cdo .cdo__chev {
  left: 325px;
  top: 23.5px;
  width: 12px;
  height: 12px;
  z-index: 3;
}"""),
)

CSS_DIVIDER = ("""/* ------------------------------------------------------------------ cards */""",
                """/* the hairline under the tab strip, measured at y=450 in the export */
.v1--cdo .cdo__divider {
  left: 20px;
  top: 450px;
  width: 361.75px;
  height: 1px;
  background: #f1f2f4;
  z-index: 4;
}

/* ------------------------------------------------------------------ cards */""")

HTML_CARDS = ("""  <!-- card 6 : 主辦方 ------------------------------------------------------ -->""",
               """  <!-- card 3 : 收費 -------------------------------------------------------- -->
  <article class="cdo__card cdo__card--3"></article>

  <!-- card 4 : 日程表 ------------------------------------------------------ -->
  <article class="cdo__card cdo__card--4"></article>

  <!-- card 5 : 參加須知 ---------------------------------------------------- -->
  <article class="cdo__card cdo__card--5"></article>

  <!-- card 6 : 主辦方 ------------------------------------------------------ -->""")

HTML_CARD7 = ("""  <!-- bottom bar ----------------------------------------------------------- -->""",
               """  <!-- card 7 : 嘉賓 -------------------------------------------------------- -->
  <article class="cdo__card cdo__card--7">
    <svg class="cdo__chev" viewBox="0 0 12 12" fill="none" stroke="#6f87a4" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M4 2.5 8.5 6 4 9.5"/></svg>
  </article>

  <!-- bottom bar ----------------------------------------------------------- -->""")


def patch(slug: str) -> None:
    css_path = ROOT / "assets" / "v1" / f"{slug}.css"
    html_path = ROOT / f"{slug}.html"
    css = css_path.read_text(encoding="utf-8")
    html = html_path.read_text(encoding="utf-8")

    for old, new in CSS_CARD:
        if old in css:
            css = css.replace(old, new, 1)
    if "cdo__divider" not in css:
        assert CSS_DIVIDER[0] in css
        css = css.replace(*CSS_DIVIDER, 1)

    if "cdo__card--3" not in html:
        assert HTML_CARDS[0] in html, slug
        html = html.replace(*HTML_CARDS, 1)
    if "cdo__card--7" not in html:
        assert HTML_CARD7[0] in html, slug
        html = html.replace(*HTML_CARD7, 1)
    if "cdo__divider" not in html:
        assert '<div class="cdo__tabunderline"></div>' in html, slug
        html = html.replace('<div class="cdo__tabunderline"></div>',
                            '<div class="cdo__tabunderline"></div>\n  <div class="cdo__divider"></div>', 1)

    # the duplicated 提供獎金 label
    dup = '  <p class="cdo__t" style="left:25px;top:1262.0px;font-size:14px;color:#ff884a;">提供獎金</p>\n'
    if dup in html:
        html = html.replace(dup, "", 1)

    # 睇更多＞ : the ＞ is a drawn chevron, not part of the label
    html = html.replace(">睇更多＞</p>", ">睇更多</p>")

    css_path.write_text(css, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    print("patched", slug)


if __name__ == "__main__":
    for slug in (sys.argv[1:] or ["v1-competition-detail-open", "v73-competition2-03"]):
        patch(slug)
