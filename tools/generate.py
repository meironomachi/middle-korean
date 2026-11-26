"""현대 한국어를 중세국어 표기로 되돌린다. analyze.py 의 반대 방향.

쪼개는 것보다 어렵다. 쪼갤 때는 글자가 이미 있어서 사전에서 찾기만 하면 되지만,
되돌릴 때는 **없는 것을 골라 만들어야** 한다. 고를 것이 셋이다.

  1. 낱말    '사람' → 사ᄅᆞᆷ / 놈   (사전에 후보가 여럿)
  2. 조사    '을'  → ᄋᆞᆯ / 을 / ᄅᆞᆯ / 를  (모음조화 + 받침 유무)
  3. 표기    사ᄅᆞᆷ + ᄋᆞᆫ → 사ᄅᆞᄆᆞᆫ  (연철, 이어적기)

1은 사전이 정해 주고, 2와 3은 grammar.json 의 rule 과 phonology.json 이 정해 준다.
원래 이 둘은 **기계가 고르라고** 넣어 둔 것이다.

    python3 tools/generate.py "나라의 말이 중국과 달라"
    python3 tools/generate.py --eval          # 용비어천가 대역으로 얼마나 맞는지
"""
import json, os, re, sys, unicodedata
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")

GRAM = json.load(open(os.path.join(ROOT, "data", "grammar.json"), encoding="utf-8"))
PHON = json.load(open(os.path.join(ROOT, "data", "phonology.json"), encoding="utf-8"))
LEX = json.load(open(os.path.join(ROOT, "data", "lexicon.json"), encoding="utf-8"))
_UR = os.path.join(ROOT, "data", "lexicon-urimal.json")
if os.path.exists(_UR):
    LEX = LEX + json.load(open(_UR, encoding="utf-8"))["entries"]
_ET = os.path.join(ROOT, "data", "lexicon-etym.json")
if os.path.exists(_ET):
    LEX = LEX + json.load(open(_ET, encoding="utf-8"))["entries"]

TONE = "〮〯"
detone = lambda s: unicodedata.normalize("NFC", "".join(c for c in (s or "") if c not in TONE))
jamo = lambda s: unicodedata.normalize("NFD", detone(s))
nfc = lambda j: unicodedata.normalize("NFC", j)

CHO_A, CHO_Z = "ᄀ", "ᅟ"
JUNG_A, JUNG_Z = "ᅠ", "ᆧ"
JONG_A, JONG_Z = "ᆨ", "ᇿ"
IEUNG = "ᄋ"

# 중성 자모 → 홀로 쓰는 모음 글자 (ᅡ U+1161 → ㅏ U+314F). 모음조화를 가리는 데 쓴다
JUNG_COMPAT = {chr(0x1161 + i): chr(0x314F + i) for i in range(21)}
JUNG_COMPAT["ᆞ"] = "ㆍ"          # 아래아
JONG_COMPAT = dict(zip("ᆨᆫᆮᆯᆷᆸᆺᆼᆽᆾᆿᇀᇁᇂᆩᆻᇫᇰ", "ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎㄲㅆㅿㆁ"))

# 받침 둘이 겹쳐 한 글자가 되는 것. 관형격 ㅅ 이 받침 뒤에 올 때 쓴다
#   셔ᄫᅳᆯ + ㅅ → 셔ᄫᅳᆳ    (ᆯ U+11AF + ᆺ U+11BA → ᆳ U+11B3)
# ㄴ·ㅁ 뒤에는 겹받침 글자가 없으므로 넣지 않았다
DOUBLE_CODA = {
    ("\u11A8", "\u11BA"): "\u11AA",   # ᆨ + ᆺ → ᆪ
    ("\u11AF", "\u11BA"): "\u11B3",   # ᆯ + ᆺ → ᆳ
    ("\u11B8", "\u11BA"): "\u11B9",   # ᆸ + ᆺ → ᆹ
}

YANG = set(PHON["vowel_harmony"]["yang"]["vowels"])
YIN = set(PHON["vowel_harmony"]["yin"]["vowels"])


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


def harmony(word):
    """낱말의 모음조화 부류. 뒤에서부터 보되 중성(ㅣ)은 건너뛴다."""
    for ch in reversed(jamo(word)):
        if JUNG_A <= ch <= JUNG_Z:
            v = JUNG_COMPAT.get(ch)
            if v in YANG:
                return "yang"
            if v in YIN:
                return "yin"
    return "yang"      # ㅣ 뿐이거나 못 가리면 양성 쪽으로 (중세에 더 흔함)


