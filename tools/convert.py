"""중세국어 표기를 현대 한글로 1차 변환한다. 번역기의 맨 앞 단계.

규칙(data/phonology.json)만으로는 반드시 틀리는 자리가 있으므로,
사전(data/lexicon.json)에 올라 있는 말은 규칙보다 사전을 먼저 본다.

    python3 tools/convert.py "나랏 말ᄊᆞ미 中國에 달아"
    python3 tools/convert.py --test
"""
import json, os, re, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

PHON = json.load(open(os.path.join(DATA, "phonology.json"), encoding="utf-8"))
LEX = json.load(open(os.path.join(DATA, "lexicon.json"), encoding="utf-8"))

# 사전: 중세형 → 현대형. 방점을 뗀 표기도 함께 올려 둔다.
TONE = "".join(t["mark"] for t in PHON["tone_marks"] if t["mark"])
detone = lambda s: "".join(c for c in s if c not in TONE)

DICT = {}
for e in LEX:
    mods = e.get("modern")
    if not mods:
        continue
    for key in {e["headword"], detone(e["headword"])} | {
            detone(s["written"]) for s in e["senses"] if s.get("written")}:
        DICT.setdefault(key, mods[0])

# 한글 자모에는 두 벌이 있음.
#   호환 자모(ㄱ ㄸ ㅏ, U+3131~) — 홀로 쓸 때의 글자
#   첫가끝 자모(ᄀ ᄄ ᅡ, U+1100~) — 음절로 합쳐질 때의 글자
# 바꿔 넣을 때 호환 자모를 쓰면 음절이 합쳐지지 않으므로 반드시 첫가끝 쪽을 써야 함.
CHO_C = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
CHO_J = "ᄀᄁᄂᄃᄄᄅᄆᄇᄈᄉᄊᄋᄌᄍᄎᄏᄐᄑᄒ"
JUNG_C = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
JUNG_J = "ᅡᅢᅣᅤᅥᅦᅧᅨᅩᅪᅫᅬᅭᅮᅯᅰᅱᅲᅳᅴᅵ"
JONG_C = "ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"
JONG_J = "ᆨᆩᆪᆫᆬᆭᆮᆯᆰᆱᆲᆳᆴᆵᆶᆷᆸᆹᆺᆻᆼᆽᆾᆿᇀᇁᇂ"
TO_CHO = dict(zip(CHO_C, CHO_J))
TO_JUNG = dict(zip(JUNG_C, JUNG_J))
TO_JONG = dict(zip(JONG_C, JONG_J))

CLUSTER = {c["jamo"]: TO_CHO[c["to"]] for c in PHON["initial_clusters"]["items"] if c["to"] in TO_CHO}
# 옛 글자를 현대 자모로. 빈 값은 '없어짐'을 뜻함
INITIAL = {"ᅀ": "", "ᄫ": "ᄋ", "ᅌ": "ᄋ", "ᅙ": "", "ᅘ": "ᄒ"}
MEDIAL_FIRST = {"ᆞ": "ᅡ", "ᆡ": "ᅢ"}   # 첫음절
MEDIAL_REST = {"ᆞ": "ᅳ", "ᆡ": "ᅢ"}    # 둘째 음절 이하
FINAL = {"ᇰ": "ᆼ", "ᇫ": "", "ᇦ": ""}


def to_jamo(s):
    """음절을 첫가끝 자모로 푼다. 이미 자모면 그대로."""
    return unicodedata.normalize("NFD", s)


