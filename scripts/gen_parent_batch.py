#!/usr/bin/env python3
"""Generate the invite-records / invite-1 / ai-agreement-modal screens."""
from pathlib import Path

R = Path("/Users/blee/src/figma")

STATUS = """  <div class="{c}__status {c}__st">
    <span class="{c}__time">9:41</span>
    <span class="{c}__icons">
      <svg class="{c}__ic-signal" width="20" height="13" viewBox="0 0 20 13" fill="{ic}"><rect x="0.5" y="8.5" width="3.5" height="4" rx="1.2"/><rect x="5.5" y="5.5" width="3.5" height="7" rx="1.2"/><rect x="10.5" y="3" width="3.5" height="9.5" rx="1.2"/><rect x="15.5" y="0.5" width="3.5" height="12" rx="1.2"/></svg>
      <svg class="{c}__ic-wifi" width="16" height="11" viewBox="-1.5 -2 17.5 13" fill="{ic}"><path d="M8 11.2 5.4 8.5a3.7 3.7 0 0 1 5.2 0zM3.3 6.3 1.6 4.5a9 9 0 0 1 12.8 0l-1.7 1.8a6.7 6.7 0 0 0-9.4 0zM.3 3.1-1.6 1.3A13 13 0 0 1 16 1.3l-1.9 1.8a10.7 10.7 0 0 0-13.8 0z"/></svg>
      <svg class="{c}__ic-batt" width="25" height="12" viewBox="0 0 25 12"><rect x="0.5" y="0.5" width="21.4" height="11" rx="3.2" fill="none" stroke="{ic}" stroke-opacity=".38" stroke-width="1"/><rect x="2.2" y="2.2" width="17.9" height="7.6" rx="2" fill="{ic}"/><path d="M23.3 3.9v4.2a2.2 2.2 0 0 0 0-4.2z" fill="{ic}" fill-opacity=".38"/></svg>
    </span>
  </div>"""

CHEVRON = """<svg width="9" height="15" viewBox="0 0 9 15"><path d="M7.4 1.6 1.6 7.5l5.8 5.9" fill="none" stroke="{c}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>"""

# ---------------------------------------------------------------- invite-records
CARDS = [
    ("一位媽媽 註冊成功", "2023-10-24 好友邀請", "+20"),
    ("媽媽個用戶名 註冊成功", "2023-10-24 直接邀請", "+100"),
    ("Lucia 註冊成功", "2023-10-24 直接邀請", "+100"),
    ("Sherry 註冊成功", "2023-10-23 好友邀請", "+20"),
    ("Lucia 註冊成功", "2023-10-24 直接邀請", "+100"),
]
TOPS = [134, 214, 293, 373, 452]

rows = []
for i, (t, sub, pts) in enumerate(CARDS):
    rows.append(f"""  <article class="ir__card ir__card--{i+1}">
    <p class="ir__ct">{t}</p>
    <p class="ir__cs">{sub}</p>
    <p class="ir__cp">{pts}</p>
  </article>""")

ir_html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=390, initial-scale=1">
<title>邀請紀錄</title>
<link rel="stylesheet" href="assets/fonts/fonts.css">
<link rel="stylesheet" href="styles-v1.css">
<link rel="stylesheet" href="assets/v1/invite-records.css">
<link rel="stylesheet" href="assets/v1/invite-records-fonts.css">
</head>
<body>
<div class="v1 v1--ir" style="width:390px;height:848px">

  <div class="ir__head"></div>

{STATUS.format(c="ir", ic="#000")}

  <div class="ir__back">
    {CHEVRON.format(c="#1c1c1e")}
  </div>

  <h1 class="ir__title">邀請紀錄</h1>

  <div class="ir__sheet"></div>

{chr(10).join(rows)}

</div>
</body>
</html>
"""

ir_css = """/* ==========================================================================
   v1-invite-records — 邀請紀錄 (390 x 848)
   Measured from source/v1raw/screens/invite-records.png (4x export).
   ========================================================================== */

