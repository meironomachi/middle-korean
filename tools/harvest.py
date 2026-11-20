"""en.wiktionary 중세 한국어 표제어와 본문을 받아 모은다.

- 공용 IP라 위키미디어가 속도 제한(429)을 걸기 때문에 간격을 두고 재시도한다.
- 한 번에 50개씩 묶어 받는다 (983개를 낱개로 받으면 983번이지만 묶으면 20번).
- 배치마다 저장하므로 중간에 끊겨도 다시 돌리면 이어서 받는다.
"""
import json, os, time, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "api")
os.makedirs(OUT, exist_ok=True)
LIST_F = os.path.join(OUT, "mk_titles.json")
PAGE_F = os.path.join(OUT, "mk_pages.json")

API = "https://en.wiktionary.org/w/api.php"
UA = "meiro-mk-dict/1.0 (dictionary compilation; non-commercial)"
GAP = 4.0
_last = [0.0]


def get(params, tries=7):
    data = urllib.parse.urlencode(params).encode()
    for i in range(tries):
        wait = GAP - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(API, data=data, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                _last[0] = time.time()
                return json.load(r)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            _last[0] = time.time()
            code = getattr(e, "code", None)
            if i == tries - 1:
                raise
            back = min(300, 15 * (2 ** i))
            print(f"    {code or type(e).__name__} — {back}초 쉬고 재시도", flush=True)
            time.sleep(back)


def category(title):
    out, cont = [], None
    while True:
        p = {"action": "query", "list": "categorymembers", "cmtitle": title,
             "cmlimit": "500", "format": "json", "formatversion": "2"}
        if cont:
            p["cmcontinue"] = cont
        d = get(p)
        out += [m["title"] for m in d.get("query", {}).get("categorymembers", [])]
        print(f"    …{len(out)}개", flush=True)
        cont = d.get("continue", {}).get("cmcontinue")
        if not cont:
            return out


# --- 1단계: 표제어 목록 ---
if os.path.exists(LIST_F):
    titles = json.load(open(LIST_F, encoding="utf-8"))
    print(f"표제어 목록 재사용: {len(titles)}개")
else:
    print("표제어 목록 받는 중…")
    titles = sorted(set(category("Category:Middle Korean lemmas")))
    json.dump(titles, open(LIST_F, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"표제어 {len(titles)}개 저장")

# --- 2단계: 본문 (50개씩, 이어받기) ---
pages = json.load(open(PAGE_F, encoding="utf-8")) if os.path.exists(PAGE_F) else {}
todo = [t for t in titles if t not in pages]
print(f"본문 받을 것 {len(todo)}개 (이미 {len(pages)}개 있음)")

BATCH = 50
for i in range(0, len(todo), BATCH):
    chunk = todo[i:i + BATCH]
    d = get({"action": "query", "titles": "|".join(chunk), "prop": "revisions",
             "rvprop": "content", "rvslots": "main", "format": "json", "formatversion": "2"})
    for pg in d.get("query", {}).get("pages", []):
        if "revisions" in pg:
            pages[pg["title"]] = pg["revisions"][0]["slots"]["main"]["content"]
    json.dump(pages, open(PAGE_F, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"  {min(i + BATCH, len(todo))}/{len(todo)}  (누적 {len(pages)})", flush=True)

print(f"\n완료: 표제어 {len(titles)}개 중 본문 {len(pages)}개")
