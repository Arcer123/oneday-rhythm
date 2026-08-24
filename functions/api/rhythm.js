// Cloudflare Pages Function: /api/rhythm
// GET /api/rhythm            -> 演示的一天话题节奏
// GET /api/rhythm?live=1     -> 抓微博热搜并记录采样到 KV

const CATEGORIES = [
  { name: "工作·通勤", color: "#58a6ff", hourly: [0,0,0,0,0,1,4,9,12,6,5,4,5,7,6,6,8,11,7,4,3,2,1,0] },
  { name: "社会·新闻", color: "#ff7a45", hourly: [0,0,0,0,0,0,1,3,6,7,8,9,7,8,7,8,7,6,5,4,3,2,1,0] },
  { name: "消费·购物", color: "#ffd166", hourly: [0,0,0,0,0,0,1,2,3,4,5,6,8,5,4,4,5,6,7,9,8,5,2,0] },
  { name: "情感·emo", color: "#e63946", hourly: [3,4,3,2,1,0,0,0,1,1,1,1,2,2,2,2,3,4,5,7,9,12,11,7] },
  { name: "娱乐·明星", color: "#3ad29f", hourly: [1,1,1,0,0,0,0,1,1,2,2,3,4,3,3,4,5,7,9,10,9,8,5,2] },
  { name: "健康·生活", color: "#a371f7", hourly: [0,0,0,0,0,1,3,6,5,3,2,2,3,2,2,2,3,4,4,5,5,4,2,1] },
];

const DAY_TOPICS = [
  { word: "通勤堵死了", mood: "焦虑" }, { word: "内卷和加班", mood: "焦虑" },
  { word: "房贷压力", mood: "焦虑" }, { word: "物价上涨", mood: "焦虑" },
  { word: "孩子教育", mood: "焦虑" }, { word: "开会写PPT", mood: "烦躁" },
  { word: "社会热点", mood: "中性" }, { word: "体检报告", mood: "焦虑" },
];

const NIGHT_TOPICS = [
  { word: "深夜emo", mood: "伤感" }, { word: "想离职了", mood: "低落" },
  { word: "前任的记忆", mood: "伤感" }, { word: "睡不着", mood: "低落" },
  { word: "追剧磕CP", mood: "愉悦" }, { word: "网络梗", mood: "亢奋" },
  { word: "夜宵吃啥", mood: "愉悦" }, { word: "城市孤独感", mood: "伤感" },
];

const NEGATIVE = new Set("爆 怒 哭 痛 难 跌 惨 死 崩塌 争议 质问 曝光 调查 悲剧 坠 失联 退款 裁员 恐慌 抢购".split(" "));
const POSITIVE = new Set("喜 赢 好 开心 笑 冠军 破纪录 回暖 治愈 浪漫 幸福 新生 成功 突破".split(" "));

function moodFromText(text) {
  let neg = 0, pos = 0;
  for (const w of NEGATIVE) if (text.includes(w)) neg++;
  for (const w of POSITIVE) if (text.includes(w)) pos++;
  if (neg > pos) return "负面";
  if (pos > neg) return "正面";
  return "中性";
}

async function fetchWeiboTopics(limit = 12) {
  try {
    const resp = await fetch("https://weibo.com/ajax/side/hotSearch", {
      headers: {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://weibo.com/",
      },
      cf: { cacheTtl: 300 },
    });
    const payload = await resp.json();
    const realtime = (payload.data && payload.data.realtime) || [];
    return realtime.slice(0, limit).map((item) => ({
      word: item.word, mood: moodFromText(String(item.word || "")),
      intensity: 0.5, hot: item.num || 0,
    })).filter((t) => t.word);
  } catch (e) {
    return null;
  }
}

export async function onRequestGet({ env, request }) {
  const url = new URL(request.url);
  const live = url.searchParams.get("live") === "1";
  const now = Math.floor(Date.now() / 1000);
  const hour = new Date().getHours();
  const result = {
    source: "demo", categories: CATEGORIES, day: DAY_TOPICS, night: NIGHT_TOPICS,
    now_hour: hour, live: { ts: null, topics: [], mood: "中性" },
  };

  if (live) {
    const topics = await fetchWeiboTopics();
    if (topics && topics.length) {
      result.source = "weibo-live";
      const moods = topics.map((t) => t.mood);
      const dominant = ["正面", "负面", "中性"].reduce((a, b) =>
        moods.filter((m) => m === a).length >= moods.filter((m) => m === b).length ? a : b);
      result.live = { ts: now, topics, mood: dominant };
      // 采样存档到 KV（最多 60 次）
      try {
        const history = JSON.parse((await env.DATA.get("history")) || "[]");
        history.push({ ts: now, hour, topics });
        await env.DATA.put("history", JSON.stringify(history.slice(-60)));
      } catch (e) { /* 忽略 */ }
    }
  }
  return new Response(JSON.stringify(result), {
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}
