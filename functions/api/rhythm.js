// Cloudflare Pages Function: /api/rhythm
// GET /api/rhythm            -> 演示的一天话题节奏
// GET /api/rhythm?live=1     -> 抓微博热搜并记录采样到 KV
// 给部署版做"自动采样"：用一个外部定时任务（UptimeRobot / GitHub Action /
// Cloudflare Cron Worker）每隔 N 分钟请求一次 /api/rhythm?live=1 即可积累真实样本。

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

// 六类话题关键词词典：把热搜词归入热力图的六条赛道
const CATEGORY_KEYWORDS = {
  "工作·通勤": ["工作","上班","下班","加班","辞职","离职","内卷","通勤","地铁","公交","堵","同事","老板","工位","工资","薪资","简历","面试","裁员","996","打工人"],
  "社会·新闻": ["通报","回应","公布","官方","警方","教育局","央视","曝光","调查","发布","辟谣","记者","新闻","事件","坠","失联","争议","事故"],
  "消费·购物": ["价格","涨价","降价","买","购物","消费","电商","双十一","618","优惠","补贴","手机","苹果","汽车","首付","房价","楼市","套餐","退款","抢购"],
  "情感·emo": ["爱","分手","恋爱","前任","失恋","单身","孤独","难过","哭","emo","焦虑","抑郁","想哭","治愈","暗恋","告白","勇气"],
  "娱乐·明星": ["明星","演唱会","电视剧","电影","综艺","剧","歌手","演员","票房","女二","男团","女团","cp","官宣","娱乐圈","导演","女主","开机"],
  "健康·生活": ["健康","医院","病","体检","睡眠","熬夜","减肥","健身","养生","疫苗","疫情","流感","传染","糖尿病","高血压","救灾","物资"],
};

const RHYTHM_DEMO_MAX = Math.max(...CATEGORIES.flatMap((c) => c.hourly));

function categorize(text) {
  let best = null, bestCnt = 0;
  for (const [cat, words] of Object.entries(CATEGORY_KEYWORDS)) {
    const cnt = words.reduce((n, w) => n + (String(text).includes(w) ? 1 : 0), 0);
    if (cnt > bestCnt) { best = cat; bestCnt = cnt; }
  }
  return best || "社会·新闻";
}

function computeRealRhythm(history) {
  const catIndex = CATEGORIES.map((c, i) => [c.name, i]);
  const idxOf = (name) => catIndex.find(([n]) => n === name)?.[1];
  const raw = CATEGORIES.map(() => Array(24).fill(0));
  const coverage = Array(24).fill(false);
  const hourTopics = {};

  for (const rec of history) {
    const hour = (Number(rec.hour) || 0) % 24;
    const topWords = [];
    for (const t of (rec.topics || [])) {
      const word = t.word;
      if (!word) continue;
      const hot = Number(t.hot) || 0;
      const weight = 1 + (hot > 0 ? Math.log10(1 + hot) : 1);
      const ci = idxOf(categorize(word));
      if (ci === undefined) continue;
      raw[ci][hour] += weight;
      topWords.push([word, weight]);
    }
    coverage[hour] = true;
    if (topWords.length) {
      topWords.sort((a, b) => b[1] - a[1]);
      (hourTopics[hour] = hourTopics[hour] || []).push(topWords[0][0]);
    }
  }

  const covered_hours = coverage.filter(Boolean).length;
  const maxv = Math.max(...raw.flat(), 0);
  const scale = maxv > 0 ? RHYTHM_DEMO_MAX / maxv : 0;
  const real = raw.map((row) => row.map((v) => Math.round(v * scale * 100) / 100));

  const topTopics = (start, end) => {
    const bucket = [];
    for (let h = 0; h < 24; h++) {
      const hit = start <= end ? (h >= start && h <= end) : (h >= start || h <= end);
      if (hit) bucket.push(...(hourTopics[h] || []));
    }
    return [...new Set(bucket)].slice(0, 8).map((w) => ({ word: w, mood: moodFromText(w) }));
  };

  return {
    raw, real, covered_hours,
    sample_count: history.length,
    day: topTopics(8, 20),
    night: topTopics(22, 2),
  };
}

function blendRhythm(real) {
  const alpha = Math.min(1, real.sample_count / 10);
  const cats = CATEGORIES.map((base, ci) => {
    const hourly = base.hourly.map((demoV, h) => {
      const rv = real.real[ci][h];
      return rv > 0 ? Math.round((demoV * (1 - alpha) + rv * alpha) * 100) / 100 : demoV;
    });
    return { name: base.name, color: base.color, hourly };
  });
  return { cats, alpha };
}

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
  // Cloudflare 边缘默认 UTC，用北京时区（UTC+8）保证与本地 server.py 一致；
  // 否则“此刻”竖线和 24h 采样时段会整体偏移。中国无夏令时，固定 +8。
  const hour = (new Date().getUTCHours() + 8) % 24;

  let history = [];
  try { history = JSON.parse((await env.DATA.get("history")) || "[]"); } catch (e) {}
  if (!Array.isArray(history)) history = [];

  const real = computeRealRhythm(history);
  const { cats, alpha } = blendRhythm(real);
  const result = {
    source: real.sample_count > 0 ? "weibo-sampled" : "demo",
    categories: cats,
    day: real.day.length ? real.day : DAY_TOPICS,
    night: real.night.length ? real.night : NIGHT_TOPICS,
    now_hour: hour,
    live: { ts: null, topics: [], mood: "中性" },
    status: {
      sample_count: real.sample_count,
      coverage_hours: real.covered_hours,
      learning_pct: Math.round(alpha * 100),
    },
  };

  if (live) {
    const topics = await fetchWeiboTopics();
    if (topics && topics.length) {
      history.push({ ts: now, hour, topics });
      const newReal = computeRealRhythm(history);
      const { cats: newCats, alpha: newAlpha } = blendRhythm(newReal);
      result.categories = newCats;
      result.day = newReal.day.length ? newReal.day : DAY_TOPICS;
      result.night = newReal.night.length ? newReal.night : NIGHT_TOPICS;
      result.status = {
        sample_count: newReal.sample_count,
        coverage_hours: newReal.covered_hours,
        learning_pct: Math.round(newAlpha * 100),
      };
      result.source = newReal.sample_count > 1 ? "weibo-sampled" : "weibo-live";
      const moods = topics.map((t) => t.mood);
      const dominant = ["正面", "负面", "中性"].reduce((a, b) =>
        moods.filter((m) => m === a).length >= moods.filter((m) => m === b).length ? a : b);
      result.live = { ts: now, topics, mood: dominant };
      try {
        // 保留近 240 次（≈2.5 天@15min/次），覆盖完整昼夜节奏
        await env.DATA.put("history", JSON.stringify(history.slice(-240)));
      } catch (e) { /* 忽略 */ }
    }
  }
  return new Response(JSON.stringify(result), {
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}
