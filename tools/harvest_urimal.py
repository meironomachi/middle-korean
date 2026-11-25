"""우리말샘(국립국어원)에서 옛말 표제어를 받아 모은다.

인증키는 Supabase 비밀값(URIMALSAEM_KEY)에만 있고, 중계 함수(urimalsaem)를 거쳐 부른다.
키가 이 저장소에도, 이 컴퓨터에도 남지 않는다.

API 는 검색어(q)가 꼭 있어야 하고 한 검색어당 start 는 1000까지만 간다.
그래서 음절을 하나씩 바꿔 가며 '그 글자로 시작하는 옛말'을 훑는다.

    python3 tools/harvest_urimal.py            # 받기 (이어받기 됨)
    python3 tools/harvest_urimal.py --status   # 어디까지 받았는지
"""
import json, os, sys, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "corpus", ".urimal")
os.makedirs(OUT, exist_ok=True)
RAW = os.path.join(OUT, "raw.json")
DONE = os.path.join(OUT, "done.json")

FN = "https://eonixnwmqpiktmcaeznf.supabase.co/functions/v1/urimalsaem"
ANON = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVvbml4bndtcXBpa3RtY2Flem5m"
        "Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI3MjU3OTMsImV4cCI6MjEwODMwMTc5M30.2N_5RvUGwQUrBYEwq2EvuAoYTqa8faA9bWf2ZdDmB2U")

NUM = 100          # 한 번에 받는 건수 (API 상한)
# start 는 '몇 번째 자료부터'가 아니라 '몇 쪽째'다.
# num=100, start=2 가 101~200번째를 준다. 확인해 보고 알아냄
MAX_PAGE = 1000
GAP = 0.4


def call(payload, tries=5):
    data = json.dumps(payload).encode()
    for i in range(tries):
        req = urllib.request.Request(FN, data=data, headers={
            "Authorization": "Bearer " + ANON, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            try:
                body = json.load(e)
            except Exception:
                body = {"error": e.read()[:200].decode("utf-8", "replace")}
            if i == tries - 1:
                return body
            time.sleep(5 * (2 ** i))
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(5 * (2 ** i))


def items(d):
    ch = d.get("channel") or {}
    it = ch.get("item") or []
    return (it if isinstance(it, list) else [it]), int(ch.get("total") or 0)


def sweep(q):
    """'q 로 시작하는 옛말' 을 끝까지 훑는다. (총건수, 받은 것들)"""
    got, page, total = [], 1, None
    while page <= MAX_PAGE:
        d = call({"q": q, "method": "start", "advanced": "y", "type3": "ancient",
                  "num": NUM, "start": page})
        if "error" in d:
            print(f"    '{q}' {page}쪽 오류: {str(d['error'])[:80]}", flush=True)
            break
        batch, total = items(d)
        got += batch
        if len(batch) < NUM or len(got) >= (total or 0):
            break
        page += 1
        time.sleep(GAP)
    return total or 0, got


# 훑을 검색어: 현대 한글 음절의 첫 자모 + 옛한글에 흔한 머리글자
SEEDS = [chr(c) for c in range(0xAC00, 0xD7A4, 28 * 21)]      # 가 갸 거 겨 …  (초성 19 × 중성 21)
SEEDS = sorted(set(SEEDS))
SEEDS += ["ᄀ", "ᄂ", "ᄃ", "ᄅ", "ᄆ", "ᄇ", "ᄉ", "ᄋ", "ᄌ", "ᄎ", "ᄏ", "ᄐ", "ᄑ", "ᄒ",
          "ᄠ", "ᄡ", "ᄢ", "ᄣ", "ᄭ", "ᄯ", "ᄲ", "ᄊ", "ᅀ", "ᅌ", "ᅙ", "ᄫ", "-"]


def main():
    raw = json.load(open(RAW, encoding="utf-8")) if os.path.exists(RAW) else {}
    done = set(json.load(open(DONE, encoding="utf-8"))) if os.path.exists(DONE) else set()
    todo = [s for s in SEEDS if s not in done]
    print(f"훑을 머리글자 {len(todo)}개 (이미 {len(done)}개 끝남, 모은 항목 {len(raw)}개)")

    for i, q in enumerate(todo, 1):
        total, got = sweep(q)
        new = 0
        for it in got:
            w = it.get("word")
            sense = it.get("sense")
            sense = sense if isinstance(sense, list) else [sense]
            for s in sense:
                if not s:
                    continue
                k = f"{w}::{s.get('sense_no') or s.get('definition', '')[:30]}"
                if k not in raw:
                    raw[k] = {"word": w, **{x: s.get(x) for x in
                              ("definition", "pos", "type", "sense_no", "link", "cat") if s.get(x)}}
                    new += 1
        done.add(q)
        json.dump(raw, open(RAW, "w", encoding="utf-8"), ensure_ascii=False)
        json.dump(sorted(done), open(DONE, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"  [{i}/{len(todo)}] '{q}' 총 {total:>5} · 받음 {len(got):>4} · 새로 {new:>4} "
              f"(누적 {len(raw)})", flush=True)
        time.sleep(GAP)

    print(f"\n끝. 뜻풀이 {len(raw)}개")


if __name__ == "__main__":
    if "--status" in sys.argv:
        raw = json.load(open(RAW, encoding="utf-8")) if os.path.exists(RAW) else {}
        done = json.load(open(DONE, encoding="utf-8")) if os.path.exists(DONE) else []
        print(f"머리글자 {len(done)}/{len(SEEDS)} 끝남 · 뜻풀이 {len(raw)}개")
    else:
        main()
