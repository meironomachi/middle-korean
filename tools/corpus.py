"""위키문헌에서 중세국어 문헌 원문을 받아 말뭉치로 만든다.

세 문헌의 위키 문법 구조가 서로 달라 각각 따로 읽는다.
  용비어천가    ==제N장== 아래 한문 / 중세국어 / 현대어 가 나란히 있음 → 대역 말뭉치
  월인천강지곡  {{더크게|…}} 줄에 본문, {{*|漢字}} 로 한자를 달아 둠
  소학언해 권1  한문 원문과 언해가 줄글로 이어짐. [ ] 안은 협주

방점(〮 거성, 〯 상성)은 지우지 않고 그대로 둔다. 성조 정보라서.

    python3 tools/corpus.py          # 받아서 corpus/ 에 저장
    python3 tools/corpus.py --stats  # 저장된 말뭉치 통계만
"""
import json, os, re, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
OUT = os.path.join(ROOT, "corpus")
API = "https://ko.wikisource.org/w/api.php"
UA = "meiro-mk-dict/1.0 (dictionary compilation; non-commercial)"

OLD = re.compile(r"[ᄀ-ᇿꥠ-꥿ힰ-퟿]")
TONE = "〮〯"

WORKS = {
    "용비어천가": {"year": 1447, "note": "한글로 간행된 최초의 문헌. 125장"},
    "월인천강지곡": {"year": 1447, "note": "세종이 지은 찬불가. 상권"},
    "소학언해/권1": {"year": 1587, "note": "소학을 우리말로 옮긴 책. 권1"},
}


def fetch(titles):
    data = urllib.parse.urlencode({
        "action": "query", "titles": "|".join(titles), "prop": "revisions",
        "rvprop": "content", "rvslots": "main", "format": "json", "formatversion": "2"}).encode()
    for i in range(6):
        try:
            req = urllib.request.Request(API, data=data, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90) as r:
                d = json.load(r)
            return {p["title"]: p["revisions"][0]["slots"]["main"]["content"]
                    for p in d.get("query", {}).get("pages", []) if "revisions" in p}
        except Exception as e:
            if i == 5:
                raise
            back = min(240, 20 * (2 ** i))
            print(f"  {getattr(e, 'code', type(e).__name__)} — {back}초 쉬고 재시도", flush=True)
            time.sleep(back)


