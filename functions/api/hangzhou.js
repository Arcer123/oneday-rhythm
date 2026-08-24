// Cloudflare Pages Function: GET /api/hangzhou
// 返回所有众包上报点；首次自动播种演示点位到 KV。

const SEED = [
  { lat: 30.2598, lng: 120.1482, type: "noise", value: 62, note: "湖滨步行街" },
  { lat: 30.2741, lng: 120.1551, type: "noise", value: 78, note: "延安路商圈" },
  { lat: 30.2870, lng: 120.1520, type: "noise", value: 45, note: "武林广场" },
  { lat: 30.2528, lng: 120.1940, type: "noise", value: 55, note: "河坊街" },
  { lat: 30.2792, lng: 120.0280, type: "air", value: 68, note: "西溪湿地" },
  { lat: 30.2330, lng: 120.1320, type: "air", value: 88, note: "滨江高新区" },
  { lat: 30.2466, lng: 120.1810, type: "air", value: 74, note: "钱江新城" },
  { lat: 30.1690, lng: 120.2560, type: "air", value: 52, note: "湘湖" },
  { lat: 30.3470, lng: 120.0910, type: "noise", value: 40, note: "良渚文化村" },
  { lat: 30.3120, lng: 120.3580, type: "air", value: 46, note: "下沙沿江" },
];

export async function onRequestGet({ env }) {
  let reports = null;
  try { reports = JSON.parse((await env.DATA.get("reports")) || "null"); } catch (e) {}
  if (!Array.isArray(reports) || reports.length === 0) {
    reports = SEED;
    try { await env.DATA.put("reports", JSON.stringify(SEED)); } catch (e) {}
  }
  return new Response(JSON.stringify(reports), {
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}
