"""어절을 '어간/체언 + 조사/어미'로 쪼갠다. 연철(이어적기)을 되돌리는 것이 핵심.

중세국어는 앞 글자의 받침을 뒤 글자의 첫소리로 내려 적었다.
    말ᄊᆞ미  =  말ᄊᆞᆷ(체언) + 이(주격)
    기픈    =  깊(어간) + 은(관형사형)
그래서 글자 그대로 쪼개면 사전에서 찾을 수 없다. 받침을 제자리로 돌려놓고 찾아야 한다.

    python3 tools/analyze.py "나랏 말ᄊᆞ미 中國에 달아"
    python3 tools/analyze.py --eval      # 말뭉치에서 얼마나 쪼개지는지
"""
import json, os, re, sys, unicodedata
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")

GRAM = json.load(open(os.path.join(ROOT, "data", "grammar.json"), encoding="utf-8"))
LEX = json.load(open(os.path.join(ROOT, "data", "lexicon.json"), encoding="utf-8"))

# 우리말샘 쪽 사전도 함께 본다. 출처와 라이선스가 달라 파일은 나눠 두되, 찾을 때는 같이 쓴다.
_UR = os.path.join(ROOT, "data", "lexicon-urimal.json")
if os.path.exists(_UR):
    LEX = LEX + json.load(open(_UR, encoding="utf-8"))["entries"]

TONE = "〮〯"
# 조합형/분해형이 섞여 있어 NFC 로 맞춘 뒤 다룬다 (가 U+AC00 과 가 U+1100 U+1161 은 다른 바이트)
detone = lambda s: unicodedata.normalize("NFC", "".join(c for c in (s or "") if c not in TONE))

CHO_A, CHO_Z = "ᄀ", "ᅟ"
JUNG_A, JUNG_Z = "ᅠ", "ᆧ"
JONG_A, JONG_Z = "ᆨ", "ᇿ"
IEUNG = "ᄋ"          # 초성 ㅇ

# 초성/종성이 짝이 되는 자모 (ᄆ U+1106 ↔ ᆷ U+11B7 처럼 글자는 같고 자리가 다름)
PAIR = {}
for c, j in zip("ᄀᄂᄃᄅᄆᄇᄉᄋᄌᄎᄏᄐᄑᄒᄁᄊᅀᅌᅙᄫ", "ᆨᆫᆮᆯᆷᆸᆺᆼᆽᆾᆿᇀᇁᇂᆩᆻᇫᇰᇹᇦ"):
    PAIR[c] = j


def jamo(s):
    return unicodedata.normalize("NFD", detone(s))


def syllables(j):
    out, cur = [], ""
    for ch in j:
        if CHO_A <= ch <= CHO_Z and cur:
            out.append(cur); cur = ch
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def nfc(j):
    return unicodedata.normalize("NFC", j)


# ---- 조사·어미 목록 ----
def collect_endings():
    out = {}

    def add(form, kind, name):
        f = detone(str(form)).strip("-")
        if f and f != "∅":
            out.setdefault(f, []).append((kind, name))

    for p in GRAM["particles"]:
        for f in p["forms"]:
            add(f["form"], "조사", p["name"])
    pe = GRAM["prefinal_endings"]
    for it in pe["items"]:
        for f in it["forms"]:
            add(f["form"], "선어말어미", it["name"])
        for f in it.get("later_forms", {}).get("forms", []):
            add(f["form"], "선어말어미", it["name"])
    fe = GRAM["final_endings"]
    for key, label in [("declarative", "평서형"), ("imperative", "명령형"),
                       ("propositive", "청유형"), ("exclamatory", "감탄형")]:
        for x in fe[key]:
            add(x["form"], "어말어미", label)
    for x in fe["interrogative"]["items"]:
        add(x["form"], "어말어미", "의문형")
    for x in GRAM["connective_endings"]:
        add(x["form"], "연결어미", x.get("meaning", ""))
    for k, label in [("nominal", "명사형"), ("adnominal", "관형사형")]:
        for x in GRAM["transformative_endings"][k]:
            add(x["form"], "전성어미", label)
    return out


ENDINGS = collect_endings()

# ---- 사전 표제어와 어간 ----
VERBAL = {"Verb", "Adjective"}
STEMS = {}
for e in LEX:
    poses = {s["pos"] for s in e["senses"]}
    for k in {detone(e["headword"])} | {detone(s["written"]) for s in e["senses"] if s.get("written")}:
        k = k.strip("-")
        if not k:
            continue
        STEMS.setdefault(k, (e["headword"], "표제어"))
        if poses & VERBAL and k.endswith("다") and len(k) > 1:
            STEMS.setdefault(k[:-1], (e["headword"], "어간"))


