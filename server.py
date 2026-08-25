#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全网情绪热力图 + 杭州城市热力 —— 轻量服务器

仅用 Python 标准库实现：
  - 服务静态页面/前端库
  - 提供情绪数据接口（演示数据，可选尝试抓微博热搜作为“实时”来源）

启动:  python3 server.py [端口]
默认:  端口 8000，浏览器打开 http://127.0.0.1:8000
"""

import json
import math
import os
import re
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENDOR_DIR = os.path.join(BASE_DIR, "vendor")
DATA_DIR = os.path.join(BASE_DIR, "data")
EMOTION_DEMO = os.path.join(DATA_DIR, "emotion_demo.json")
RECORD_DIR = os.path.join(DATA_DIR, "records")
HOT_HISTORY = os.path.join(RECORD_DIR, "hot_history.json")

# 后台自动采样间隔（分钟），可用环境变量 SAMPLE_INTERVAL_MIN 覆盖
SAMPLE_INTERVAL_MIN = float(os.environ.get("SAMPLE_INTERVAL_MIN", "15"))
# 热搜采样历史保留条数（每 15 分钟一次，≈2.5 天；覆盖一个完整昼夜节奏）
HOT_HISTORY_MAX = 240

# 允许对外提供的静态文件（PWA 相关），避免整目录暴露
PUBLIC_STATIC = {
    "manifest.json": "application/manifest+json",
    "sw.js": "application/javascript",
    "icon-192.png": "image/png",
    "icon-512.png": "image/png",
    "apple-touch-icon.png": "image/png",
    "hz_density.json": "application/json",
    "events.json": "application/json",
}

# --------------------------------- 情绪数据 ---------------------------------
# 演示用的省份情绪分布（离线样本）。真实来源见 fetch_weibo_topics()。
DEMO_PROVINCES = [
    {"name": "北京市", "value": 82, "mood": "焦虑", "keyword": "工作压力"},
    {"name": "上海市", "value": 76, "mood": "亢奋", "keyword": "消费回暖"},
    {"name": "广东省", "value": 88, "mood": "忙碌", "keyword": "通勤拥堵"},
    {"name": "浙江省", "value": 70, "mood": "放松", "keyword": "春日出行"},
    {"name": "江苏省", "value": 64, "mood": "愉悦", "keyword": "文旅"},
    {"name": "四川省", "value": 58, "mood": "闲适", "keyword": "火锅夜生活"},
    {"name": "湖北省", "value": 61, "mood": "平淡", "keyword": "工作日"},
    {"name": "山东省", "value": 55, "mood": "平静", "keyword": "通勤"},
    {"name": "河南省", "value": 67, "mood": "焦虑", "keyword": "返乡"},
    {"name": "陕西省", "value": 52, "mood": "闲适", "keyword": "旅游"},
    {"name": "湖南省", "value": 59, "mood": "亢奋", "keyword": "夜经济"},
    {"name": "福建省", "value": 57, "mood": "愉悦", "keyword": "天气"},
    {"name": "重庆市", "value": 66, "mood": "亢奋", "keyword": "周末"},
    {"name": "河北省", "value": 49, "mood": "平静", "keyword": "日常"},
    {"name": "辽宁省", "value": 45, "mood": "低落", "keyword": "降温"},
    {"name": "云南省", "value": 50, "mood": "闲适", "keyword": "旅居"},
    {"name": "广西壮族自治区", "value": 54, "mood": "愉悦", "keyword": "出行"},
    {"name": "黑龙江省", "value": 42, "mood": "低落", "keyword": "寒冷"},
    {"name": "江西省", "value": 51, "mood": "平淡", "keyword": "通勤"},
    {"name": "安徽省", "value": 56, "mood": "平静", "keyword": "日常"},
]


# 简单关键词 -> 情绪 分类（用于从热搜词推断情绪，粗糙但够看）
NEGATIVE = {"爆", "怒", "哭", "痛", "难", "跌", "惨", "死", "崩塌",
            "争议", "质问", "曝光", "调查", "悲剧", "坠", "失联", "退款",
            "裁员", "恐慌", "抢购"}
POSITIVE = {"喜", "赢", "好", "开心", "笑", "冠军", "破纪录", "回暖",
            "治愈", "浪漫", "幸福", "新生", "成功", "突破"}


def mood_from_text(text):
    """根据关键词给一段文本打一个粗略情绪标签。"""
    neg = sum(1 for w in NEGATIVE if w in text)
    pos = sum(1 for w in POSITIVE if w in text)
    if neg > pos:
        return "负面", min(1.0, 0.5 + 0.1 * neg)
    if pos > neg:
        return "正面", min(1.0, 0.5 + 0.1 * pos)
    return "中性", 0.5


# 六类话题关键词词典：把热搜词归入热力图的六条赛道
CATEGORY_KEYWORDS = {
    "工作·通勤": ["工作", "上班", "下班", "加班", "辞职", "离职", "内卷", "通勤", "地铁", "公交",
               "堵", "同事", "老板", "工位", "工资", "薪资", "简历", "面试", "裁员", "996", "打工人"],
    "社会·新闻": ["通报", "回应", "公布", "官方", "警方", "教育局", "央视", "曝光", "调查", "发布",
               "辟谣", "记者", "新闻", "事件", "通报", "回应", "坠", "失联", "争议", "事故"],
    "消费·购物": ["价格", "涨价", "降价", "买", "购物", "消费", "电商", "双十一", "618", "优惠",
               "补贴", "手机", "苹果", "汽车", "首付", "房价", "楼市", "套餐", "退款", "抢购"],
    "情感·emo": ["爱", "分手", "恋爱", "前任", "失恋", "单身", "孤独", "难过", "哭", "emo",
               "焦虑", "抑郁", "想哭", "治愈", "暗恋", "告白", "emo", "勇气"],
    "娱乐·明星": ["明星", "演唱会", "电视剧", "电影", "综艺", "剧", "歌手", "演员", "票房", "女二",
               "男团", "女团", "cp", "官宣", "娱乐圈", "导演", "女主", "开机"],
    "健康·生活": ["健康", "医院", "病", "体检", "睡眠", "熬夜", "减肥", "健身", "养生", "疫苗",
               "疫情", "流感", "传染", "糖尿病", "高血压", "救灾", "物资"],
}


def classify_category(text):
    """把一个热搜词归到六个类别之一；无命中默认归入社会·新闻。"""
    text = str(text)
    best, best_cnt = None, 0
    for cat, words in CATEGORY_KEYWORDS.items():
        cnt = sum(1 for w in words if w in text)
        if cnt > best_cnt:
            best, best_cnt = cat, cnt
    return best or "社会·新闻"


def fetch_weibo_topics(limit=15):
    """尝试抓取微博实时热搜。失败返回 None（调用方回退演示数据）。"""
    url = "https://weibo.com/ajax/side/hotSearch"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/124 Safari/537.36"),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://weibo.com/",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        realtime = payload.get("data", {}).get("realtime", []) or []
        topics = []
        for item in realtime[:limit]:
            word = item.get("word")
            if not word:
                continue
            mood, intensity = mood_from_text(str(word))
            topics.append({"word": word, "mood": mood, "intensity": round(intensity, 2),
                           "hot": item.get("num") or 0})
        return topics if topics else None
    except Exception:
        return None


# ------------------------- 一天话题节奏（24h） -------------------------
# 每个类别一条 0-23 小时的相对讨论度曲线，用于画出“一天节奏”。
RHYTHM_CATEGORIES = [
    {"name": "工作·通勤", "color": "#58a6ff",
     "hourly": [0,0,0,0,0,1,4,9,12,6,5,4,5,7,6,6,8,11,7,4,3,2,1,0]},
    {"name": "社会·新闻", "color": "#ff7a45",
     "hourly": [0,0,0,0,0,0,1,3,6,7,8,9,7,8,7,8,7,6,5,4,3,2,1,0]},
    {"name": "消费·购物", "color": "#ffd166",
     "hourly": [0,0,0,0,0,0,1,2,3,4,5,6,8,5,4,4,5,6,7,9,8,5,2,0]},
    {"name": "情感·emo", "color": "#e63946",
     "hourly": [3,4,3,2,1,0,0,0,1,1,1,1,2,2,2,2,3,4,5,7,9,12,11,7]},
    {"name": "娱乐·明星", "color": "#3ad29f",
     "hourly": [1,1,1,0,0,0,0,1,1,2,2,3,4,3,3,4,5,7,9,10,9,8,5,2]},
    {"name": "健康·生活", "color": "#a371f7",
     "hourly": [0,0,0,0,0,1,3,6,5,3,2,2,3,2,2,2,3,4,4,5,5,4,2,1]},
]


# 演示曲线里每个类别 hourly 的最大值，用于把真实矩阵缩放到同一量纲
RHYTHM_DEMO_MAX = max(max(c["hourly"]) for c in RHYTHM_CATEGORIES)


def compute_real_rhythm(history):
    """从热搜采样历史统计真实的一天节奏。

    返回:
      raw[cat][hour]    原始累加（每类/每时段的加权热度，weight=1+log10(1+hot)）
      real[cat][hour]   归一化到 demo 量纲后的真实矩阵
      covered_hours     覆盖的时段数（0-23 中有采样的）
      sample_count      历史样本条数
      day / night       由真实采样得到的昼夜代表话题（可能为空列表）
    """
    n_cats = len(RHYTHM_CATEGORIES)
    cat_index = {c["name"]: i for i, c in enumerate(RHYTHM_CATEGORIES)}
    raw = [[0.0] * 24 for _ in range(n_cats)]
    coverage = [False] * 24
    hour_topics = {}  # hour -> [(word, weight)]

    for rec in history:
        hour = int(rec.get("hour", 0)) % 24
        top_words = []
        for t in rec.get("topics", []):
            word = t.get("word")
            if not word:
                continue
            hot = float(t.get("hot") or 0)
            weight = 1 + (math.log10(1 + hot) if hot > 0 else 1)
            cat = cat_index.get(classify_category(word))
            if cat is None:
                continue
            raw[cat][hour] += weight
            top_words.append((word, weight))
        coverage[hour] = True
        if top_words:
            top_words.sort(key=lambda x: x[1], reverse=True)
            hour_topics.setdefault(hour, []).append(top_words[0][0])

    covered_hours = sum(1 for c in coverage if c)
    maxv = max((max(row) for row in raw), default=0.0)
    scale = (RHYTHM_DEMO_MAX / maxv) if maxv > 0 else 0.0
    real = [[round(v * scale, 2) for v in row] for row in raw]

    def top_topics(start, end):
        bucket = []
        for h in range(24):
            if start <= end:
                hit = start <= h <= end
            else:  # 跨零点，如 22-2
                hit = h >= start or h <= end
            if hit:
                bucket.extend(hour_topics.get(h, []))
        seen, out = set(), []
        for w in bucket:
            if w not in seen:
                seen.add(w)
                out.append({"word": w, "mood": mood_from_text(w)[0]})
        return out[:8]

    return {
        "raw": raw,
        "real": real,
        "covered_hours": covered_hours,
        "sample_count": len(history),
        "day": top_topics(8, 20),
        "night": top_topics(22, 2),
    }


def blend_rhythm(real):
    """把真实节奏与演示样本按采集进度混合。

    采集越充分(sample_count/10)越趋近真实；未被采集的时段保持演示基线，
    避免热力图出现大片空白。返回 (categories, alpha)。
    """
    alpha = min(1.0, real["sample_count"] / 10.0)
    cats = []
    for ci, base in enumerate(RHYTHM_CATEGORIES):
        hourly = []
        for h in range(24):
            rv = real["real"][ci][h]
            if rv > 0:
                hourly.append(round(base["hourly"][h] * (1 - alpha) + rv * alpha, 2))
            else:
                hourly.append(base["hourly"][h])
        cats.append({"name": base["name"], "color": base["color"], "hourly": hourly})
    return cats, alpha


# 白天(约8-20) 大家在焦虑/关注什么 —— 演示样本
DAY_TOPICS = [
    {"word": "通勤堵死了", "mood": "焦虑"},
    {"word": "内卷和加班", "mood": "焦虑"},
    {"word": "房贷压力", "mood": "焦虑"},
    {"word": "物价上涨", "mood": "焦虑"},
    {"word": "孩子教育", "mood": "焦虑"},
    {"word": "开会写PPT", "mood": "烦躁"},
    {"word": "社会热点", "mood": "中性"},
    {"word": "体检报告", "mood": "焦虑"},
]

# 深夜(约22-02) 大家在聊什么 —— 演示样本
NIGHT_TOPICS = [
    {"word": "深夜emo", "mood": "伤感"},
    {"word": "想离职了", "mood": "低落"},
    {"word": "前任的记忆", "mood": "伤感"},
    {"word": "睡不着", "mood": "低落"},
    {"word": "追剧磕CP", "mood": "愉悦"},
    {"word": "网络梗", "mood": "亢奋"},
    {"word": "夜宵吃啥", "mood": "愉悦"},
    {"word": "城市孤独感", "mood": "伤感"},
]


def append_history(ts, topics):
    """把每次抓到的热搜标注时间戳存档，供后续统计一天的节奏。"""
    os.makedirs(RECORD_DIR, exist_ok=True)
    with _history_lock:
        history = []
        if os.path.exists(HOT_HISTORY):
            try:
                with open(HOT_HISTORY, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []
        history.append({"ts": ts, "hour": time.localtime(ts).tm_hour, "topics": topics})
        # 只保留最近 HOT_HISTORY_MAX 次采样，避免无限膨胀
        history = history[-HOT_HISTORY_MAX:]
        with open(HOT_HISTORY, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)


def load_rhythm(live=False):
    """返回 24h 话题节奏。live=True 时抓取微博热搜并记录采样。"""
    def _read_history():
        if not os.path.exists(HOT_HISTORY):
            return []
        try:
            with open(HOT_HISTORY, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _build(history):
        real = compute_real_rhythm(history)
        cats, alpha = blend_rhythm(real)
        return real, cats, alpha

    history = _read_history()
    real, cats, alpha = _build(history)

    result = {
        "source": "demo",
        "categories": cats,
        "day": real["day"] or DAY_TOPICS,
        "night": real["night"] or NIGHT_TOPICS,
        "now_hour": time.localtime().tm_hour,
        "live": {"ts": None, "topics": [], "mood": "中性"},
        "status": {
            "sample_count": real["sample_count"],
            "coverage_hours": real["covered_hours"],
            "learning_pct": round(alpha * 100),
        },
    }
    if real["sample_count"] > 0:
        result["source"] = "weibo-sampled"

    if live:
        topics = fetch_weibo_topics(limit=12)
        if topics:
            now = int(time.time())
            append_history(now, topics)
            # 把刚抓到的样本也计进节奏
            history = _read_history()
            real, cats, alpha = _build(history)
            result["categories"] = cats
            result["day"] = real["day"] or DAY_TOPICS
            result["night"] = real["night"] or NIGHT_TOPICS
            result["status"] = {
                "sample_count": real["sample_count"],
                "coverage_hours": real["covered_hours"],
                "learning_pct": round(alpha * 100),
            }
            # 统计此刻热搜的主导情绪
            moods = [t["mood"] for t in topics]
            dominant = max(set(["正面", "负面", "中性"]), key=lambda m: moods.count(m))
            result["source"] = "weibo-live" if real["sample_count"] <= 1 else "weibo-sampled"
            result["live"] = {"ts": now, "topics": topics, "mood": dominant}
    return result


def auto_sampler_loop():
    """后台守护线程：每隔 SAMPLE_INTERVAL_MIN 分钟抓一次微博热搜并采样存档。

    用于积累覆盖一整天（甚至多天）的真实样本，从而让 24h 热力图逐渐变真实。
    Cloudflare 上无法常驻线程，部署版可改由外部定时任务(如 UptimeRobot/GitHub Action/
    Cloudflare Cron Worker)周期调用 /api/rhythm?live=1 达到同样效果。
    """
    print(f"[auto-sample] 后台采样已启动 · 每 {SAMPLE_INTERVAL_MIN:g} 分钟一次"
          f"（环境变量 SAMPLE_INTERVAL_MIN 可调）")
    while True:
        time.sleep(SAMPLE_INTERVAL_MIN * 60)
        try:
            topics = fetch_weibo_topics(limit=12)
            if topics:
                now = int(time.time())
                append_history(now, topics)
                print(f"[auto-sample] {time.strftime('%H:%M:%S')} 采样成功 · {len(topics)} 条")
            else:
                print("[auto-sample] 本次抓取失败（可能是微博拦截），跳过")
        except Exception as e:  # 防止线程因单次异常退出
            print(f"[auto-sample] 异常：{e}")


def load_emotion(live=False):
    """返回情绪数据。live=True 且能抓到热搜时混入实时数据。"""
    # data/ 被 .gitignore 排除，全新克隆时 emotion_demo.json 可能不存在，
    # 这里回退到内置的 DEMO_PROVINCES，避免 /api/emotion 直接 500。
    provinces = DEMO_PROVINCES
    if os.path.exists(EMOTION_DEMO):
        try:
            with open(EMOTION_DEMO, "r", encoding="utf-8") as f:
                provinces = json.load(f).get("provinces") or DEMO_PROVINCES
        except Exception:
            provinces = DEMO_PROVINCES
    result = {"source": "demo", "updated": int(time.time()), "provinces": provinces, "topics": []}
    if live:
        topics = fetch_weibo_topics()
        if topics:
            result["source"] = "weibo-live"
            result["topics"] = topics
    return result


# --------------------------------- 历史采样锁 ---------------------------------
_history_lock = threading.Lock()


# --------------------------------- HTTP handler -------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "SocialHeatmap/1.0"

    def log_message(self, fmt, *args):
        # 精简日志，只保留有意义的
        pass

    def _send(self, status, content_type, body):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            index = os.path.join(BASE_DIR, "index.html")
            if os.path.exists(index):
                with open(index, "r", encoding="utf-8") as f:
                    self._send(200, "text/html; charset=utf-8", f.read())
            else:
                self._send(404, "text/plain; charset=utf-8", "index.html not found")
            return

        name = path.lstrip("/")
        if name in PUBLIC_STATIC:
            fpath = os.path.join(BASE_DIR, name)
            if os.path.exists(fpath):
                with open(fpath, "rb") as f:
                    self._send(200, PUBLIC_STATIC[name], f.read())
            else:
                self._send(404, "text/plain", "not found")
            return

        if path == "/api/emotion":
            live_flag = (qs.get("live", ["false"])[0] or "false").lower()
            live = live_flag in ("1", "true", "yes", "on")
            data = load_emotion(live=live)
            self._send(200, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False))
            return

        if path == "/api/rhythm":
            live_flag = (qs.get("live", ["false"])[0] or "false").lower()
            live = live_flag in ("1", "true", "yes", "on")
            data = load_rhythm(live=live)
            self._send(200, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False))
            return

        if path.startswith("/vendor/"):
            rel = path[len("/vendor/"):]
            fpath = os.path.normpath(os.path.join(VENDOR_DIR, rel))
            if not fpath.startswith(VENDOR_DIR) or not os.path.exists(fpath):
                self._send(404, "text/plain", "not found")
                return
            ext = os.path.splitext(fpath)[1].lower()
            mime = {".js": "application/javascript", ".css": "text/css",
                    ".json": "application/json", ".png": "image/png"}.get(ext, "application/octet-stream")
            with open(fpath, "rb") as f:
                self._send(200, mime, f.read())
            return

        self._send(404, "text/plain; charset=utf-8", "404")

    def do_POST(self):
        self._send(404, "application/json", json.dumps({"error": "not found"}))


def main():
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Running at http://127.0.0.1:{port}")
    print("情绪热力图: /api/emotion   (加 ?live=1 尝试抓微博热搜)")
    try:
        threading.Thread(target=auto_sampler_loop, daemon=True).start()
    except Exception as e:
        print(f"后台采样启动失败：{e}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
