"""말뭉치와 사전을 맞대어 본다.

둘을 한다.
  1) 사전 표제어가 문헌 어디에 실제로 쓰였는지 찾아 용례를 붙인다 (corpus/attestations.json)
  2) 말뭉치에는 나오는데 사전에 없는 어절을 뽑는다 — 어휘를 늘릴 실마리 (corpus/unknown.json)

방점은 비교할 때만 떼고, 저장할 때는 원문 그대로 둔다.
"""
import json, os, re, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
COR = os.path.join(ROOT, "corpus")
TONE = "〮〯"
detone = lambda s: "".join(c for c in s if c not in TONE)
# 한자·한글 아닌 것 떼기 (조사 비교를 위해 구두점만 제거)
PUNCT = re.compile(r"[​\s.,·:;!?()\[\]{}「」『』〈〉《》\"'ㆍ]+")

LEX = json.load(open(os.path.join(ROOT, "data", "lexicon.json"), encoding="utf-8"))
VERBAL = {"Verb", "Adjective"}

HEADS = {}
for e in LEX:
    poses = {s["pos"] for s in e["senses"]}
    forms = {detone(e["headword"])} | {detone(s["written"]) for s in e["senses"] if s.get("written")}
    for k in forms:
        k = k.strip("-")
        if len(k) >= 2:
            HEADS.setdefault(k, e["headword"])
        # 용언은 '-다' 를 뗀 어간도 올린다. ᄒᆞ다 → ᄒᆞ 라야 ᄒᆞ시니·ᄒᆞᆫ 을 알아봄
        if poses & VERBAL and k.endswith("다") and len(k) > 1:
            stem = k[:-1]
            if stem:
                HEADS.setdefault(stem, e["headword"])

docs = []
for f in sorted(os.listdir(COR)):
    if f.endswith(".json") and not f.startswith(".") \
            and f not in ("index.json", "attestations.json", "unknown.json"):
        docs.append(json.load(open(os.path.join(COR, f), encoding="utf-8")))

def longest_head(tok):
    """어절 앞에서부터 가장 길게 맞는 표제어를 찾는다.
    중세국어는 교착어라 '어간 + 조사/어미' 꼴이므로 어절 앞쪽만 본다.
    낱말 가운데서 맞는 것(ᄆᆞᆯ쓰미 안의 ᄆᆞᆯ)은 잡지 않는다."""
    for n in range(len(tok), 1, -1):
        if tok[:n] in HEADS:
            return tok[:n]
    return None


attest, tokens, matched = {}, Counter(), Counter()
for d in docs:
    for u in d["units"]:
        for line in u["mk"]:
            for raw_tok in PUNCT.split(line):
                if not raw_tok:
                    continue
                tok = detone(raw_tok)
                tokens[tok] += 1
                key = longest_head(tok)
                if not key:
                    continue
                matched[tok] += 1
                head = HEADS[key]
                attest.setdefault(head, [])
                if len(attest[head]) < 5:
                    attest[head].append({
                        "work": d["work"], "unit": u["id"],
                        "token": raw_tok, "line": line})

# 사전으로 설명되지 않는 어절
unknown = Counter({t: n for t, n in tokens.items() if t not in matched})

json.dump(attest, open(os.path.join(COR, "attestations.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
json.dump(unknown.most_common(), open(os.path.join(COR, "unknown.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print(f"사전 표제어 {len(LEX)}개 중 문헌에서 찾은 것 {len(attest)}개")
print(f"말뭉치 어절 {sum(tokens.values())}개 (서로 다른 꼴 {len(tokens)}개)")
print(f"사전에 없는 꼴 {len(unknown)}개 — corpus/unknown.json")
print(f"어절 가운데 사전으로 설명된 것 {sum(matched.values())}개 "
      f"({sum(matched.values()) / max(1, sum(tokens.values())) * 100:.0f}%)")
print("\n문헌에서 찾은 표제어 (용례와 함께):")
for h, v in sorted(attest.items(), key=lambda x: -len(x[1]))[:8]:
    print(f"  {h:<10} {len(v)}곳  예: {v[0]['token']}  <{v[0]['work']} {v[0]['unit']}>")
print("\n사전에 없고 자주 나오는 꼴:")
for t, n in unknown.most_common(15):
    print(f"  {t:<14} {n}회")