def tail(word):
    """끝소리. ('consonant'|'vowel', 받침글자 or 모음글자)"""
    j = jamo(word)
    if not j:
        return ("vowel", "")
    last = j[-1]
    if JONG_A <= last <= JONG_Z:
        return ("consonant", JONG_COMPAT.get(last, ""))
    if JUNG_A <= last <= JUNG_Z:
        return ("vowel", JUNG_COMPAT.get(last, ""))
    return ("consonant", "")


def fits(rule, word):
    """grammar.json 의 rule 이 이 낱말 뒤에 들어맞는지."""
    if not rule:
        return True
    kind, ch = tail(word)
    if "harmony" in rule and rule["harmony"] != "both" and rule["harmony"] != harmony(word):
        return False
    e = rule.get("ends")
    if e == "consonant" and kind != "consonant":
        return False
    if e == "vowel" and kind != "vowel":
        return False
    if e == "vowel_i" and not (kind == "vowel" and ch == "ㅣ"):
        return False
    if e == "vowel_not_i" and not (kind == "vowel" and ch != "ㅣ"):
        return False
    if e == "vowel_or_l" and not (kind == "vowel" or ch == "ㄹ"):
        return False
    # 유정/무정과 높임은 글만 보고 알 수 없다. 무정·예사 쪽을 기본으로 둔다
    if rule.get("animacy") == "animate" or rule.get("honorific") or rule.get("special"):
        return False
    return True


# ---- 현대어 → 중세어 낱말 사전 (사전을 뒤집는다) ----
def build_reverse():
    rev = defaultdict(list)
    for e in LEX:
        hw = detone(e["headword"])
        if not hw or hw.startswith("-"):      # 접사는 통째로 쓸 수 없다
            continue
        # 위키낱말사전 쪽이 사람 손을 탄 것이라 먼저 본다
        src = e.get("source") or "위키낱말사전"
        # 어원란에서 온 것은 현대어와 짝이 또렷해 가장 먼저 본다.
        # 그 다음이 손을 탄 위키낱말사전 표제어, 마지막이 우리말샘.
        pri = {"위키낱말사전 어원란": 0, "위키낱말사전": 1}.get(src, 2)
        for m in e.get("modern") or []:
            m = detone(m).strip()
            if m:
                rev[m].append((pri, len(hw), hw))
    return {k: [h for _, _, h in sorted(set(v))] for k, v in rev.items()}


REV = build_reverse()

# ---- 현대어 조사 → 중세어 조사 ----
# grammar.json 의 particles 에 modern('이/가') 과 rule 이 같이 있어서 그대로 쓴다
def build_particles():
    out = defaultdict(list)
    for p in GRAM["particles"]:
        mods = [x.strip() for x in re.split(r"[/·,]", p.get("modern") or "") if x.strip()]
        mods = [re.sub(r"[()]", "", m) for m in mods]
        for m in mods:
            for f in p["forms"]:
                form = detone(f["form"]).strip("-")
                if form and form != "∅":
                    out[m].append((form, f.get("rule"), p["name"]))
                elif form == "∅":
                    out[m].append(("", f.get("rule"), p["name"]))
    return out


PARTICLES = build_particles()
# 긴 것부터 떼어야 '으로' 가 '로' 보다 먼저 걸린다
PART_KEYS = sorted(PARTICLES, key=len, reverse=True)

# 용언 어미. 현대어 꼴 → 중세어 꼴. 자주 쓰는 것만 손으로 적었다
VERB_ENDINGS = [
    ("습니다", "ᄂᆞᅌᅵ다"), ("ㅂ니다", "ᄂᆞᅌᅵ다"), ("습니까", "ᄂᆞ니ᅌᅵᆺ가"),
    ("십시오", "쇼셔"), ("세요", "쇼셔"), ("ㅂ시다", "사이다"),
    ("는다", "ᄂᆞ다"), ("ㄴ다", "ᄂᆞ다"), ("는가", "ᄂᆞᆫ가"), ("는고", "ᄂᆞᆫ고"),
    ("느냐", "ᄂᆞ뇨"), ("으냐", "녀"), ("냐", "녀"),
    ("으시", "ᄋᆞ시"), ("시", "시"),
    ("고자", "고져"), ("자", "져"),
    ("다", "다"), ("고", "고"), ("며", "며"), ("니", "니"), ("나", "나"),
    ("아라", "라"), ("어라", "라"), ("라", "라"),
    ("은", "ᄋᆞᆫ"), ("는", "ᄂᆞᆫ"), ("ㄴ", "ㄴ"), ("을", "ᄋᆞᆯ"), ("ㄹ", "ㄹ"),
    ("음", "옴"), ("기", "기"),
    ("나이다", "니ᅌᅵ다"), ("더니", "더니"), ("으므로", "ᄊᆡ"), ("므로", "ᄊᆡ"),
]
VERB_ENDINGS.sort(key=lambda x: -len(x[0]))   # 긴 어미부터 떼어야 한다