def clean(s, keep_hanja=False):
    """위키 문법을 걷어내고 본문만 남긴다. 방점은 그대로 둔다."""
    s = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>", "", s, flags=re.S)
    s = re.sub(r"\{\{\*\|([^}]*)\}\}", r"\1" if keep_hanja else "", s)   # 한자 루비
    s = re.sub(r"\{\{(?:옛한글 인라인|더크게|첫가끝|큰글씨)\|", "", s)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"\}\}", "", s)
    s = re.sub(r"\[\[[^\]|]*\|([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"</?[^>]+>", " ", s)
    s = s.replace("'''", "").replace("''", "")
    return re.sub(r"[ \t]+", " ", s).strip()


def split_lines(block):
    """<br> 로 갈린 줄을 나눈다."""
    parts = re.split(r"<br\s*/?>|\n{2,}", block)
    return [x for x in (clean(p) for p in parts) if x]


def parse_yongbi(w):
    units = []
    for m in re.finditer(r"^==\s*제(\d+)장\s*==\s*$(.*?)(?=^==\s*제\d+장|\Z)", w, re.S | re.M):
        no, body = int(m.group(1)), m.group(2)
        sec = {}
        for s in re.finditer(r"^===\s*([^=\n]+?)\s*===\s*$(.*?)(?=^===|\Z)", body, re.S | re.M):
            sec[s.group(1).strip()] = s.group(2)
        mk = split_lines(sec.get("중세국어", ""))
        if not mk:
            continue
        u = {"id": f"제{no}장", "n": no, "mk": mk}
        mo = split_lines(sec.get("현대어", ""))
        if mo:
            u["modern"] = mo
        han = sec.get("한문", "")
        rb = re.findall(r"\{\{윗주\|([^|}]*)\|([^}]*)\}\}", han)
        if rb:
            u["hanmun"] = [a.strip() for a, _ in rb]
            u["hanmun_reading"] = [b.strip() for _, b in rb]
        units.append(u)
    return units


PAGES_TAG = re.compile(r'<pages\s+index="([^"]+)"\s+from=(\d+)\s+to=(\d+)')


def expand_pages(w, title):
    """<pages index="X.pdf" from=a to=b /> 는 '페이지:X.pdf/N' 문서에서 본문을 끌어오는 틀.
    API 는 이걸 펼쳐 주지 않으므로 해당 쪽 문서를 직접 받아 붙인다."""
    spans = PAGES_TAG.findall(w)
    if not spans:
        return w
    titles = []
    for idx, a, b in spans:
        titles += [f"페이지:{idx}/{n}" for n in range(int(a), int(b) + 1)]
    print(f"    {title}: 쪽 문서 {len(titles)}개 받는 중…", flush=True)
    got = {}
    for i in range(0, len(titles), 50):
        got.update(fetch(titles[i:i + 50]))
        time.sleep(1)
    # 쪽 번호 순서대로 이어 붙임
    def key(t):
        m = re.search(r"/(\d+)$", t)
        return int(m.group(1)) if m else 0
    body = "\n\n".join(got[t] for t in sorted(got, key=key))
    print(f"    받은 쪽 {len(got)}/{len(titles)}", flush=True)
    return w + "\n\n" + body


def parse_worin(w):
    """:{{더크게|끠其삼三…}} 가 '기(其) N' 번호, 그 뒤 {{더크게|…}} 들이 본문."""
    units, cur = [], None
    for line in w.splitlines():
        if not line.strip().startswith((":{{더크게", "{{더크게")):
            continue
        is_no = line.strip().startswith(":")
        txt = clean(line)
        if not txt:
            continue
        if is_no:
            if cur and cur["mk"]:
                units.append(cur)
            cur = {"id": txt, "mk": []}
        elif cur is not None:
            cur["mk"].append(txt)
    if cur and cur["mk"]:
        units.append(cur)
    for i, u in enumerate(units, 1):
        u["n"] = i
    return units


def parse_sohak(w):
    """== 편 == / === 장 === 아래 줄글. '○' 로 토막이 나뉨."""
    units = []
    part = chap = None
    for blk in re.split(r"\n{2,}", w):
        h2 = re.match(r"^==\s*([^=\n]+?)\s*==\s*$", blk.strip())
        h3 = re.match(r"^===\s*([^=\n]+?)\s*===\s*$", blk.strip())
        if h2:
            part = clean(h2.group(1)); continue
        if h3:
            chap = clean(h3.group(1)); continue
        t = clean(blk)
        if not t or not OLD.search(t):
            continue
        u = {"id": f"{chap or part or '권1'}-{len(units) + 1}", "n": len(units) + 1, "mk": [t]}
        if chap:
            u["chapter"] = chap
        units.append(u)
    return units


PARSERS = {"용비어천가": parse_yongbi, "월인천강지곡": parse_worin, "소학언해/권1": parse_sohak}


def stats(doc):
    mk = [l for u in doc["units"] for l in u["mk"]]
    words = [t for l in mk for t in l.split()]
    return {
        "units": len(doc["units"]),
        "lines": len(mk),
        "words": len(words),
        "with_modern": sum(1 for u in doc["units"] if u.get("modern")),
        "tone_marks": sum(l.count(c) for l in mk for c in TONE),
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    cache = os.path.join(OUT, ".raw.json")
    raw = json.load(open(cache, encoding="utf-8")) if os.path.exists(cache) else {}
    need = [t for t in WORKS if t not in raw]
    if need:
        print(f"위키문헌에서 {len(need)}개 받는 중…")
        raw.update(fetch(need))
        json.dump(raw, open(cache, "w", encoding="utf-8"), ensure_ascii=False)

    index = []
    for title, meta in WORKS.items():
        if title not in raw:
            print(f"  {title}: 못 받음"); continue
        src = raw[title]
        if PAGES_TAG.search(src):
            key = title + "::pages"
            if key not in raw:
                raw[key] = expand_pages(src, title)
                json.dump(raw, open(cache, "w", encoding="utf-8"), ensure_ascii=False)
            src = raw[key]
        units = PARSERS[title](src)
        doc = {
            "work": title, "year": meta["year"], "note": meta["note"],
            "source": f"https://ko.wikisource.org/wiki/{urllib.parse.quote(title)}",
            "license": "CC BY-SA (위키문헌). 원문 자체는 저작권 소멸",
            "note_tone": "방점 〮(거성) 〯(상성) 을 원문 그대로 둠",
            "units": units,
        }
        name = title.replace("/", "_") + ".json"
        json.dump(doc, open(os.path.join(OUT, name), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        s = stats(doc)
        index.append({"work": title, "file": name, "year": meta["year"], **s})
        print(f"  {title:<14} 단락 {s['units']:>4} · 줄 {s['lines']:>4} · 어절 {s['words']:>6} "
              f"· 현대어 있는 단락 {s['with_modern']:>4} · 방점 {s['tone_marks']:>6}")

    json.dump(index, open(os.path.join(OUT, "index.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\ncorpus/ 에 {len(index)}개 문헌 저장")


if __name__ == "__main__":
    if "--stats" in sys.argv:
        for e in json.load(open(os.path.join(OUT, "index.json"), encoding="utf-8")):
            print(e)
    else:
        main()
