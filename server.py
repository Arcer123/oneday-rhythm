#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全网情绪热力图 + 杭州噪音/空气众包地图 —— 轻量服务器

仅用 Python 标准库实现：
  - 服务静态页面/前端库
  - 提供情绪数据接口（演示数据，可选尝试抓微博热搜作为“实时”来源）
  - 接收杭州众包上报并持久化到 data/hangzhou_reports.json

启动:  python3 server.py [端口]
默认:  端口 8000，浏览器打开 http://127.0.0.1:8000
"""

import json
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
HANGZHOU_REPORTS = os.path.join(DATA_DIR, "hangzhou_reports.json")
RECORD_DIR = os.path.join(DATA_DIR, "records")
HOT_HISTORY = os.path.join(RECORD_DIR, "hot_history.json")

# 允许对外提供的静态文件（PWA 相关），避免整目录暴露
PUBLIC_STATIC = {
    "manifest.json": "application/manifest+json",
    "sw.js": "application/javascript",
    "icon-192.png": "image/png",
    "icon-512.png": "image/png",
    "apple-touch-icon.png": "image/png",
}

# 众包上报默认点位数（首次运行时写入，作为演示底图）
HANGZHOU_SEED = [
    {"lat": 30.2598, "lng": 120.1482, "type": "noise", "value": 62, "note": "湖滨步行街"},
    {"lat": 30.2741, "lng": 120.1551, "type": "noise", "value": 78, "note": "延安路商圈"},
    {"lat": 30.2870, "lng": 120.1520, "type": "noise", "value": 45, "note": "武林广场"},
    {"lat": 30.2528, "lng": 120.1940, "type": "noise", "value": 55, "note": "河坊街"},
    {"lat": 30.2792, "lng": 120.0280, "type": "air", "value": 68, "note": "西溪湿地"},
    {"lat": 30.2330, "lng": 120.1320, "type": "air", "value": 88, "note": "滨江高新区"},
    {"lat": 30.2466, "lng": 120.1810, "type": "air", "value": 74, "note": "钱江新城"},
    {"lat": 30.1690, "lng": 120.2560, "type": "air", "value": 52, "note": "湘湖"},
    {"lat": 30.3470, "lng": 120.0910, "type": "noise", "value": 40, "note": "良渚文化村"},
    {"lat": 30.3120, "lng": 120.3580, "type": "air", "value": 46, "note": "下沙沿江"},
]


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
NEGATIVE = {"爆", "怒", "哭", "痛", "难", "跌", "涨", "惨", "死", "崩塌",
            "争议", "质问", "曝光", "调查", "悲剧", "坠", "失联", "退款",
            "裁员", "恐慌", "抢购"}
POSITIVE = {"喜", "赢", "涨", "好", "开心", "笑", "冠军", "破纪录", "回暖",
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
    with _reports_lock:
        history = []
        if os.path.exists(HOT_HISTORY):
            try:
                with open(HOT_HISTORY, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []
        history.append({"ts": ts, "hour": time.localtime(ts).tm_hour, "topics": topics})
        # 只保留最近 60 次采样，避免无限膨胀
        history = history[-60:]
        with open(HOT_HISTORY, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)


def load_rhythm(live=False):
    """返回 24h 话题节奏。live=True 时抓取微博热搜并记录采样。"""
    result = {
        "source": "demo",
        "categories": RHYTHM_CATEGORIES,
        "day": DAY_TOPICS,
        "night": NIGHT_TOPICS,
        "now_hour": time.localtime().tm_hour,
        "live": {"ts": None, "topics": [], "mood": "中性"},
    }
    if live:
        topics = fetch_weibo_topics(limit=12)
        if topics:
            now = int(time.time())
            append_history(now, topics)
            # 统计此刻热搜的主导情绪
            moods = [t["mood"] for t in topics]
            dominant = max(set(["正面", "负面", "中性"]), key=lambda m: moods.count(m))
            result["source"] = "weibo-live"
            result["live"] = {"ts": now, "topics": topics, "mood": dominant}
    return result


def load_emotion(live=False):
    """返回情绪数据。live=True 且能抓到热搜时混入实时数据。"""
    with open(EMOTION_DEMO, "r", encoding="utf-8") as f:
        demo = json.load(f)
    result = {"source": "demo", "updated": int(time.time()), "provinces": demo["provinces"], "topics": []}
    if live:
        topics = fetch_weibo_topics()
        if topics:
            result["source"] = "weibo-live"
            result["topics"] = topics
    return result


# --------------------------------- 众包存储 ---------------------------------
_reports_lock = threading.Lock()


def _ensure_reports():
    if not os.path.exists(HANGZHOU_REPORTS):
        with open(HANGZHOU_REPORTS, "w", encoding="utf-8") as f:
            json.dump(HANGZHOU_SEED, f, ensure_ascii=False, indent=2)


def load_reports():
    with _reports_lock:
        _ensure_reports()
        with open(HANGZHOU_REPORTS, "r", encoding="utf-8") as f:
            return json.load(f)


def add_report(report):
    with _reports_lock:
        _ensure_reports()
        with open(HANGZHOU_REPORTS, "r", encoding="utf-8") as f:
            reports = json.load(f)
        reports.append(report)
        with open(HANGZHOU_REPORTS, "w", encoding="utf-8") as f:
            json.dump(reports, f, ensure_ascii=False, indent=2)
        return len(reports)


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

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length == 0:
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return None

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

        if path == "/api/hangzhou":
            reports = load_reports()
            self._send(200, "application/json; charset=utf-8", json.dumps(reports, ensure_ascii=False))
            return

        if path.startswith("/vendor/"):
            rel = path[len("/vendor/"):]
            fpath = os.path.normpath(os.path.join(VENDOR_DIR, rel))
            if not fpath.startswith(VENDOR_DIR) or not os.path.exists(fpath):
                self._send(404, "text/plain", "not found")
                return
            ext = os.path.splitext(fpath)[1].lower()
            mime = {"js": "application/javascript", ".css": "text/css",
                    ".json": "application/json", ".png": "image/png"}.get(ext, "application/octet-stream")
            with open(fpath, "rb") as f:
                self._send(200, mime, f.read())
            return

        self._send(404, "text/plain; charset=utf-8", "404")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/report":
            data = self._read_json()
            if not data or "lat" not in data or "lng" not in data or "type" not in data:
                self._send(400, "application/json", json.dumps({"error": "missing fields"}))
                return
            try:
                lat = float(data["lat"])
                lng = float(data["lng"])
                value = int(float(data.get("value", 50)))
            except (TypeError, ValueError):
                self._send(400, "application/json", json.dumps({"error": "bad numeric"}))
                return
            report = {
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "type": "noise" if data["type"] == "noise" else "air",
                "value": max(0, min(100, value)),
                "note": str(data.get("note", ""))[:60],
                "ts": int(time.time()),
            }
            count = add_report(report)
            self._send(200, "application/json", json.dumps({"ok": True, "total": count}))
            return
        self._send(404, "application/json", json.dumps({"error": "not found"}))


def main():
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Running at http://127.0.0.1:{port}")
    print("情绪热力图: /api/emotion   (加 ?live=1 尝试抓微博热搜)")
    print("杭州众包:    /api/hangzhou")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
