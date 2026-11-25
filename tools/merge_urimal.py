"""우리말샘에서 받은 옛말을 사전 파일로 바꾼다.

출처가 달라 라이선스도 다르므로(위키 쪽 CC BY-SA 4.0, 국립국어원 쪽 CC BY-SA 2.0 KR)
한 파일에 섞지 않고 data/lexicon-urimal.json 으로 따로 둔다.

우리말샘 옛말 뜻풀이는 거의 "'…'의 옛말" 꼴이라, 거기서 현대어 대응을 뽑아낸다.
표제어의 붙임표(가각-다)는 형태소 경계 표시라 떼어 낸 꼴도 함께 올린다.
"""
import json, os, re, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
RAW = os.path.join(ROOT, "corpus", ".urimal", "raw.json")
OUT = os.path.join(ROOT, "data", "lexicon-urimal.json")

# "'급하다'의 옛말", "‘뜻’의 옛말" 등에서 현대어를 뽑음
MODERN = re.compile(r"[‘'\"“]([^’'\"”]+)[’'\"”]\s*의\s*옛말")
POS_KO = {
    "명사": "Noun", "동사": "Verb", "형용사": "Adjective", "부사": "Adverb",
    "관형사": "Determiner", "대명사": "Pronoun", "수사": "Numeral", "조사": "Particle",
    "감탄사": "Interjection", "어미": "Suffix", "접사": "Suffix",
    "의존 명사": "Noun", "보조 동사": "Verb", "보조 형용사": "Adjective",
}


def main():
    if not os.path.exists(RAW):
        print("받은 자료가 없어요. 먼저 tools/harvest_urimal.py 를 돌려 주세요.")
        return 1
    raw = json.load(open(RAW, encoding="utf-8"))

    entries, skipped = {}, 0
    for rec in raw.values():
        word = (rec.get("word") or "").strip()
        defn = (rec.get("definition") or "").strip()
        if not word:
            skipped += 1
            continue
        plain = word.replace("-", "").replace("^", "").strip()
        if not plain:
            skipped += 1
            continue

        e = entries.setdefault(plain, {
            "headword": plain, "senses": [], "source": "우리말샘",
        })
        if word != plain and "written" not in e:
            e["written"] = word          # 붙임표로 형태소 경계를 보인 꼴

        sense = {"pos": POS_KO.get(rec.get("pos"), rec.get("pos") or "Unknown")}
        if defn:
            sense["glosses"] = [defn]
        if rec.get("pos"):
            sense["pos_ko"] = rec["pos"]
        e["senses"].append(sense)

        m = MODERN.search(defn)
        if m:
            mod = m.group(1).strip()
            e.setdefault("modern", [])
            if mod and mod not in e["modern"]:
                e["modern"].append(mod)
        if rec.get("link"):
            e.setdefault("link", rec["link"])

    out = sorted(entries.values(), key=lambda x: x["headword"])
    doc = {
        "meta": {
            "title": "우리말샘 옛말",
            "source": "우리말샘 (국립국어원) https://opendict.korean.go.kr",
            "license": "CC BY-SA 2.0 KR",
            "note": "표제어는 우리말샘 표기를 따름. 붙임표(-)는 형태소 경계라 떼어 낸 꼴을 표제어로 삼고 "
                    "원래 표기는 written 에 둠. modern 은 뜻풀이의 \"'…'의 옛말\" 에서 뽑은 현대어",
            "count": len(out),
        },
        "entries": out,
    }
    json.dump(doc, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    pos = Counter(s["pos"] for e in out for s in e["senses"])
    print(f"항목 {len(out)}개 (뜻풀이 {sum(len(e['senses']) for e in out)}개, 건너뜀 {skipped}개)")
    print(f"현대어 대응이 붙은 항목 {sum(1 for e in out if e.get('modern'))}개")
    print(f"붙임표 표기가 있는 항목 {sum(1 for e in out if e.get('written'))}개")
    print("품사:", ", ".join(f"{k} {v}" for k, v in pos.most_common(10)))
    print("\n표본:")
    for e in out[:6]:
        print("  ", json.dumps(e, ensure_ascii=False)[:150])
    print(f"\n{OUT} 에 저장")
    return 0


if __name__ == "__main__":
    sys.exit(main())
