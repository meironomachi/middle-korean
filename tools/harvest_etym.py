"""위키낱말사전의 현대 한국어 어원란에서 중세국어 꼴을 거둔다.

중세국어 표제어는 969개로 이미 다 받았다 (카테고리에 그만큼뿐이다). 그런데
'깊다·없다·듣다' 같은 기본 용언은 그 안에 없다. 현대에도 살아 있는 말이라
중세국어 표제어로는 안 서 있고, **현대 한국어 문서의 어원란**에 적혀 있기 때문이다.

    깊다  ===Etymology===
          {{ko-etym-native|yb|깊다〮|kìphtá}}
                           └ 출전  └ 중세 꼴(방점)  └ 예일 로마자

이 틀 하나가 우리에게 필요한 것을 다 담고 있다. 현대어↔중세어 짝, 방점, 출전까지.
3,300여 문서가 이 틀을 쓴다.

    python3 tools/harvest_etym.py            # 받아서 data/lexicon-etym.json 로
    python3 tools/harvest_etym.py --stats    # 저장된 것 통계만

출처: 영어 위키낱말사전 (CC BY-SA 4.0). 출전 코드표는 Module:ko-etym.
"""
import json, os, re, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
OUT = os.path.join(ROOT, "data", "lexicon-etym.json")
CACHE = os.path.join(ROOT, "data", ".etym-raw.json")
API = "https://en.wiktionary.org/w/api.php"
UA = "meiro-mk-dict/1.0 (dictionary compilation; non-commercial)"

TPL = "Template:ko-etym-native"
OLD = re.compile(r"[ᄀ-ᇿㄱ-㆏가-힣]")
HANGUL_ONLY = re.compile(r"^[ᄀ-ᇿ가-힣〮〯\-]+$")