.v1--ir { background: #fff8f4; }

/* ------------------------------------------------------------- header */

.v1--ir .ir__head {
  left: 0; top: 0;
  width: 390px; height: 143px;
  background: #fc6665 url("invite-records-head.png") no-repeat 0 0 / 100% 100%;
  z-index: 1;
}

/* --------------------------------------------------------- status bar */

.v1--ir .ir__st {
  display: block; padding: 0; height: 44px; z-index: 6;
}
.v1--ir .ir__time {
  left: 54px; top: 21px;
  font-family: "Arimo", sans-serif;
  font-size: 15px; font-weight: 600; line-height: 1;
  color: #000000;
}
.v1--ir .ir__icons { left: 281px; top: 21px; height: 13px; }
.v1--ir .ir__ic-signal { left: 0; top: 0; }
.v1--ir .ir__ic-wifi   { left: 25.5px; top: 2px; }
.v1--ir .ir__ic-batt   { left: 52px; top: 1px; }

/* -------------------------------------------------------- back button */

.v1--ir .ir__back {
  left: 20px; top: 60px;
  width: 40px; height: 40px;
  border-radius: 50%;
  background: #ffffff;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06);
  z-index: 5;
}
.v1--ir .ir__back svg { position: absolute; left: 15.5px; top: 12.5px; }

/* -------------------------------------------------------------- title */

.v1--ir .ir__title {
  left: 72px; top: 67px;
  margin: 0;
  font-family: "Noto Sans TC", sans-serif;
  font-size: 20px; font-weight: 700; line-height: 28px;
  color: #ffffff;
  z-index: 4;
}

/* -------------------------------------------------------------- sheet */

.v1--ir .ir__sheet {
  left: 0; top: 115px;
  width: 390px; height: 733px;
  border-radius: 28px 28px 0 0;
  background: #fff8f4;
  z-index: 2;
}

/* -------------------------------------------------------------- cards */

.v1--ir .ir__card {
  left: 24px;
  width: 342px; height: 64px;
  border-radius: 16px;
  background: #ffffff;
  z-index: 4;
}
.v1--ir .ir__card--1 { top: 134px; }
.v1--ir .ir__card--2 { top: 214px; }
.v1--ir .ir__card--3 { top: 293px; }
.v1--ir .ir__card--4 { top: 373px; }
.v1--ir .ir__card--5 { top: 452px; }

.v1--ir .ir__ct {
  left: 16px; top: 9px;
  margin: 0;
  font-family: "Noto Sans TC", sans-serif;
  font-size: 16px; font-weight: 500; line-height: 22px;
  color: #1f1f1f;
  z-index: 5;
}
.v1--ir .ir__cs {
  left: 16px; top: 31px;
  margin: 0;
  font-family: "Noto Sans TC", sans-serif;
  font-size: 12px; font-weight: 400; line-height: 17px;
  color: #a39b97;
  z-index: 5;
}
.v1--ir .ir__cp {
  left: 250px; top: 18px;
  width: 68px;
  margin: 0;
  text-align: right;
  font-family: "Poppins", sans-serif;
  font-size: 18px; font-weight: 600; line-height: 24px;
  color: #ff7730;
  z-index: 5;
}
"""

# ---------------------------------------------------------------- invite-1
inv1_html = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=402, initial-scale=1">
<title>邀請好友</title>
<link rel="stylesheet" href="assets/fonts/fonts.css">
<link rel="stylesheet" href="styles-v1.css">
<link rel="stylesheet" href="assets/v1/invite-1.css">
<link rel="stylesheet" href="assets/v1/invite-1-fonts.css">
</head>
<body>
<div class="v1 v1--iv" style="width:402px;height:874px">

  <div class="iv__head"></div>

""" + STATUS.format(c="iv", ic="#ffffff") + """

  <div class="iv__back">
    """ + CHEVRON.format(c="#1a1a1a") + """
  </div>

  <div class="iv__history">
    <svg width="19" height="19" viewBox="0 0 19 19" fill="none" stroke="#1a1a1a" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3.2 9.5a6.3 6.3 0 1 0 1.9-4.5"/><path d="M2.4 2.6v3.2h3.2"/><path d="M9.5 5.6v4l2.7 1.7"/></svg>
  </div>

  <img class="iv__hero" src="assets/v1/invite-1-hero.png" alt="">

  <h1 class="iv__title">邀請好友，輕鬆賺積分</h1>
  <p class="iv__rules">只限邀請從未註冊過的新用戶，<br>邀請成功後雙方均可獲得積分，<br>好友再成功邀請其他新用戶亦可獲得額外積分。</p>

  <article class="iv__stat iv__stat--l">
    <p class="iv__sl">已邀請好友</p>
    <p class="iv__sv">12<span class="iv__su">人</span></p>
  </article>
  <article class="iv__stat iv__stat--r">
    <p class="iv__sl">獲得積分</p>
    <p class="iv__sv">2,400<span class="iv__su">pts</span></p>
  </article>

  <article class="iv__task iv__task--1">
    <img class="iv__ticon iv__ticon--1" src="assets/v1/invite-1-t1.png" alt="">
    <p class="iv__tt">邀請 1 位好友</p>
    <p class="iv__ts"><span class="iv__ts-a">雙方</span> <span class="iv__ts-b">+100</span> 積分</p>
  </article>
  <article class="iv__task iv__task--2">
    <img class="iv__ticon iv__ticon--2" src="assets/v1/invite-1-t2.png" alt="">
    <p class="iv__tt">好友再邀請好友</p>
  </article>

  <div class="iv__sheet"></div>

  <div class="iv__codecard"></div>
  <img class="iv__avatar" src="assets/v1/invite-1-avatar.png" alt="">
  <p class="iv__clabel">我的邀請碼</p>
  <p class="iv__code">COFFEE</p>
  <span class="iv__copy">複製邀请码</span>
  <p class="iv__cta">分享我的邀請圖片</p>
  <div class="iv__homebar"></div>

</div>
</body>
</html>
"""

inv1_css = """/* ==========================================================================
   v1-invite-1 — 邀請好友 (402 x 874)
   Measured from source/v1raw/screens/invite-1.png (4x export).
   ========================================================================== */

.v1--iv { background: #fc8947; }

/* ------------------------------------------------------------- header */

.v1--iv .iv__head {
  left: 0; top: 0;
  width: 402px; height: 268px;
  background: #fc8947 url("invite-1-head.png") no-repeat 0 0 / 100% 100%;
  z-index: 1;
}

/* --------------------------------------------------------- status bar */

.v1--iv .iv__st {
  display: block; padding: 0; height: 44px; z-index: 6;
}
.v1--iv .iv__time {
  left: 56px; top: 21px;
  font-family: "Arimo", sans-serif;
  font-size: 15px; font-weight: 600; line-height: 1;
  color: #ffffff;
}
.v1--iv .iv__icons { left: 281px; top: 21px; height: 13px; }
.v1--iv .iv__ic-signal { left: 0; top: 0; }
.v1--iv .iv__ic-wifi   { left: 25.5px; top: 2px; }
.v1--iv .iv__ic-batt   { left: 52px; top: 1px; }

/* ----------------------------------------------------- header buttons */

.v1--iv .iv__back,
.v1--iv .iv__history {
  top: 58px;
  width: 40px; height: 40px;
  border-radius: 50%;
  background: #ffffff;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06);
  z-index: 5;
}
.v1--iv .iv__back { left: 20px; }
.v1--iv .iv__back svg { position: absolute; left: 15.5px; top: 12.5px; }
.v1--iv .iv__history { left: 342px; }
.v1--iv .iv__history svg { position: absolute; left: 10.5px; top: 10.5px; }

/* --------------------------------------------------------------- hero */

.v1--iv .iv__hero {
  left: 62px; top: 72px;
  width: 278px; height: 196px;
  z-index: 3;
}

/* ---------------------------------------------------------- title/rules */

.v1--iv .iv__title {
  left: 0; top: 280px;
  width: 402px;
  margin: 0;
  text-align: center;
  font-family: "Noto Sans TC", sans-serif;
  font-size: 28px; font-weight: 700; line-height: 36px;
  color: #ffffff;
  z-index: 4;
}
.v1--iv .iv__rules {
  left: 32px; top: 326px;
  width: 338px;
  margin: 0;
  text-align: center;
  font-family: "Noto Sans TC", sans-serif;
  font-size: 15.5px; font-weight: 400; line-height: 21px;
  color: rgba(255, 255, 255, 0.9);
  z-index: 4;
}

/* ---------------------------------------------------------- stat cards */

.v1--iv .iv__stat {
  top: 411px;
  width: 168px; height: 86px;
  border-radius: 20px;
  background: #fff8f4;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
  z-index: 4;
}
.v1--iv .iv__stat--l { left: 21px; width: 171px; }
.v1--iv .iv__stat--r { left: 209px; width: 172px; }

.v1--iv .iv__sl {
  left: 16px; top: 17px;
  margin: 0;
  font-family: "Noto Sans TC", sans-serif;
  font-size: 13.9px; font-weight: 500; line-height: 18px;
  color: #7d7d7d;
  z-index: 5;
}
.v1--iv .iv__sv {
  left: 16px; top: 40px;
  margin: 0;
  font-family: "Poppins", sans-serif;
  font-size: 30px; font-weight: 700; line-height: 38px;
  color: #fa7b38;
  z-index: 5;
}
.v1--iv .iv__su {
  position: static;
  font-family: "Noto Sans TC", sans-serif;
  font-size: 14px; font-weight: 500;
}

/* ---------------------------------------------------------- task cards */

.v1--iv .iv__task {
  left: 24px;
  width: 356px; height: 70px;
  border-radius: 20px;
  background: #fff8f4;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
  z-index: 4;
}
.v1--iv .iv__task--1 { top: 517px; }
.v1--iv .iv__task--2 { top: 611px; }

.v1--iv .iv__ticon {
  left: 10px; top: 11px;
  width: 46px; height: 48px;
  z-index: 5;
}
.v1--iv .iv__ticon--2 { left: 10px; top: 11px; width: 46px; height: 46px; }

.v1--iv .iv__tt {
  left: 64px; top: 14.5px;
  margin: 0;
  font-family: "Noto Sans TC", sans-serif;
  font-size: 16px; font-weight: 700; line-height: 22px;
  color: #1a1a1a;
  white-space: nowrap;
  z-index: 5;
}
.v1--iv .iv__ts {
  left: 64px; top: 42.5px;
  margin: 0;
  white-space: nowrap;
  font-family: "Noto Sans TC", sans-serif;
  font-size: 13.5px; font-weight: 400; line-height: 18px;
  letter-spacing: 0.25px;
  color: #7d7d7d;
  z-index: 5;
}
.v1--iv .iv__ts-a { position: static; margin-right: 2px; }
.v1--iv .iv__ts-b { position: static; font-weight: 600; color: #fa7b38; }

/* ------------------------------------------------------- bottom sheet */

.v1--iv .iv__sheet {
  left: 0; top: 654px;
  width: 402px; height: 220px;
  border-radius: 28px 28px 0 0;
  background: #ffffff;
  box-shadow: 0 -6px 20px rgba(0, 0, 0, 0.06);
  z-index: 8;
}

.v1--iv .iv__codecard {
  left: 24px; top: 670px;
  width: 356px; height: 74px;
  border: 1px solid #f7ddd0;
  border-radius: 20px;
  background: #fbf7fa;
  z-index: 9;
}
.v1--iv .iv__avatar {
  left: 36px; top: 684px;
  width: 50px; height: 54px;
  z-index: 10;
}
.v1--iv .iv__clabel {
  left: 96px; top: 688px;
  margin: 0;
  font-family: "Noto Sans TC", sans-serif;
  font-size: 13.4px; font-weight: 400; line-height: 17px;
  color: #8c8c8c;
  z-index: 10;
}
.v1--iv .iv__code {
  left: 96px; top: 711px;
  margin: 0;
  font-family: "Poppins", sans-serif;
  font-size: 19px; font-weight: 700; line-height: 24px;
  letter-spacing: 0.5px;
  color: #1a1a1a;
  z-index: 10;
}
.v1--iv .iv__copy {
  left: 253px; top: 691px;
  width: 104px; height: 40px;
  border-radius: 20px;
  background: #ffffff;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
  font-family: "Noto Sans TC", sans-serif;
  font-size: 15.5px; font-weight: 600; line-height: 40px;
  text-align: center;
  color: #e6733b;
  z-index: 10;
}

.v1--iv .iv__cta {
  left: 19px; top: 766px;
  width: 365px; height: 58px;
  margin: 0;
  border-radius: 20px;
  background: #ff7d58 url("invite-1-cta.png") no-repeat 0 0 / 100% 100%;
  font-family: "Noto Sans TC", sans-serif;
  font-size: 18px; font-weight: 700; line-height: 66px;
  text-align: center;
  color: #ffffff;
  z-index: 9;
}

.v1--iv .iv__homebar {
  left: 131px; top: 861px;
  width: 139px; height: 5px;
  border-radius: 3px;
  background: #000000;
  z-index: 10;
}
"""

# ---------------------------------------------------------------- agreement
ag_html = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=402, initial-scale=1">
<title>私隱政策聲明</title>
<link rel="stylesheet" href="assets/fonts/fonts.css">
<link rel="stylesheet" href="styles-v1.css">
<link rel="stylesheet" href="assets/v1/ai-agreement-modal.css">
<link rel="stylesheet" href="assets/v1/ai-agreement-modal-fonts.css">
</head>
<body>
<div class="v1 v1--ag" style="width:402px;height:874px">

  <div class="ag__scrim"></div>

  <div class="ag__sheet"></div>

  
  <p class="ag__logo">Aimeee</p>
    <h1 class="ag__title">私隱政策聲明</h1>
  <p class="ag__body">本功能將使用第三方 AI服務處理您輸入的內容<br>（如暱稱、出生資料、聊天訊息），以生成分析結<br>果。資料將加密傳輸，且不會用於模型訓練。</p>
  <p class="ag__ask">是否同意繼續使用？</p>
  <p class="ag__link">《私隱政策聲明》</p>
    <p class="ag__cancel">取消</p>
  <p class="ag__agree">同意</p>

</div>
</body>
</html>
"""

ag_css = """/* ==========================================================================
   v1-ai-agreement-modal — AI 協議窗口 (402 x 874)
   Measured from source/v1raw/screens/ai-agreement-modal.png (4x export).
   ========================================================================== */

.v1--ag { background: #666666; }

.v1--ag .ag__scrim {
  left: 0; top: 0;
  width: 402px; height: 874px;
  background: #666666;
  z-index: 1;
}

.v1--ag .ag__sheet {
  left: 0; top: 498px;
  width: 402px; height: 376px;
  border-radius: 32px 32px 0 0;
  background: #ffffff;
  z-index: 2;
}

.v1--ag .ag__logo {
  left: 0; top: 529px;
  width: 402px;
  margin: 0;
  text-align: center;
  font-family: "Poppins", sans-serif;
  font-size: 28px; font-weight: 700; line-height: 34px;
  background: linear-gradient(90deg, #9c55a8 0%, #db4f7a 42%, #f7764b 75%, #f48e44 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  z-index: 3;
}

.v1--ag .ag__title {
  left: 0; top: 571px;
  width: 402px;
  margin: 0;
  text-align: center;
  font-family: "Noto Sans TC", sans-serif;
  font-size: 22px; font-weight: 700; line-height: 28px;
  color: #000000;
  z-index: 3;
}

.v1--ag .ag__body {
  left: 32px; top: 626px;
  width: 338px;
  margin: 0;
  text-align: center;
  font-family: "Noto Sans TC", sans-serif;
  font-size: 14px; font-weight: 400; line-height: 22px;
  color: #000000;
  z-index: 3;
}

.v1--ag .ag__ask {
  left: 0; top: 696px;
  width: 402px;
  margin: 0;
  text-align: center;
  font-family: "Noto Sans TC", sans-serif;
  font-size: 14px; font-weight: 400; line-height: 20px;
  color: #000000;
  z-index: 3;
}

.v1--ag .ag__link {
  left: 0; top: 722px;
  width: 402px;
  margin: 0;
  text-align: center;
  font-family: "Noto Sans TC", sans-serif;
  font-size: 12px; font-weight: 400; line-height: 16px;
  color: #949494;
  z-index: 3;
}

.v1--ag .ag__cancel {
  left: 28px; top: 764px;
  width: 80px; height: 64px;
  margin: 0;
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
  font-family: "Noto Sans TC", sans-serif;
  font-size: 17px; font-weight: 700; line-height: 64px;
  text-align: center;
  color: #000000;
  z-index: 3;
}

.v1--ag .ag__agree {
  left: 124px; top: 764px;
  width: 250px; height: 64px;
  margin: 0;
  border-radius: 24px;
  background: linear-gradient(135deg, #ff6452 0%, #fa8c48 100%);
  box-shadow: 0 8px 24px rgba(250, 140, 72, 0.35);
  font-family: "Noto Sans TC", sans-serif;
  font-size: 17px; font-weight: 700; line-height: 64px;
  text-align: center;
  color: #ffffff;
  z-index: 3;
}
"""

(R / "v1-invite-records.html").write_text(ir_html, encoding="utf-8")
(R / "assets/v1/invite-records.css").write_text(ir_css, encoding="utf-8")
(R / "v1-invite-1.html").write_text(inv1_html, encoding="utf-8")
(R / "assets/v1/invite-1.css").write_text(inv1_css, encoding="utf-8")
(R / "v1-ai-agreement-modal.html").write_text(ag_html, encoding="utf-8")
(R / "assets/v1/ai-agreement-modal.css").write_text(ag_css, encoding="utf-8")
print("written")