def join(body, suffix):
    """체언·어간 뒤에 조사·어미를 붙이고 연철(이어적기)로 적는다.

    사ᄅᆞᆷ + ᄋᆞᆫ → 사ᄅᆞᄆᆞᆫ   받침을 뒤 음절 첫소리로 내려 적음
    나라   + ㅅ   → 나랏        홀로 쓰는 자음은 받침으로 올려 붙임
    """
    if not suffix:
        return body
    # ㅅ·ㄴ·ㄹ 처럼 홀로 쓰는 자음은 앞 글자 받침으로 붙인다
    if suffix in JONG_COMPAT.values() or suffix in ("ㅅ", "ㄴ", "ㄹ", "ㅁ"):
        back = {v: k for k, v in JONG_COMPAT.items()}
        jo = back.get(suffix)
        if not jo:
            return body + suffix
        bj = jamo(body)
        if not bj or not (JONG_A <= bj[-1] <= JONG_Z):
            return nfc(bj + jo)                      # 나라 + ㅅ → 나랏
        # 이미 받침이 있을 때. ㅎ종성체언의 ㅎ 은 자음 앞에서 적히지 않는다
        if bj[-1] == "\u11C2":                       # ᇂ
            return nfc(bj[:-1] + jo)                 # 나랗 + ㅅ → 나랏
        both = DOUBLE_CODA.get((bj[-1], jo))
        if both:
            return nfc(bj[:-1] + both)               # 셔ᄫᅳᆯ + ㅅ → 셔ᄫᅳᆳ
        return body + suffix
    if suffix == "ㅣ":                       # 주격 ㅣ 는 앞 글자에 붙여 적는다
        return nfc(jamo(body) + "ᅵ")

    bj, sj = jamo(body), jamo(suffix)
    starts_vowel = sj[:1] == IEUNG
    ends_cons = bool(bj) and JONG_A <= bj[-1] <= JONG_Z
    if starts_vowel and ends_cons:
        moved = bj[-1]
        # 종성 자모를 같은 소리의 초성 자모로 바꾼다 (ᆷ U+11B7 → ᄆ U+1106)
        pair = {"ᆨ": "ᄀ", "ᆫ": "ᄂ", "ᆮ": "ᄃ", "ᆯ": "ᄅ", "ᆷ": "ᄆ", "ᆸ": "ᄇ", "ᆺ": "ᄉ",
                "ᆽ": "ᄌ", "ᆾ": "ᄎ", "ᆿ": "ᄏ", "ᇀ": "ᄐ", "ᇁ": "ᄑ", "ᇂ": "ᄒ",
                "ᆩ": "ᄁ", "ᆻ": "ᄊ", "ᇫ": "ᅀ", "ᇰ": "ᅌ", "ᇦ": "ᄫ"}
        if moved in pair:
            return nfc(bj[:-1] + pair[moved] + sj[1:])
    return nfc(bj + sj)


def pick_particle(modern_part, body):
    """현대어 조사에 맞는 중세어 꼴을 고른다. rule 이 들어맞는 것 가운데 첫째."""
    for form, rule, name in PARTICLES.get(modern_part, []):
        if fits(rule, body):
            return form, name
    return None, None