# 중세국어의 불규칙 교체. 어간 끝소리가 모음 앞에서 바뀌어 적힌다.
#   돕- + -아  →  도ᄫᅡ   (ㅂ → ㅸ)
#   짓- + -어  →  지ᅀᅥ   (ㅅ → ㅿ)
#   듣- + -어  →  드러   (ㄷ → ㄹ)
# 사전에는 본디 꼴(돕다·짓다·듣다)이 실려 있으므로, 거꾸로 되돌려 찾는다.
IRREGULAR = {"ᄫ": ("ᆸ", "ㅂ불규칙"), "ᅀ": ("ᆺ", "ㅅ불규칙"), "ᄅ": ("ᆮ", "ㄷ불규칙")}


def unlink(tok):
    """연철과 불규칙 교체를 되돌린 꼴들을 만든다. (어간, 어미, 어떻게) 를 돌려준다.

    말ᄊᆞ미 → (말ᄊᆞᆷ, 이, 연철)      끝 음절 초성을 앞 음절 받침으로 옮김
    도ᄫᅡ   → (돕, 아, ㅂ불규칙)      ㅸ 을 ㅂ 받침으로 되돌림
    """
    out = []
    sy = syllables(jamo(tok))
    for i in range(1, len(sy)):
        head, tail = sy[:i], sy[i:]
        first = tail[0]
        # 뒤쪽 첫 음절이 '초성 + 중성' 이고, 앞 음절에 받침이 없을 때만
        if len(first) < 2 or not (CHO_A <= first[0] <= CHO_Z):
            continue
        if not (JUNG_A <= first[1] <= JUNG_Z):
            continue
        prev = head[-1]
        if any(JONG_A <= c <= JONG_Z for c in prev):
            # 앞 음절에 이미 받침이 있으면 연철이 아니다. 다만 ㅎ종성체언은 예외:
            # 하ᄂᆞᆯㅎ + 이 → 하ᄂᆞᆯ히 처럼 받침 뒤에 ㅎ 이 한 번 더 붙는다
            if first[0] == "ᄒ":
                out.append((nfc("".join(head)),
                            nfc("".join([IEUNG + first[1:]] + tail[1:])), "ㅎ종성체언"))
            continue
        cand = []
        if first[0] in PAIR:
            cand.append((PAIR[first[0]], "연철"))
        if first[0] in IRREGULAR:
            cand.append(IRREGULAR[first[0]])
        for moved, how in cand:
            new_head = head[:-1] + [prev + moved]
            new_tail = [IEUNG + first[1:]] + tail[1:]
            out.append((nfc("".join(new_head)), nfc("".join(new_tail)), how))
            # ㅎ종성체언: 하ᄂᆞᆯㅎ + 이 → 하ᄂᆞᆯ히. 사전에는 ㅎ 없이 실린 것이 많다
            if moved == "ᇂ":
                out.append((nfc("".join(head)), nfc("".join(new_tail)), "ㅎ종성체언"))
    return out


# 종성 자모 → 홀로 쓰는 글자 (ᆺ → ㅅ). 관형격 ㅅ 처럼 받침으로 붙는 조사를 떼기 위함
JONG_COMPAT = dict(zip("ᆨᆫᆮᆯᆷᆸᆺᆼᆽᆾᆿᇀᇁᇂᆩᆻᇫᇰ", "ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎㄲㅆㅿㆁ"))


def strip_coda(t):
    """끝 음절의 받침이 조사로 쓰이는 글자면 떼어 낸다. 나랏 → (나라, ㅅ)"""
    j = jamo(t)
    if not j:
        return None
    last = j[-1]
    if not (JONG_A <= last <= JONG_Z):
        return None
    c = JONG_COMPAT.get(last)
    if not c or c not in ENDINGS:
        return None
    return nfc(j[:-1]), c


def split_endings(rest, depth=0):
    """남은 부분이 아는 어미들의 연쇄인지 본다. 되면 어미 목록, 아니면 None.

    중세국어는 어미가 겹쳐 붙는다. ᄒᆞ시니 = ᄒᆞ + 시 + 니 처럼
    선어말어미와 연결어미가 잇따르므로, 하나만 떼어서는 끝까지 못 간다.
    """
    if not rest:
        return []
    if depth > 4:                      # 너무 잘게 쪼개지 않도록
        return None
    for n in range(len(rest), 0, -1):  # 긴 어미부터
        head = rest[:n]
        if head in ENDINGS:
            tail = split_endings(rest[n:], depth + 1)
            if tail is not None:
                return [head] + tail
    return None


