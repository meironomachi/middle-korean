"""받아 둔 위키낱말사전 본문에서 중세 한국어(Middle Korean) 부분만 떼어내 사전 항목으로 만든다.

위키 문법을 걷어낼 때 틀이 중첩돼 있으므로 안쪽부터 되풀이해 지운다.
'다른 꼴(alternative form of)' 같은 틀은 그 자체가 뜻풀이라서 따로 글로 바꾼다.
"""
import json, os, re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = json.load(open(os.path.join(HERE, "api", "mk_pages.json"), encoding="utf-8"))

SEC = re.compile(r"^==\s*Middle Korean\s*==\s*$(.*?)(?=^==[^=]|\Z)", re.S | re.M)
SUB = re.compile(r"^===+\s*([^=]+?)\s*=+==\s*$", re.M)
INNER = re.compile(r"\{\{([^{}]*)\}\}")          # 가장 안쪽 틀

POS = {"Noun", "Verb", "Adjective", "Adverb", "Determiner", "Pronoun", "Numeral",
       "Particle", "Suffix", "Prefix", "Interjection", "Conjunction", "Proper noun",
       "Counter", "Postposition", "Syllable", "Root", "Phrase", "Affix",
       # 글자 자체를 다루는 항목들 — 옛 자모와 방점이 여기 들어감
       "Letter", "Symbol", "Ideophone", "Punctuation mark", "Infix", "Classifier"}

# 그 자체가 뜻풀이 구실을 하는 틀
REL = {
    "alternative form of": "다른 꼴", "alt form": "다른 꼴", "altform": "다른 꼴",
    "alt form of": "다른 꼴", "altform of": "다른 꼴", "alternative of": "다른 꼴",
    "okm-idu form of": "이두 표기", "idu form of": "이두 표기",
    "alternative spelling of": "다른 표기", "honorific alternative form of": "높임말",
    "synonym of": "같은 말", "abbreviation of": "준말", "contraction of": "줄어든 꼴",
    "inflection of": "활용형", "obsolete form of": "옛 표기",
}


def args(body):
    """틀 안을 | 로 나눠 위치인자와 이름인자로 가른다."""
    parts = body.split("|")
    name = parts[0].strip()
    pos, kw = [], {}
    for p in parts[1:]:
        if "=" in p:
            k, _, v = p.partition("=")
            kw[k.strip()] = v.strip()
        else:
            pos.append(p.strip())
    return name, pos, kw


def one_template(body):
    """틀 하나를 읽을 수 있는 글로 바꾼다 (없애야 하면 빈 문자열)."""
    name, pos, kw = args(body)
    low = name.lower()
    if low in ("lb", "label", "tlb"):
        return "(" + ", ".join(pos[1:]) + ")" if len(pos) > 1 else ""
    if low in ("n-g", "non-gloss definition", "ng", "gloss", "non-gloss", "nongloss"):
        return pos[0] if pos else ""
    if low == "ko-defn-jamo":                     # 합용병서 등 자모 결합
        return " + ".join(pos) + " 가 합쳐진 자모" if pos else ""
    if low == "ipafont":
        return pos[0] if pos else ""
    if low in ("okm-hanja form of", "hanja form of"):     # 한자로 적은 표기
        tgt = pos[0] if pos else ""
        mean = pos[1] if len(pos) > 1 else ""
        return f"{tgt}의 한자 표기" + (f" — {mean}" if mean else "")
    if low == "place":                                     # 지명·나라 이름
        t = kw.get("t2") or kw.get("t") or ""
        kind = pos[1] if len(pos) > 1 else ""
        return (f"{t} ({kind})" if t and kind else t or kind)
    if low in ("transclude", "tcl"):                        # 다른 문서에서 끌어온 뜻
        return (pos[1] if len(pos) > 1 else pos[0] if pos else "")
    if low in REL:
        tgt = pos[1] if len(pos) > 1 else (pos[0] if pos else "")
        extra = kw.get("pos") or kw.get("from") or ""
        s = f"{tgt}의 {REL[low]}"
        return f"{s} ({extra})" if extra else s
    if low in ("m", "l", "link", "cog", "der", "inh", "bor", "mention"):
        return pos[1] if len(pos) > 1 else (pos[0] if pos else "")
    if low in ("q", "qualifier", "qual"):
        return "(" + ", ".join(pos) + ")" if pos else ""
    return ""                                     # 그 밖의 틀은 버림


