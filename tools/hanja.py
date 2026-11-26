"""유니코드 Unihan 에서 한자의 한국 음독을 뽑아 data/hanja.json 을 만든다.

말뭉치 어절의 29%에 한자가 들어 있는데, 분석기가 한자를 모르니 그런 어절은
거의 다 못 쪼갠다. 못 쪼갠 어절의 49%가 한자가 든 것이다.

한자 자체는 체언처럼 쓰이므로(王ᄋᆞᆫ = 王 + ᄋᆞᆫ), 음독만 알면 쪼갤 수 있다.

    python3 tools/hanja.py <Unihan 디렉터리>

Unihan.zip 은 https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip 에서 받는다.
라이선스는 Unicode License V3 — 고지를 함께 두면 재배포할 수 있다.
"""
import json, os, re, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
HAN = re.compile(r"[㐀-䶿一-鿿豈-﫿]")


def read_field(path, want):
    """Unihan 파일에서 U+XXXX<TAB>필드<TAB>값 꼴을 읽는다."""
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or "\t" not in line:
                continue
            cp, field, val = (line.rstrip("\n").split("\t") + ["", ""])[:3]
            if field != want:
                continue
            out[chr(int(cp[2:], 16))] = val
    return out


def corpus_chars():
    """말뭉치에 실제로 나오는 한자. 쓰지 않는 글자까지 싣지 않으려고 센다."""
    cnt = Counter()
    cor = os.path.join(ROOT, "corpus")
    for name in sorted(os.listdir(cor)):
        if not name.endswith(".json"):
            continue
        doc = json.load(open(os.path.join(cor, name), encoding="utf-8"))
        if not isinstance(doc, dict) or "units" not in doc:
            continue
        for u in doc["units"]:
            for line in u["mk"]:
                cnt.update(c for c in line if HAN.match(c))
            for line in u.get("hanmun", []) or []:
                cnt.update(c for c in line if HAN.match(c))
    return cnt


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "."
    rd = os.path.join(src, "Unihan_Readings.txt")
    if not os.path.exists(rd):
        print(f"{rd} 가 없습니다. Unihan.zip 을 풀어 그 경로를 넘겨 주세요.")
        return 1

    hangul = read_field(rd, "kHangul")        # 현대 한국 음독
    korean = read_field(rd, "kKorean")        # 옛 음독 (로마자)
    define = read_field(rd, "kDefinition")    # 영어 뜻풀이

    used = corpus_chars()
    print(f"Unihan 음독 {len(hangul)}자 · 말뭉치에 나오는 한자 {len(used)}자")

    out = {}
    for ch, val in hangul.items():
        # '온:N 은:N' 처럼 음독 뒤에 출처 표시가 붙는다. 떼어 낸다
        reads = []
        for part in val.split():
            r = part.split(":")[0].strip()
            if r and r not in reads:
                reads.append(r)
        if not reads:
            continue
        # 사이트가 받는 파일이라 작게 둔다. 음은 다 넣고, 뜻은 첫 뜻만 짧게.
        # 옛 음독(kKorean)과 말뭉치 횟수는 통계로만 쓰므로 싣지 않는다.
        e = {"음": reads}
        d = define.get(ch)
        if d:
            e["뜻"] = d.split(";")[0].split(",")[0].strip()[:40]
        out[ch] = e

    # 말뭉치에 나오는 것은 모두 넣고, 그 밖에는 음독이 있는 것만 넣는다.
    # (사이트가 받는 파일이라 너무 키우지 않는다)
    missing = [c for c in used if c not in out]
    doc = {
        "meta": {
            "note": "한자의 한국 음독. 王 → 왕 처럼 읽어 체언으로 다룬다",
            "source": "Unicode Unihan Database (kHangul · kKorean · kDefinition)",
            "source_url": "https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip",
            "license": "Unicode License V3 — 고지를 함께 두면 재배포 가능",
            "license_url": "https://www.unicode.org/license.txt",
            "chars": len(out),
            "in_corpus": sum(1 for c in used if c in out),
            "corpus_chars": len(used),
            "missing_in_corpus": missing,
        },
        "readings": out,
    }
    path = os.path.join(ROOT, "data", "hanja.json")
    json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False,
              separators=(",", ":"))
    size = os.path.getsize(path) / 1024
    print(f"data/hanja.json 에 {len(out)}자 저장 ({size:.0f}KB)")
    print(f"말뭉치 한자 가운데 음독을 찾은 것 {doc['meta']['in_corpus']}/{len(used)}자")
    if missing:
        print(f"음독을 못 찾은 것 {len(missing)}자: {' '.join(missing[:20])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