def role(form, last):
    """한 꼴이 여러 자리에 쓰일 때, 놓인 자리에 맞는 쪽을 고른다.
    니 는 선어말어미도 되고 연결어미도 되는데, 맨 끝이면 연결어미로 읽는 것이 맞다."""
    opts = ENDINGS[form]
    if last:
        for k, n in opts:
            if k != "선어말어미":
                return (k, n)
    else:
        for k, n in opts:
            if k == "선어말어미":
                return (k, n)
    return opts[0]


def describe(ends):
    parts = [role(e, i == len(ends) - 1) for i, e in enumerate(ends)]
    return " + ".join(ends), " · ".join(f"{k} {n}" for k, n in parts)


def analyze(tok):
    """한 어절을 쪼갠다. 못 쪼개면 None."""
    t = detone(tok)
    def made(stem, ends, how):
        txt, kinds = describe(ends)
        return {"token": tok, "stem": stem, "head": STEMS[stem][0], "stem_kind": STEMS[stem][1],
                "ending": txt, "endings": ends, "ending_kind": kinds, "ending_name": "",
                "via": how if len(ends) < 2 else f"{how}+연쇄"}

    # 1) 글자 그대로 쪼개기 (어미가 여럿 붙어 있어도 됨)
    for i in range(len(t) - 1, 0, -1):
        stem = t[:i]
        if stem not in STEMS:
            continue
        ends = split_endings(t[i:])
        if ends:
            return made(stem, ends, "직접")
    # 2) 연철·불규칙 되돌려 쪼개기
    for stem, end, how in unlink(t):
        if stem in STEMS:
            ends = split_endings(end)
            if ends:
                return made(stem, ends, how)
    # 3) 받침으로 붙은 조사 떼기 (나랏 → 나라 + ㅅ)
    sc = strip_coda(t)
    if sc and sc[0] in STEMS:
        return made(sc[0], [sc[1]], "받침조사")
    # 4) 어미 없이 표제어 자체
    if t in STEMS:
        return {"token": tok, "stem": t, "head": STEMS[t][0], "stem_kind": STEMS[t][1],
                "ending": None, "via": "그대로"}
    return None


PUNCT = re.compile(r"[\s.,·:;!?()\[\]{}「」『』〈〉《》\"']+")


def run(text):
    for tok in PUNCT.split(text):
        if not tok:
            continue
        a = analyze(tok)
        if not a:
            print(f"  {tok:<12} —")
        elif a["ending"]:
            print(f"  {tok:<12} {a['stem']} + {a['ending']}"
                  f"   [{a['stem_kind']} {a['head']} / {a['ending_kind']} · {a['via']}]")
        else:
            print(f"  {tok:<12} {a['stem']}   [{a['stem_kind']} {a['head']} · 그대로]")


def evaluate():
    COR = os.path.join(ROOT, "corpus")
    toks = []
    for f in sorted(os.listdir(COR)):
        if f.endswith(".json") and not f.startswith(".") and f not in ("index.json", "attestations.json", "unknown.json"):
            d = json.load(open(os.path.join(COR, f), encoding="utf-8"))
            for u in d["units"]:
                for line in u["mk"]:
                    toks += [x for x in PUNCT.split(line) if x]
    how = Counter()
    for t in toks:
        a = analyze(t)
        how[a["via"] if a else "못 쪼갬"] += 1
    done = len(toks) - how["못 쪼갬"]
    print(f"말뭉치 어절 {len(toks)}개")
    for k, v in how.most_common():
        print(f"  {k:<8} {v:>5}개 ({v / len(toks) * 100:.1f}%)")
    print(f"\n설명된 어절 {done}개 ({done / len(toks) * 100:.1f}%)")
    print(f"조사·어미 목록 {len(ENDINGS)}개 · 표제어와 어간 {len(STEMS)}개")

    # 못 쪼갠 까닭 가리기: 어미는 알아보는데 어간을 모르는가, 아니면 둘 다 모르는가
    why = Counter()
    for t in toks:
        if analyze(t):
            continue
        d = detone(t)
        cand = [(d[:i], d[i:]) for i in range(len(d) - 1, 0, -1)]
        cand += [(a, b) for a, b, _ in unlink(d)]
        sc = strip_coda(d)
        if sc:
            cand.append(sc)
        if any(split_endings(e) for _, e in cand):
            why["어미는 아는데 어간을 모름"] += 1
        else:
            why["어미도 어간도 모름"] += 1
    print("\n못 쪼갠 까닭:")
    for k, v in why.most_common():
        print(f"  {k:<22} {v:>5}개 ({v / max(1, how['못 쪼갬']) * 100:.0f}%)")


if __name__ == "__main__":
    if "--eval" in sys.argv:
        evaluate()
    elif len(sys.argv) > 1:
        run(" ".join(a for a in sys.argv[1:] if not a.startswith("--")))
    else:
        print(__doc__)
