"""나눔바른고딕 옛한글을 이 사전에 쓰이는 글자만 남겨 줄이고, 이름을 바꾼다.

SIL OFL 1.1 의 3항: 수정본은 Reserved Font Name 을 쓸 수 없다.
subset 은 수정본이므로 'NanumBarunGothic' 이 들어간 이름을 떼고 새 이름을 단다.
저작권 표시와 만든 이들은 그대로 둔다 (OFL 이 그러라고 한다).
"""
import os, subprocess, sys
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
SRC = sys.argv[1] if len(sys.argv) > 1 else ""
CP = os.path.join(ROOT, "fonts", "codepoints.txt")
OUT = os.path.join(ROOT, "fonts", "16s-kr-yet.woff2")
if not SRC or not os.path.exists(SRC):
    print(__doc__)
    print("쓰는 법: python3 tools/makefont.py <나눔바른고딕 옛한글.ttf>")
    sys.exit(1)
NEW_FAMILY = "16s-kr Yet"
NEW_PS = "16s-krYet-Regular"

tmp = OUT + ".tmp.ttf"
subprocess.run([sys.executable, "-I", "-m", "fontTools.subset", SRC,
                f"--unicodes-file={CP}", "--layout-features=*",
                f"--output-file={tmp}"], check=True)

f = TTFont(tmp)
name = f["name"]
old = {r.nameID: str(r) for r in name.names if r.platformID == 3}

NOTICE = (
    "Copyright (c) 2010, NAVER Corporation (https://www.navercorp.com/) "
    "with Reserved Font Name Nanum, NanumBarunGothic. "
    "Original: NanumBarunGothic YetHangul, (c) 2014 NHN Corporation, designed by FONTRIX Inc. "
    "This is a modified version: subset to the characters used by 16s-kr.meiro.kr and renamed, "
    "as required by SIL OFL 1.1 clause 3. Licensed under the SIL Open Font License, Version 1.1."
)
LICENSE_DESC = (
    "This Font Software is licensed under the SIL Open Font License, Version 1.1. "
    "No modified version may use the Reserved Font Names."
)

want = {
    0: NOTICE,
    1: NEW_FAMILY,
    2: "Regular",
    3: f"{NEW_FAMILY}; subset of NanumBarunGothic YetHangul 1.0.0.4",
    4: f"{NEW_FAMILY} Regular",
    6: NEW_PS,
    13: LICENSE_DESC,
    14: "https://openfontlicense.org/",
    16: NEW_FAMILY,
    17: "Regular",
}
# 만든 이·제작사(8, 9, 11)는 그대로 둔다
for nid, val in want.items():
    name.setName(val, nid, 3, 1, 0x409)
    name.setName(val, nid, 1, 0, 0)
# 예전 이름이 남지 않게, 바꾸지 않은 칸 가운데 Nanum 이 들어간 것은 지운다
keep = []
for r in name.names:
    if r.nameID in want or "Nanum" not in str(r) or r.nameID in (8, 9, 11):
        keep.append(r)
name.names = keep

f.save(tmp + "2")
subprocess.run([sys.executable, "-I", "-m", "fontTools.ttLib.woff2", "compress",
                "-o", OUT, tmp + "2"], check=True)
for x in (tmp, tmp + "2"):
    os.remove(x)

g = TTFont(OUT)
n = {r.nameID: str(r) for r in g["name"].names if r.platformID == 3}
print(f"\n만든 글꼴: {OUT}  {os.path.getsize(OUT)/1024:.0f}KB")
for k in (1, 4, 6, 0, 13):
    print(f"  nameID {k:>2}: {n.get(k, '')[:110]}")
leftover = [f"{r.nameID}" for r in g["name"].names if "Nanum" in str(r) and r.nameID not in (0, 3, 8, 9, 11)]
print("  이름에 Nanum 이 남은 칸:", leftover or "없음")
