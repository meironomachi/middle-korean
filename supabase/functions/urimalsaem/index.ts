// 우리말샘(국립국어원) 오픈 API 중계.
// 인증키는 주소 변수(key=)로 들어가는데, 그 값을 어디에도 남기지 않기 위해
// Supabase 비밀값(URIMALSAEM_KEY)에만 두고 여기서 꺼내 부른다. book-search 함수와 같은 방식.
//
// 비밀값 넣는 곳: Supabase 대시보드 → Edge Functions → Secrets → URIMALSAEM_KEY

const SEARCH = "https://opendict.korean.go.kr/api/search";
const VIEW = "https://opendict.korean.go.kr/api/view";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

// 그대로 넘길 수 있는 변수만 받는다 (임의의 주소를 대신 부르지 못하게)
const ALLOWED = new Set([
  "q", "start", "num", "advanced", "target", "method", "sort", "part",
  "type1", "type2", "type3", "type4", "pos", "cat", "multimedia", "letter_s", "letter_e",
  "update_s", "update_e", "lang", "norm",
]);

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS, "Content-Type": "application/json; charset=utf-8" },
  });

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });

  const key = Deno.env.get("URIMALSAEM_KEY") ?? "";
  if (!key) {
    return json({ error: "URIMALSAEM_KEY 비밀 설정이 없어요. Supabase 대시보드에서 넣어 주세요." }, 503);
  }

  let body: Record<string, unknown> = {};
  try {
    body = await req.json();
  } catch { /* 빈 몸은 그냥 기본값 */ }

  const which = body.endpoint === "view" ? VIEW : SEARCH;
  const url = new URL(which);
  url.searchParams.set("key", key);
  url.searchParams.set("req_type", "json");
  for (const [k, v] of Object.entries(body)) {
    if (ALLOWED.has(k) && v !== undefined && v !== null && v !== "") {
      url.searchParams.set(k, String(v));
    }
  }
  if (!url.searchParams.get("q") && body.endpoint !== "view") {
    return json({ error: "q(검색어)가 필요해요" }, 400);
  }

  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(20000) });
    const text = await res.text();
    if (!res.ok) return json({ error: `상위 서버 응답 ${res.status}`, body: text.slice(0, 300) }, 502);
    try {
      return json(JSON.parse(text));
    } catch {
      // 에러는 XML 로 올 때가 있음
      return json({ error: "JSON 이 아닌 응답", body: text.slice(0, 300) }, 502);
    }
  } catch (e) {
    return json({ error: String((e as Error)?.message ?? e) }, 502);
  }
});