def strip_wiki(s):
    for _ in range(8):                            # 중첩 틀을 안쪽부터 걷어냄
        new = INNER.sub(lambda m: one_template(m.group(1)), s)
        if new == s:
            break
        s = new
    s = re.sub(r"\{\{[^}]*\}?\}?", "", s)         # 닫히지 않은 찌꺼기
    s = re.sub(r"\[\[[^\]|]*\|([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r"\1", s)
    s = s.replace("'''", "").replace("''", "")
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" ,;:")


def subsections(body):
    out, marks = {}, list(SUB.finditer(body))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        out.setdefault(m.group(1).strip(), []).append(body[m.end():end])
    return out


def defs_of(chunk):
    out = []
    for line in chunk.splitlines():
        if line.startswith("#") and not line.startswith(("#:", "#*", "##")):
            g = strip_wiki(line.lstrip("# ").strip())
            if g and g not in out:
                out.append(g)
    return out


HEAD_T = re.compile(r"\{\{(?:head\|okm|okm-[a-z ]+)([^{}]*)\}\}")


def head_info(chunk):
    """표제어 틀에서 성조 찍힌 표기(head=)와 예일식 로마자(tr=)를 꺼낸다."""
    form = yale = None
    for m in HEAD_T.finditer(chunk):
        _, pos, kw = args("x" + m.group(1))
        form = form or kw.get("head")
        yale = yale or kw.get("tr")
        if not form:
            for p in pos:
                if p and re.search(r"[가-힣ᄀ-ᇿꥠ-꥿ힰ-퟿]", p):
                    form = p
                    break
    return form, yale


def descendants(body):
    out = []
    for line in body.splitlines():
        if not line.lstrip().startswith("*"):
            continue
        if "desc|ko|" in line or re.search(r"\*\s*Korean", line):
            for a, b in re.findall(r"\{\{desc\|ko\|([^|}]+)|\[\[([^\]|]+)", line):
                t = (a or b).strip()
                if t and t != "Korean" and t not in out:
                    out.append(t)
    return out


def attestations(body):
    out, seen = [], set()
    for m in re.finditer(r"\{\{[^{}]*?(?:year|work)=[^{}]*?\}\}", body):
        y = re.search(r"\|year=(\d{3,4})", m.group(0))
        w = re.search(r"\|work=([^|}]+)", m.group(0))
        rec = (w.group(1).strip() if w else None, int(y.group(1)) if y else None)
        if rec != (None, None) and rec not in seen:
            seen.add(rec)
            out.append({"work": rec[0], "year": rec[1]})
    return out


entries, skipped = [], []
for title, text in PAGES.items():
    m = SEC.search(text)
    if not m:
        skipped.append((title, "절 없음"))
        continue
    body = m.group(1)
    senses = []
    for name, chunks in subsections(body).items():
        base = name.split()[0] if name.split() else ""
        if name not in POS and base not in POS:
            continue
        for ch in chunks:
            ds = defs_of(ch)
            if not ds:
                continue
            form, yale = head_info(ch)
            s = {"pos": name, "glosses": ds}
            if yale:
                s["yale"] = yale
            if form and form != title:
                s["written"] = form          # 방점(〮〯)까지 찍힌 표기
            senses.append(s)
    if not senses:
        skipped.append((title, "뜻풀이 없음"))
        continue
    e = {"headword": title, "senses": senses}
    d = descendants(body)
    if d:
        e["modern"] = d
    a = attestations(body)
    if a:
        e["attested"] = a[:4]
    entries.append(e)

entries.sort(key=lambda x: x["headword"])
json.dump(entries, open(os.path.join(HERE, "api", "mk_entries.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print(f"항목 {len(entries)}개 / 건너뜀 {len(skipped)}개")
c = Counter(s["pos"] for e in entries for s in e["senses"])
print("품사:", ", ".join(f"{k} {v}" for k, v in c.most_common()))
print(f"현대어 연결 {sum(1 for e in entries if e.get('modern'))}개 · "
      f"예일식 표기 {sum(1 for e in entries for s in e['senses'] if s.get('yale'))}개 · "
      f"방점 표기 {sum(1 for e in entries for s in e['senses'] if s.get('written'))}개 · "
      f"출전 {sum(1 for e in entries if e.get('attested'))}개")
print("\n표본:")
for t in ["-ᄉᆞᆸ-", "-를", "가다", "ᄒᆞ다"]:
    for e in entries:
        if e["headword"] == t:
            print(" ", json.dumps(e, ensure_ascii=False)[:300])
            break
if skipped:
    print("\n건너뛴 까닭:", Counter(r for _, r in skipped).most_common())
    print("표본:", [t for t, _ in skipped[:12]])