def word(tok):
    """어절 하나를 중세국어 표기로 돌린다. 못 하면 원문 그대로."""
    t = detone(tok)

    # 1) 통째로 사전에 있나
    if t in REV:
        return REV[t][0], "사전"

    # 2) 체언 + 조사
    for key in PART_KEYS:
        if not t.endswith(key) or len(t) <= len(key):
            continue
        body = t[:-len(key)]
        if body not in REV:
            continue
        mk_body = REV[body][0]
        form, _ = pick_particle(key, mk_body)
        if form is None:
            continue
        return join(mk_body, form), "체언+조사"

    # 3) 용언 어간 + 어미
    for mod_end, mk_end in VERB_ENDINGS:
        if not t.endswith(mod_end) or len(t) <= len(mod_end):
            continue
        stem = t[:-len(mod_end)]
        for cand in (stem + "다", stem):          # 사전에는 기본형(-다)으로 실려 있다
            if cand not in REV:
                continue
            mk = REV[cand][0]
            mk_stem = mk[:-1] if mk.endswith("다") and len(mk) > 1 else mk
            return join(mk_stem, mk_end), "용언+어미"

    # 4) 어간만 아는 경우 (어미를 못 가림)
    for i in range(len(t), 1, -1):
        if i >= 2 and t[:i] in REV:      # 한 글자만 맞는 것은 거의 잡음이라 버린다
            return REV[t[:i]][0] + t[i:], "어간만"

    return tok, "그대로"


PUNCT = re.compile(r"([\s.,·:;!?()\[\]{}「」『』〈〉《》\"']+)")


def convert(text):
    out, how = [], []
    for piece in PUNCT.split(text):
        if not piece or PUNCT.fullmatch(piece):
            out.append(piece)
            continue
        w, h = word(piece)
        out.append(w)
        how.append(h)
    return "".join(out), how


def chars(s):
    return Counter(c for c in re.sub(r"\s+", "", detone(s)))


def f1(pred, gold):
    p, g = chars(pred), chars(gold)
    hit = sum((p & g).values())
    if not hit:
        return 0.0
    pr, rc = hit / max(1, sum(p.values())), hit / max(1, sum(g.values()))
    return 2 * pr * rc / (pr + rc)


def evaluate(show=0):
    """용비어천가 대역을 거꾸로 쓴다. 현대어를 넣어 원문 중세어가 나오는지 본다."""
    doc = json.load(open(os.path.join(ROOT, "corpus", "용비어천가.json"), encoding="utf-8"))
    pairs = [(u["id"], " ".join(u["mk"]), " ".join(u["modern"]))
             for u in doc["units"] if u.get("modern")]
    tot = hitn = 0
    f1s, how = [], Counter()
    rows = []
    for uid, mk, mo in pairs:
        gold = set(x for x in PUNCT.split(detone(mk)) if x and not PUNCT.fullmatch(x))
        pred, hs = convert(mo)
        how.update(hs)
        for w in (x for x in PUNCT.split(pred) if x and not PUNCT.fullmatch(x)):
            tot += 1
            if detone(w) in gold:
                hitn += 1
        f1s.append(f1(pred, mk))
        rows.append((uid, mo, pred, detone(mk), f1s[-1]))

    n = len(pairs)
    print(f"대역이 있는 장 {n}개 · 만든 어절 {tot}개\n")
    print(f"  어절 적중률  {hitn / tot * 100:5.1f}%   ({hitn}/{tot})")
    print(f"  글자 겹침    {sum(f1s) / n * 100:5.1f}%   (장별 F1 평균)")
    done = sum(v for k, v in how.items() if k != "그대로")
    print(f"  바꾼 비율    {done / max(1, sum(how.values())) * 100:5.1f}%")
    print("\n  만든 방법:", ", ".join(f"{k} {v}" for k, v in how.most_common()))

    best, worst = max(rows, key=lambda r: r[4]), min(rows, key=lambda r: r[4])
    for label, r in (("가장 잘된 장", best), ("가장 안된 장", worst)):
        print(f"\n  {label} {r[0]} (F1 {r[4]*100:.0f}%)")
        print(f"    현대어 {r[1][:58]}")
        print(f"    만듦   {r[2][:58]}")
        print(f"    원문   {r[3][:58]}")
    if show:
        print("\n" + "─" * 60)
        for uid, mo, pred, mk, s in rows[:show]:
            print(f"\n{uid}  (F1 {s*100:.0f}%)")
            print(f"  현대어 {mo}")
            print(f"  만듦   {pred}")
            print(f"  원문   {mk}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--eval" in sys.argv:
        k = 0
        for i, a in enumerate(sys.argv):
            if a == "--show" and i + 1 < len(sys.argv):
                k = int(sys.argv[i + 1])
        evaluate(k)
    elif args:
        text = " ".join(args)
        pred, how = convert(text)
        print(f"  현대어  {text}")
        print(f"  중세어  {pred}")
        print(f"  방법    {', '.join(f'{k} {v}' for k, v in Counter(how).most_common())}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
