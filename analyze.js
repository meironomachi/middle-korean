/* 어절을 '어간/체언 + 조사/어미'로 쪼갠다. tools/analyze.py 를 브라우저로 옮긴 것.
 *
 * 규칙은 파이썬 쪽과 같게 맞춰 두었다. 한쪽을 고치면 다른 쪽도 고쳐야 한다.
 * 사전(lexicon)과 문법(grammar.json)은 사이트가 이미 받아 두므로 그대로 넘겨받는다.
 *
 *   const A = MKAnalyze.build(GRAM, LEX);
 *   A.analyze("ᄒᆞ시니ᅌᅵᆺ고")
 */
(function (global) {
  "use strict";

  var TONE = "〮〯";
  var CHO_A = 0x1100, CHO_Z = 0x115f;    // 초성
  var JUNG_A = 0x1160, JUNG_Z = 0x11a7;  // 중성
  var JONG_A = 0x11a8, JONG_Z = 0x11ff;  // 종성
  var IEUNG = "ᄋ";                  // 초성 ㅇ

  function inRange(ch, a, z) {
    var c = ch.charCodeAt(0);
    return c >= a && c <= z;
  }

  // 방점을 떼고 NFC 로 맞춘다. 조합형(가 U+AC00)과 분해형(가 U+1100 U+1161)이 섞여 있어서다.
  function detone(s) {
    s = String(s == null ? "" : s);
    var out = "";
    for (var i = 0; i < s.length; i++) if (TONE.indexOf(s[i]) < 0) out += s[i];
    return out.normalize("NFC");
  }
  function jamo(s) { return detone(s).normalize("NFD"); }
  function nfc(j) { return j.normalize("NFC"); }

  // 자모를 음절 단위로 끊는다. 초성이 나오면 새 음절이 시작된 것으로 본다.
  function syllables(j) {
    var out = [], cur = "";
    for (var i = 0; i < j.length; i++) {
      var ch = j[i];
      if (inRange(ch, CHO_A, CHO_Z) && cur) { out.push(cur); cur = ch; }
      else cur += ch;
    }
    if (cur) out.push(cur);
    return out;
  }

  // 초성/종성이 짝이 되는 자모 (ᄆ U+1106 ↔ ᆷ U+11B7 처럼 글자는 같고 자리가 다름)
  var PAIR = {};
  (function () {
    var a = "ᄀᄂᄃᄅᄆᄇᄉᄋᄌᄎᄏᄐᄑᄒᄁᄊᅀᅌᅙᄫ";
    var b = "ᆨᆫᆮᆯᆷᆸᆺᆼᆽᆾᆿᇀᇁᇂᆩᆻᇫᇰᇹᇦ";
    for (var i = 0; i < a.length; i++) PAIR[a[i]] = b[i];
  })();

  // 종성 자모 → 홀로 쓰는 글자 (ᆺ → ㅅ). 관형격 ㅅ 처럼 받침으로 붙는 조사를 떼기 위함
  var JONG_COMPAT = {};
  (function () {
    var a = "ᆨᆫᆮᆯᆷᆸᆺᆼᆽᆾᆿᇀᇁᇂᆩᆻᇫᇰ";
    var b = "ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎㄲㅆㅿㆁ";
    for (var i = 0; i < a.length; i++) JONG_COMPAT[a[i]] = b[i];
  })();

  // 중세국어의 불규칙 교체. 어간 끝소리가 모음 앞에서 바뀌어 적힌다.
  //   돕- + -아 → 도ᄫᅡ (ㅂ→ㅸ) · 짓- + -어 → 지ᅀᅥ (ㅅ→ㅿ) · 듣- + -어 → 드러 (ㄷ→ㄹ)
  var IRREGULAR = { "ᄫ": ["ᆸ", "ㅂ불규칙"], "ᅀ": ["ᆺ", "ㅅ불규칙"], "ᄅ": ["ᆮ", "ㄷ불규칙"] };

  var VERBAL = { Verb: 1, Adjective: 1 };
  // 어간 끝 음절이 이 꼴이면 선어말어미를 삼킨 어간일 수 있다
  var PREFINAL_SYL = { "시": 1, "샤": 1, "니": 1, "리": 1, "오": 1, "우": 1, "더": 1, "거": 1, "ᄂᆞ": 1, "ᅌᅵ": 1 };
  // 관형사형 어미. 이 뒤에 오는 '가·고' 는 의문 보조사다
  var ADNOM = { "ᄂᆞᆫ": 1, "는": 1, "ㄴ": 1, "ᄋᆞᆫ": 1, "은": 1, "ㄹ": 1, "ᄋᆞᆯ": 1, "을": 1, "던": 1 };
  // 평서형 '-라' 는 이 선어말어미들 뒤에서만 쓰인다
  var DECL_RA_PREV = { "니": 1, "리": 1, "오": 1, "우": 1, "더": 1, "거": 1, "ᄉᆞᆸ": 1, "ᄉᆞᇦ": 1, "ᅀᆞᆸ": 1, "ᅀᆞᇦ": 1 };

  // 어느 자리에서 어떤 갈래로 읽을지 — 앞쪽이 먼저
  var PREF_VERB_LAST = ["어말어미", "연결어미", "전성어미", "선어말어미", "조사"];
  var PREF_VERB_MID = ["선어말어미", "전성어미", "연결어미", "어말어미", "조사"];
  var PREF_NOUN = ["조사", "어말어미", "연결어미", "전성어미", "선어말어미"];

  var PUNCT = /[\s.,·:;!?()[\]{}「」『』〈〉《》"']+/;
  // 한자는 체언처럼 쓰인다. 王ᄋᆞᆫ = 王 + ᄋᆞᆫ. 음독만 알면 쪼갤 수 있다.
  var HAN_RUN = /^[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]+/;

  function collectEndings(GRAM) {
    var out = new Map();

    function add(form, kind, name, needsPrev) {
      // '-녀/-니아' 처럼 한 칸에 두 꼴이 적힌 것이 있다. 갈라서 따로 등록한다.
      String(form).split("/").forEach(function (part) {
        var f = detone(part).replace(/^-+|-+$/g, "").trim();
        if (!f || f === "∅") return;
        if (!out.has(f)) out.set(f, []);
        out.get(f).push([kind, name, !!needsPrev]);
      });
    }

    (GRAM.particles || []).forEach(function (p) {
      (p.forms || []).forEach(function (f) { add(f.form, "조사", p.name); });
    });
    ((GRAM.prefinal_endings || {}).items || []).forEach(function (it) {
      (it.forms || []).forEach(function (f) { add(f.form, "선어말어미", it.name); });
      (((it.later_forms || {}).forms) || []).forEach(function (f) { add(f.form, "선어말어미", it.name); });
    });

    var fe = GRAM.final_endings || {};
    function tag(label) {
      var bits = [].slice.call(arguments, 1).filter(Boolean);
      return bits.length ? label + "(" + bits.join("·") + ")" : label;
    }
    [["declarative", "평서형"], ["imperative", "명령형"],
     ["propositive", "청유형"], ["exclamatory", "감탄형"]].forEach(function (pair) {
      (fe[pair[0]] || []).forEach(function (x) {
        // 평서형 '-라' 는 '-오/우-·-니-'·서술격 뒤에서만. 앞이 비면 명령형이다.
        add(x.form, "어말어미", tag(pair[1], x.level), !!x.env && pair[0] === "declarative");
      });
    });
    (((fe.interrogative || {}).items) || []).forEach(function (x) {
      add(x.form, "어말어미", tag("의문형", x.kind, x.level));
    });

    // 상대 높임 선어말어미에 등급을 적어 둔다.
    // '-니-·-리-' 는 문장을 끝맺을 때만 반말 등분이므로 뺀다.
    (((GRAM.speech_levels || {}).levels) || []).forEach(function (l) {
      if (l.id === "halyeo") return;
      (l.prefinal || []).forEach(function (f) {
        var k = detone(f).replace(/^-+|-+$/g, "");
        if (!out.has(k)) return;
        out.set(k, out.get(k).map(function (o) {
          return [o[0], o[1].indexOf(l.name) >= 0 ? o[1] : o[1] + "(" + l.name + ")", o[2]];
        }));
      });
    });

    (GRAM.connective_endings || []).forEach(function (x) { add(x.form, "연결어미", x.meaning || ""); });
    [["nominal", "명사형"], ["adnominal", "관형사형"]].forEach(function (pair) {
      (((GRAM.transformative_endings || {})[pair[0]]) || []).forEach(function (x) {
        add(x.form, "전성어미", pair[1]);
      });
    });
    return out;
  }

  function collectStems(LEX) {
    var stems = new Map();
    LEX.forEach(function (e) {
      var senses = e.senses || [];
      var verbal = senses.some(function (s) { return VERBAL[s.pos]; });
      var keys = new Set([detone(e.headword)]);
      senses.forEach(function (s) { if (s.written) keys.add(detone(s.written)); });
      keys.forEach(function (k) {
        k = k.replace(/^-+|-+$/g, "");
        if (!k) return;
        if (!stems.has(k)) stems.set(k, [e.headword, "표제어", e]);
        if (verbal && k.slice(-1) === "다" && k.length > 1) {
          var st = k.slice(0, -1);
          if (!stems.has(st)) stems.set(st, [e.headword, "어간", e]);
        }
      });
    });
    return stems;
  }

  function build(GRAM, LEX, HANJA) {
    var ENDINGS = collectEndings(GRAM);
    var STEMS = collectStems(LEX);
    HANJA = HANJA || {};

    function sylTail(stem) {
      var sy = syllables(jamo(stem));
      return sy.length ? nfc(sy[sy.length - 1]) : "";
    }

    /* 연철과 불규칙 교체를 되돌린 꼴들. [어간, 어미, 어떻게] 를 돌려준다.
       말ᄊᆞ미 → [말ᄊᆞᆷ, 이, 연철]   ·   도ᄫᅡ → [돕, 아, ㅂ불규칙] */
    function unlink(tok) {
      var out = [], sy = syllables(jamo(tok));
      for (var i = 1; i < sy.length; i++) {
        var head = sy.slice(0, i), tail = sy.slice(i), first = tail[0];
        if (first.length < 2 || !inRange(first[0], CHO_A, CHO_Z)) continue;
        if (!inRange(first[1], JUNG_A, JUNG_Z)) continue;
        var prev = head[head.length - 1];
        var hasCoda = false;
        for (var c = 0; c < prev.length; c++) if (inRange(prev[c], JONG_A, JONG_Z)) hasCoda = true;
        var newTail = [IEUNG + first.slice(1)].concat(tail.slice(1));
        if (hasCoda) {
          // 앞 음절에 이미 받침이 있으면 연철이 아니다. 다만 ㅎ종성체언은 예외:
          // 하ᄂᆞᆯㅎ + 이 → 하ᄂᆞᆯ히 처럼 받침 뒤에 ㅎ 이 한 번 더 붙는다
          if (first[0] === "ᄒ") out.push([nfc(head.join("")), nfc(newTail.join("")), "ㅎ종성체언"]);
          continue;
        }
        var cand = [];
        if (PAIR[first[0]]) cand.push([PAIR[first[0]], "연철"]);
        if (IRREGULAR[first[0]]) cand.push(IRREGULAR[first[0]]);
        cand.forEach(function (mh) {
          var newHead = head.slice(0, -1).concat([prev + mh[0]]);
          out.push([nfc(newHead.join("")), nfc(newTail.join("")), mh[1]]);
          // ㅎ종성체언은 사전에 ㅎ 없이 실린 것이 많다
          if (mh[0] === "ᇂ") out.push([nfc(head.join("")), nfc(newTail.join("")), "ㅎ종성체언"]);
        });
      }
      return out;
    }

    // 끝 음절의 받침이 조사로 쓰이는 글자면 떼어 낸다. 나랏 → [나라, ㅅ]
    function stripCoda(t) {
      var j = jamo(t);
      if (!j) return null;
      var last = j[j.length - 1];
      if (!inRange(last, JONG_A, JONG_Z)) return null;
      var c = JONG_COMPAT[last];
      if (!c || !ENDINGS.has(c)) return null;
      return [nfc(j.slice(0, -1)), c];
    }

    /* 남은 부분이 아는 어미들의 연쇄인지 본다. 중세국어는 어미가 겹쳐 붙는다.
       ᄒᆞ시니 = ᄒᆞ + 시 + 니 처럼 선어말어미와 연결어미가 잇따른다. */
    function splitEndings(rest, depth) {
      depth = depth || 0;
      if (!rest) return [];
      if (depth > 4) return null;
      for (var n = rest.length; n > 0; n--) {
        var head = rest.slice(0, n);
        if (ENDINGS.has(head)) {
          var tail = splitEndings(rest.slice(n), depth + 1);
          if (tail !== null) return [head].concat(tail);
        }
      }
      return null;
    }

    /* 한 꼴이 여러 자리에 쓰일 때, 놓인 자리에 맞는 쪽을 고른다.
       '니' 는 선어말어미도 연결어미도 되는데 맨 끝이면 연결어미다.
       'ᄒᆞ라' 의 '라' 는 서술격 조사가 아니라 명령형 어미다. */
    function role(form, last, verbal, prev) {
      var all = ENDINGS.get(form) || [], i;

      // '가·고' 는 의문 보조사이기도 하고 연결어미·주격조사이기도 하다.
      // ᄒᆞ고 의 '고' 는 연결어미, ᄒᆞᄂᆞᆫ고 의 '고' 는 설명의문이다.
      if (form === "가" || form === "고") {
        var p = prev || "";
        var asks = !!ADNOM[prev] || /(?:ᅌᅵᆺ|ᅵᆺ)$/.test(p);
        for (i = 0; i < all.length; i++) {
          if (!asks && (all[i][0] === "연결어미" || all[i][0] === "조사")) return [all[i][0], all[i][1]];
          if (asks && all[i][0] === "어말어미") return [all[i][0], all[i][1]];
        }
      }

      if (form === "라") {
        var pick = DECL_RA_PREV[prev] ? "평서" : "명령";
        for (i = 0; i < all.length; i++) {
          if (all[i][0] === "어말어미" && all[i][1].indexOf(pick) === 0) return [all[i][0], all[i][1]];
        }
      }

      var opts = all.filter(function (o) { return prev != null || !o[2]; });
      if (!opts.length) opts = all;
      var order = !verbal ? PREF_NOUN : (last ? PREF_VERB_LAST : PREF_VERB_MID);
      for (var w = 0; w < order.length; w++) {
        for (i = 0; i < opts.length; i++) if (opts[i][0] === order[w]) return [opts[i][0], opts[i][1]];
      }
      return opts.length ? [opts[0][0], opts[0][1]] : ["", ""];
    }

    function describe(ends, verbal) {
      return ends.map(function (e, i) {
        return role(e, i === ends.length - 1, verbal, i ? ends[i - 1] : null);
      });
    }

    function analyze(tok) {
      var t = detone(tok), i;

      function made(stem, ends, how, head, kind, entry) {
        var rec = STEMS.get(stem) || [head, kind, null];
        head = head != null ? head : rec[0];
        kind = kind != null ? kind : rec[1];
        var parts = describe(ends, kind === "어간");
        return {
          token: tok, stem: stem, head: head, stem_kind: kind,
          entry: entry !== undefined ? entry : rec[2],
          ending: ends.join(" + "), endings: ends, parts: parts,
          ending_kind: parts.map(function (p) { return p[0] + " " + p[1]; }).join(" · "),
          via: ends.length < 2 ? how : how + "+연쇄"
        };
      }

      // 0) 한자로 시작하면 한자 덩어리를 체언으로 본다. 王ᄋᆞᆫ → 王 + ᄋᆞᆫ
      var hm = HAN_RUN.exec(t);
      if (hm) {
        var run = hm[0], ok = true, reading = "";
        for (i = 0; i < run.length; i++) {
          if (!HANJA[run[i]]) { ok = false; break; }
          reading += HANJA[run[i]]["음"][0];
        }
        if (ok) {
          var rest = t.slice(run.length);
          var he = rest ? splitEndings(rest) : [];
          if (he !== null) {
            if (!he.length) {
              return { token: tok, stem: run, head: reading, stem_kind: "한자", entry: null,
                       ending: null, endings: [], parts: [], ending_kind: "", via: "한자" };
            }
            return made(run, he, "한자", reading, "한자", null);
          }
        }
      }

      // 1) 글자 그대로 쪼개기. 긴 어간부터 보되, 어간 끝 음절이 선어말어미와 같은
      //    꼴이면 뒤로 미룬다. 사전에 'ᄒᆞ니다' 가 있어서 ᄒᆞ니라 가 (ᄒᆞ니 + 라) 로
      //    잡히는데, (ᄒᆞ + 니 + 라) 로 읽어야 '라' 가 평서형임을 알 수 있다.
      var cands = [];
      for (i = t.length - 1; i > 0; i--) {
        var stem = t.slice(0, i);
        if (!STEMS.has(stem)) continue;
        var ends = splitEndings(t.slice(i));
        if (ends) cands.push([PREFINAL_SYL[sylTail(stem)] ? 1 : 0, -stem.length, stem, ends]);
      }
      if (cands.length) {
        cands.sort(function (a, b) {
          return a[0] - b[0] || a[1] - b[1] || (a[2] < b[2] ? -1 : a[2] > b[2] ? 1 : 0);
        });
        return made(cands[0][2], cands[0][3], "직접");
      }

      // 2) 연철·불규칙 되돌려 쪼개기
      var un = unlink(t);
      for (i = 0; i < un.length; i++) {
        if (!STEMS.has(un[i][0])) continue;
        var e2 = splitEndings(un[i][1]);
        if (e2) return made(un[i][0], e2, un[i][2]);
      }

      // 3) 받침으로 붙은 조사 떼기 (나랏 → 나라 + ㅅ)
      var sc = stripCoda(t);
      if (sc && STEMS.has(sc[0])) return made(sc[0], [sc[1]], "받침조사");

      // 4) 어미 없이 표제어 자체
      if (STEMS.has(t)) {
        var r = STEMS.get(t);
        return { token: tok, stem: t, head: r[0], stem_kind: r[1], entry: r[2],
                 ending: null, endings: [], parts: [], ending_kind: "", via: "그대로" };
      }
      return null;
    }

    function analyzeText(text) {
      return String(text || "").split(PUNCT).filter(Boolean).map(function (tok) {
        return { token: tok, result: analyze(tok) };
      });
    }

    return { analyze: analyze, analyzeText: analyzeText,
             endings: ENDINGS, stems: STEMS, detone: detone };
  }

  global.MKAnalyze = { build: build, detone: detone, PUNCT: PUNCT };
})(typeof window !== "undefined" ? window : globalThis);