def syllables(jamo):
    """자모 열을 음절 덩어리로 끊는다 (초성 기준)."""
    out, cur = [], ""
    for ch in jamo:
        if "ᄀ" <= ch <= "ᅟ" and cur:      # 새 초성이 오면 음절이 바뀜
            out.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def convert_word(w, use_dict=True):
    """낱말 하나를 현대 표기로. 사전에 있으면 사전 값을 쓴다."""
    plain = detone(w)
    if use_dict and plain in DICT:
        return DICT[plain], "사전"
    j = to_jamo(plain)
    out = []
    for i, syl in enumerate(syllables(j)):
        chars = list(syl)
        # 초성
        if chars and "ᄀ" <= chars[0] <= "ᅟ":
            c = chars[0]
            if c in CLUSTER:                         # 어두자음군 → 된소리
                chars[0] = CLUSTER[c]
            elif c in INITIAL:
                chars[0] = INITIAL[c] or "ᄋ"        # 소리가 없어져도 초성 자리는 ㅇ으로 채움
        # 중성·종성
        for k, ch in enumerate(chars):
            if ch in ("ᆞ", "ᆡ"):
                chars[k] = (MEDIAL_FIRST if i == 0 else MEDIAL_REST)[ch]
            elif ch in FINAL:
                chars[k] = FINAL[ch]
        out.append("".join(chars))
    res = unicodedata.normalize("NFC", "".join(out))
    return res, "규칙"


def convert(text):
    parts = re.split(r"(\s+)", text)
    done, how = [], []
    for p in parts:
        if not p.strip():
            done.append(p)
            continue
        r, src = convert_word(p)
        done.append(r)
        how.append((p, r, src))
    return "".join(done), how


TESTS = [
    ("ᄒᆞ다", "하다"),
    ("ᄆᆞᅀᆞᆷ", "마음"),
    ("ᄠᅳᆮ", "뜻"),
    ("ᄭᅮᆷ", "꿈"),
    ("ᄯᅩ", "또"),
]

# 사전을 거치지 않고 규칙만으로 어디까지 가는지 보는 시험.
# 규칙만으로는 닿지 못하는 것이 있는 게 정상이라, 틀린 것도 함께 적어 둔다.
RULE_TESTS = [
    ("ᄭᅮᆷ", "꿈", True),            # ㅺ→ㄲ
    ("ᄡᅳ다", "쓰다", True),          # ㅄ→ㅆ
    ("ᄯᅩ", "또", True),             # ㅼ→ㄸ
    ("ᄆᆞᆯ", "말", True),            # 첫음절 ㆍ→ㅏ
    ("ᄆᆞᅀᆞᆷ", "마음", True),        # ㅿ 없어지고 둘째 음절 ㆍ→ㅡ 로 '마음'까지 닿음
    # 아래 둘은 규칙만으로는 못 닿는 자리. 사전이 받아 준다
    ("ᄠᅳᆮ", "뜻", False),           # 어두자음군은 풀리지만(ᄠ→ㄸ) 8종성법 때문에 '뜯'에서 멈춤
    ("ᄀᆞᄅᆞᆷ", "가람", False),       # 어휘 자체가 바뀐 말 — '가름'까지만 감
]

if __name__ == "__main__":
    if "--test" in sys.argv:
        ok = 0
        for src, want in TESTS:
            got, how = convert_word(src)
            mark = "○" if got == want else "✗"
            ok += got == want
            print(f"  {mark} {src} → {got}  (바라던 값 {want}, {how})")
        print(f"\n{ok}/{len(TESTS)} 맞음 · 사전에 올라 있는 중세형 {len(DICT)}개")

        print("\n규칙만으로 (사전 건너뜀):")
        hit = 0
        for src, want, should in RULE_TESTS:
            got, _ = convert_word(src, use_dict=False)
            good = got == want
            hit += good == should
            mark = "○" if good else "—"
            tail = "" if good == should else "   ← 예상과 다름"
            print(f"  {mark} {src} → {got}" + (f"  (사전 값 {want})" if not good else "") + tail)
        print(f"\n  규칙이 닿는 범위가 예상대로인 것 {hit}/{len(RULE_TESTS)}")
        print("  규칙만으로 못 가는 말은 사전이 받아 줌 — 그래서 사전을 먼저 봄")
    elif len(sys.argv) > 1:
        text = " ".join(a for a in sys.argv[1:] if not a.startswith("--"))
        res, how = convert(text)
        print(res)
        if "-v" in sys.argv:
            print()
            for a, b, s in how:
                print(f"  {a} → {b}  [{s}]")
    else:
        print(__doc__)
