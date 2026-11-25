"""용비어천가의 원문↔현대어 대역으로 번역이 얼마나 맞는지 잰다.

용비어천가는 장마다 중세국어와 현대어가 나란히 있다. 이것을 정답으로 삼아
지금 가진 도구(표기 변환 + 형태소 분석 + 사전)가 어디까지 가는지 숫자로 본다.

잣대 셋:
  어절 적중률   현대어 정답에 들어 있는 어절을 몇 개나 맞혔나
  글자 겹침     글자 단위로 얼마나 겹치나 (F1)
  설명률        원문 어절 가운데 형태소 분석이 된 비율

번역기가 아직 없으므로, 지금은 '사전에 적힌 현대어로 낱말만 바꾼 것'을 잰다.
이 숫자가 앞으로 번역기를 붙일 때의 바닥값이 된다.

    python3 tools/evaluate.py            # 숫자만
    python3 tools/evaluate.py --show 5   # 실제로 어떻게 옮겼는지 몇 장 보여 줌
"""
import json, os, re, sys, unicodedata
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)

import analyze as A   # 형태소 분석기를 그대로 가져다 쓴다

TONE = "〮〯"
detone = lambda s: unicodedata.normalize("NFC", "".join(c for c in (s or "") if c not in TONE))
PUNCT = re.compile(r"[\s.,·:;!?()\[\]{}「」『』〈〉《》\"']+")

# 표제어 → 현대어 (사전에 적힌 것)
MODERN = {}
for e in A.LEX:
    mods = e.get("modern")
    if not mods:
        continue
    for k in {detone(e["headword"])} | {detone(s.get("written", "")) for s in e["senses"]}:
        k = k.strip("-")
        if k:
            MODERN.setdefault(k, mods[0])


def render(tok):
    """한 어절을 현대어 쪽으로 옮겨 본다. 못 옮기면 원문 그대로."""
    t = detone(tok)
    if t in MODERN:
        return MODERN[t], "사전"
    a = A.analyze(tok)
    if a:
        stem = a["stem"]
        base = MODERN.get(stem) or MODERN.get(a["head"]) or stem
        # 용언이면 '-다' 를 떼고 어미를 붙여 둔다 (아직 활용은 못 함)
        if a.get("endings"):
            if base.endswith("다") and len(base) > 1:
                base = base[:-1]
            return base + "".join(a["endings"]), "분석"
        return base, "분석"
    return tok, "그대로"


def chars(s):
    return Counter(c for c in re.sub(r"\s+", "", s))


def f1(pred, gold):
    p, g = chars(pred), chars(gold)
    hit = sum((p & g).values())
    if not hit:
        return 0.0
    prec, rec = hit / max(1, sum(p.values())), hit / max(1, sum(g.values()))
    return 2 * prec * rec / (prec + rec)


def main():
    doc = json.load(open(os.path.join(ROOT, "corpus", "용비어천가.json"), encoding="utf-8"))
    pairs = [(u, " ".join(u["mk"]), " ".join(u["modern"]))
             for u in doc["units"] if u.get("modern")]
    if not pairs:
        print("대역이 있는 장이 없어요.")
        return 1

    tot_tok = hit_tok = 0
    f1s, how = [], Counter()
    rows = []
    for u, mk, mo in pairs:
        gold = set(PUNCT.split(mo)) - {""}
        out = []
        for tok in PUNCT.split(mk):
            if not tok:
                continue
            r, kind = render(tok)
            how[kind] += 1
            out.append(r)
            tot_tok += 1
            if r in gold:
                hit_tok += 1
        pred = " ".join(out)
        f1s.append(f1(pred, mo))
        rows.append((u["id"], mk, pred, mo, f1s[-1]))

    n = len(pairs)
    print(f"대역이 있는 장 {n}개 · 어절 {tot_tok}개\n")
    print(f"  어절 적중률  {hit_tok / tot_tok * 100:5.1f}%   ({hit_tok}/{tot_tok})")
    print(f"  글자 겹침    {sum(f1s) / n * 100:5.1f}%   (장별 F1 평균)")
    print(f"  설명률       {(how['사전'] + how['분석']) / tot_tok * 100:5.1f}%")
    print("\n  옮긴 방법:", ", ".join(f"{k} {v}" for k, v in how.most_common()))

    best = max(rows, key=lambda r: r[4])
    worst = min(rows, key=lambda r: r[4])
    print(f"\n  가장 잘된 장 {best[0]} (F1 {best[4]*100:.0f}%)")
    print(f"    원문 {best[1][:60]}")
    print(f"    옮김 {best[2][:60]}")
    print(f"    정답 {best[3][:60]}")
    print(f"\n  가장 안된 장 {worst[0]} (F1 {worst[4]*100:.0f}%)")
    print(f"    원문 {worst[1][:60]}")
    print(f"    옮김 {worst[2][:60]}")
    print(f"    정답 {worst[3][:60]}")

    k = 0
    for i, a in enumerate(sys.argv):
        if a == "--show" and i + 1 < len(sys.argv):
            k = int(sys.argv[i + 1])
    if k:
        print("\n" + "─" * 60)
        for rid, mk, pred, mo, s in rows[:k]:
            print(f"\n{rid}  (F1 {s*100:.0f}%)")
            print(f"  원문 {mk}")
            print(f"  옮김 {pred}")
            print(f"  정답 {mo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
