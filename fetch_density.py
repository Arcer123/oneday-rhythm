#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 Overpass 抓取杭州 POI，聚合成"繁华度"热力。
使用单条正则查询（非 union），每条之间停顿，避开公共 Overpass 的速率限制。
"""

import json
import math
import os
import time
import urllib.parse
import urllib.request
import urllib.error


BBOX = "(30.00,120.00,30.42,120.42)"
OVERPASS_ENDPOINTS = [
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
OUT = "/Users/admin/Documents/ChatGPT/New project/social-heatmap/hz_density.json"
STEP = 0.02
MIN_POIS = 300          # 低于此数量视为抓取失败，不覆盖现有数据

# 单条无 union 的正则查询（public Overpass 更能接受这种写法）
QUERIES = [
    'node["amenity"~"^(restaurant|cafe|school|hospital|bank|cinema|marketplace|university|library)$"](%s);out;' % BBOX,
    'node["shop"~"^(mall|supermarket|department_store|clothes|electronics)$"](%s);out;' % BBOX,
    'node["leisure"~"^(park|fitness_centre|playground|stadium)$"](%s);out;' % BBOX,
    'node["tourism"~"^(hotel|museum|attraction)$"](%s);out;' % BBOX,
    'node["railway"="station"](%s);out;' % BBOX,
    'node["highway"="bus_stop"](%s);out;' % BBOX,
]


def fetch_one(q):
    data = "data=" + urllib.parse.quote(q)
    last = None
    for ep in OVERPASS_ENDPOINTS:
        req = urllib.request.Request(
            ep, data=data.encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                     "User-Agent": "city-pulse-map/1.0 (personal project)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            return payload.get("elements", [])
        except Exception as e:
            last = e
            print(f"  · {ep} 失败({type(e).__name__})")
    if last:
        raise last
    return []


# ---------- 高德 / 百度 POI（中文本地 POI 更全；有 key 时优先走这里，否则回退上方 OSM） ----------
AMAP_KEY = os.environ.get("AMAP_KEY", "")
BAIDU_AK = os.environ.get("BAIDU_AK", "")
UA = "city-pulse-map/1.0 (personal project)"

# 高德 POI 大类类型码
AMAP_TYPES = ["050000", "060000", "080000", "090000", "100000", "110000",
              "120000", "130000", "140000", "150000", "160000", "190000"]
# 百度搜索关键词（覆盖相近类别）
BAIDU_KWS = ["美食", "购物", "娱乐", "医疗", "酒店", "景点", "写字楼",
             "学校", "银行", "公交", "地铁", "商场"]


def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode("utf-8"))


# 坐标转换：高德 GCJ-02、百度 BD-09 → WGS84（对齐 OSM 底图）
def _in_china(lat, lng):
    return 0.929 < lat < 53.55 and 73.66 < lng < 135.05


def _transform_lat(x, y):
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320.0 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(x, y):
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def gcj02_to_wgs84(lng, lat):
    if not _in_china(lat, lng):
        return lng, lat
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - 0.00669342162296594323 * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((6378245.0 * (1 - 0.00669342162296594323)) / (magic * sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (6378245.0 / sqrtmagic * math.cos(radlat) * math.pi)
    return lng - dlng, lat - dlat


def bd09_to_gcj02(lng, lat):
    x = lng - 0.0065
    y = lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * math.pi)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * math.pi)
    return z * math.cos(theta), z * math.sin(theta)


def bd09_to_wgs84(lng, lat):
    lng, lat = bd09_to_gcj02(lng, lat)
    return gcj02_to_wgs84(lng, lat)


def fetch_amap():
    pois = []
    for t in AMAP_TYPES:
        page = 1
        while page <= 40:
            params = {"key": AMAP_KEY, "types": t, "city": "330100", "citylimit": "true",
                      "offset": "25", "page": str(page), "extensions": "base"}
            try:
                d = _get_json("https://restapi.amap.com/v3/place/text?" + urllib.parse.urlencode(params))
            except Exception as e:
                print("  [amap] 失败", t, page, type(e).__name__, e)
                break
            if str(d.get("status")) != "1":
                print("  [amap] 状态:", d.get("info"))
                break
            arr = d.get("pois") or []
            for p in arr:
                loc = p.get("location") or ""
                if loc and "," in loc:
                    lng, lat = loc.split(",")
                    pois.append((float(lng), float(lat)))
            print(f"  [amap] 类型 {t} 页 {page} 得 {len(arr)}（累计 {len(pois)}）")
            if not arr or page * 25 >= int(d.get("count") or 0):
                break
            page += 1
            time.sleep(0.25)
    return [gcj02_to_wgs84(lng, lat) for lng, lat in pois]


def fetch_baidu():
    pois = []
    for kw in BAIDU_KWS:
        page = 0
        while page < 40:
            params = {"query": kw, "region": "杭州", "city_limit": "true", "output": "json",
                      "ak": BAIDU_AK, "page_num": str(page), "page_size": "20",
                      "scope": "1", "coord_type": "bd09ll"}
            try:
                d = _get_json("https://api.map.baidu.com/place/v2/search?" + urllib.parse.urlencode(params))
            except Exception as e:
                print("  [baidu] 失败", kw, page, type(e).__name__, e)
                break
            if str(d.get("status")) != "0":
                print("  [baidu] 状态:", d.get("message"))
                break
            arr = d.get("results") or []
            for r in arr:
                loc = r.get("location") or {}
                if "lat" in loc and "lng" in loc:
                    pois.append((float(loc["lng"]), float(loc["lat"])))
            print(f"  [baidu] 关键词「{kw}」页 {page+1} 得 {len(arr)}（累计 {len(pois)}）")
            if not arr:
                break
            page += 1
            time.sleep(0.3)
    return [bd09_to_wgs84(lng, lat) for lng, lat in pois]


def aggregate(points, source):
    grid = {}
    for lat, lng in points:
        key = (math.floor(lat / STEP), math.floor(lng / STEP))
        grid[key] = grid.get(key, 0) + 1
    cells = [{"lat": round(k[0] * STEP + STEP / 2, 4),
              "lng": round(k[1] * STEP + STEP / 2, 4),
              "value": v} for k, v in grid.items()]
    cells.sort(key=lambda c: c["value"], reverse=True)
    maxv = cells[0]["value"] if cells else 1
    return {"meta": {"source": source, "desc": f"{source} POI 繁华度", "total_poi": len(points),
                     "cells": len(cells), "max": maxv},
            "cells": cells}

def main():
    # 有高德 / 百度 key 时优先抓更全的中文 POI
    if AMAP_KEY or BAIDU_AK:
        if AMAP_KEY:
            print("使用高德 POI（GCJ-02 → WGS84）…")
            points = fetch_amap()
            source = "amap"
        else:
            print("使用百度 POI（BD-09 → WGS84）…")
            points = fetch_baidu()
            source = "baidu"
        if points:
            result = aggregate(points, source)
            with open(OUT, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
            print(f"写入 {OUT}：{len(result['cells'])} 网格，{len(points)} 个 POI，最大 {result['meta']['max']}")
            return
        else:
            print("高德/百度未取得 POI，回退 OSM…")

    # 无 key（或高德/百度失败）时走 OpenStreetMap Overpass
    points = []
    for q in QUERIES:
        ok = False
        for attempt in range(3):
            try:
                els = fetch_one(q)
                pts = [(e.get("lat"), e.get("lon")) for e in els
                       if e.get("lat") is not None and e.get("lon") is not None]
                points.extend(pts)
                print(f"✓ {q[5:20]}... -> {len(pts)} 个")
                ok = True
                break
            except Exception as e:
                print(f"… {q[5:20]}... 失败({type(e).__name__})，重试")
                time.sleep(4)
        time.sleep(5)  # 避限流

    print(f"共 {len(points)} 个 POI 点")
    if len(points) < MIN_POIS:
        print(f"◆ 抓取点太少(<{MIN_POIS})，保留现有 hz_density.json（demo）")
        return
    grid = {}
    for lat, lon in points:
        key = (math.floor(lat / STEP), math.floor(lon / STEP))
        grid[key] = grid.get(key, 0) + 1
    cells = [{"lat": round(k[0] * STEP + STEP / 2, 4),
              "lng": round(k[1] * STEP + STEP / 2, 4),
              "value": v} for k, v in grid.items()]
    cells.sort(key=lambda c: c["value"], reverse=True)
    if cells:
        maxv = cells[0]["value"]
    else:
        maxv = 1
    result = {"meta": {"source": "OpenStreetMap", "desc": "杭州 POI 密度（真实 OSM 数据）",
                       "total_poi": len(points), "cells": len(cells), "max": maxv},
              "cells": cells}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    print(f"写入 {OUT}：{len(cells)} 网格，最大 POI 数 {maxv}")


if __name__ == "__main__":
    main()