def api(params, tries=5):
    params.update({"format": "json", "formatversion": "2"})
    data = urllib.parse.urlencode(params).encode()
    for i in range(tries):
        try:
            req = urllib.request.Request(API, data=data, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception as e:
            if i == tries - 1:
                raise
            back = min(120, 15 * (2 ** i))
            print(f"  {getattr(e, 'code', type(e).__name__)} — {back}초 쉬고 다시", flush=True)
            time.sleep(back)


def refs_table():
    """Module:ko-etym 의 출전 코드표. yb → 용비어천가 1447 처럼."""
    d = api({"action": "query", "titles": "Module:ko-etym", "prop": "revisions",
             "rvprop": "content", "rvslots": "main"})
    w = d["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"]
    block = w[w.index("local refs"):]
    block = block[:block.index("\n}")]
    out = {}
    # 한 문헌에 코드가 여럿인 것이 있다. {{"7", "ws", "wi"}, "월인석보…", "okm"}
    # 둘짜리만 받다가 월인석보(ws) 를 통째로 놓쳤었다.
    for codes, desc, lang in re.findall(
            r'\{\{([^{}]*)\},\s*"(.*?)",\s*"(\w+)"\}', block):
        ko = re.findall(r"\{\{lang\|ko\|([^}]*)\}\}", desc)
        name = ""
        if ko:
            m = re.search(r"/\s*([가-힣]+)", ko[-1]) or re.search(r"([가-힣]+)", ko[-1])
            name = m.group(1) if m else ""
        roman = re.search(r"''(.*?)''", desc)
        year = re.search(r"(\d{3,4})\s*$", desc.strip())
        rec = {"work": name or (roman.group(1) if roman else ""),
               "year": year.group(1) if year else "", "lang": lang}
        for part in codes.split(","):                  # '"7", "ws", "wi"' → 7 / ws / wi
            c = part.strip().strip('"').strip()
            if c and not c.isdigit():                  # 맨 앞 숫자는 차례 번호다
                out[c] = rec
    return out


def pages_using_template():
    got, cont = [], {}
    while True:
        p = {"action": "query", "list": "embeddedin", "eititle": TPL,
             "einamespace": "0", "eilimit": "500"}
        p.update(cont)
        d = api(p)
        got += [x["title"] for x in d["query"]["embeddedin"]]
        if "continue" not in d:
            return got
        cont = d["continue"]
        time.sleep(0.4)


def fetch(titles):
    d = api({"action": "query", "titles": "|".join(titles), "prop": "revisions",
             "rvprop": "content", "rvslots": "main"})
    return {p["title"]: p["revisions"][0]["slots"]["main"]["content"]
            for p in d["query"].get("pages", []) if "revisions" in p}


def clean_gloss(t):
    t = re.sub(r"\{\{(?:uxi|ux|ko-usex)\|.*?\}\}", "", t, flags=re.S)
    t = re.sub(r"\{\{(?:l|ko-l|m)\|[^|}]*\|([^|}]*)[^}]*\}\}", r"\1", t)
    t = re.sub(r"\{\{[^{}]*\}\}", "", t)
    # [[lacking#Adjective|lacking]] 처럼 닻이 달린 고리는 보이는 글자만 남긴다
    t = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[\[([^\]|#]*)(?:#[^\]|]*)?\]\]", r"\1", t)
    t = re.sub(r"#[A-Za-z_ ]+\|", "", t)
    t = t.replace("[[", "").replace("]]", "").replace("'''", "").replace("''", "")
    t = re.sub(r"\s+", " ", t).strip(" .,;")
    return t if 1 < len(t) < 120 else ""


def parse(title, wiki, refs):
    """한 문서에서 중세국어 꼴과 뜻을 뽑는다."""
    ko = re.search(r"==Korean==(.*?)(?=\n==[^=]|\Z)", wiki, re.S)
    if not ko:
        return None
    body = ko.group(1)

    forms = []
    for m in re.finditer(r"\{\{ko-etym-native\|([^}]*)\}\}", body):
        args = [a.strip() for a in m.group(1).split("|")]
        pos = [a for a in args if "=" not in a]
        if len(pos) < 2:
            continue
        code, form = pos[0], pos[1]
        yale = pos[2] if len(pos) > 2 else ""
        if not HANGUL_ONLY.match(form):
            continue            # 嫩 처럼 한자로 적힌 고대 표기는 건너뛴다
        ref = refs.get(code, {})
        if not ref:
            continue            # 모르는 출전 코드는 버린다 (무엇인지 밝히지 못하므로)
        if ref.get("lang") != "okm":
            continue            # 중세국어(okm) 출전만. 고대(oko) 는 쓰지 않는다
        f = {"written": form, "yale": yale,
             "src": ref.get("work", code), "year": ref.get("year", "")}
        if f not in forms:
            forms.append(f)
    if not forms:
        return None

    # 품사와 뜻
    senses = []
    for m in re.finditer(r"^===+\s*(Noun|Verb|Adjective|Adverb|Determiner|Numeral|Pronoun|Interjection|Counter|Suffix|Prefix)\s*===+\s*$(.*?)(?=^===|\Z)",
                         body, re.S | re.M):
        pos, chunk = m.group(1), m.group(2)
        for line in re.findall(r"^#\s+(?!\*|:)(.+)$", chunk, re.M):
            g = clean_gloss(line)
            if g:
                senses.append({"pos": pos, "definition": g})
                break
    return {"headword": forms[0]["written"], "modern": [title],
            "forms": forms, "senses": senses or [{"pos": "", "definition": ""}],
            "source": "위키낱말사전 어원란"}


def main():
    if "--stats" in sys.argv:
        d = json.load(open(OUT, encoding="utf-8"))
        print(json.dumps(d["meta"], ensure_ascii=False, indent=1))
        return 0

    refs = refs_table()
    print(f"출전 코드 {len(refs)}개")
    titles = pages_using_template()
    print(f"{TPL} 을 쓰는 문서 {len(titles)}개")

    raw = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
    todo = [t for t in titles if t not in raw]
    for i in range(0, len(todo), 50):
        raw.update(fetch(todo[i:i + 50]))
        if i % 500 == 0:
            json.dump(raw, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"  {min(i + 50, len(todo))}/{len(todo)}", flush=True)
        time.sleep(0.4)
    json.dump(raw, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)

    entries, works = [], {}
    for t in titles:
        if t not in raw:
            continue
        e = parse(t, raw[t], refs)
        if e:
            entries.append(e)
            for f in e["forms"]:
                works[f["src"]] = works.get(f["src"], 0) + 1

    doc = {
        "meta": {
            "note": "현대 한국어 문서의 어원란에서 거둔 중세국어 꼴. 방점과 출전이 함께 있다",
            "source": "영어 위키낱말사전 Template:ko-etym-native",
            "source_url": "https://en.wiktionary.org/wiki/Template:ko-etym-native",
            "license": "CC BY-SA 4.0",
            "entries": len(entries),
            "forms": sum(len(e["forms"]) for e in entries),
            "by_work": dict(sorted(works.items(), key=lambda x: -x[1])),
        },
        "entries": entries,
    }
    json.dump(doc, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\ndata/lexicon-etym.json 에 표제어 {len(entries)}개 · 꼴 {doc['meta']['forms']}개")
    for w, n in list(doc["meta"]["by_work"].items())[:8]:
        print(f"  {w:<14} {n:>5}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
