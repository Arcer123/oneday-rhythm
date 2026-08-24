// Cloudflare Pages Function: POST /api/report
// 接收众包上报，持久化到 KV（"reports"）。

export async function onRequestPost({ env, request }) {
  let body;
  try { body = await request.json(); } catch (e) {
    return json({ error: "bad json" }, 400);
  }
  const lat = Number(body.lat), lng = Number(body.lng);
  if (!isFinite(lat) || !isFinite(lng) || !body.type) {
    return json({ error: "missing fields" }, 400);
  }
  const value = Math.max(0, Math.min(100, Math.round(Number(body.value) || 50)));
  const report = {
    lat: Number(lat.toFixed(6)), lng: Number(lng.toFixed(6)),
    type: body.type === "noise" ? "noise" : "air",
    value, note: String(body.note || "").slice(0, 60),
    ts: Math.floor(Date.now() / 1000),
  };

  try {
    const reports = JSON.parse((await env.DATA.get("reports")) || "[]");
    reports.push(report);
    await env.DATA.put("reports", JSON.stringify(reports));
    return json({ ok: true, total: reports.length }, 200);
  } catch (e) {
    return json({ error: "storage failed" }, 500);
  }
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}
