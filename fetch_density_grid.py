#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分格抓取杭州 OSM POI，聚合成真实"繁华度"热力。
把 bbox 切成小格子，逐格小查询（响应小，避免被公共 Overpass 断开），
格间停顿避让速率限制。仅当抓到的点足够多时才覆盖 hz_density.json。
"""

import json
import math
import time
import urllib.parse
import urllib.request
import urllib.error

OVERPASS_ENDPOINTS = [
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
OUT = "/Users/admin/Documents/ChatGPT/New project/social-heatmap/hz_density.json"

LAT0, LAT1, LNG0, LNG1 = 30.00, 30.42, 120.00, 120.42
CELL = 0.06          # 分格尺寸
STEP = 0.02          # 聚合网格
AMENITY = "restaurant|cafe|school|hospital|bank|cinema|marketplace|university|library"
SHOP = "mall|supermarket|department_store"


def fetch(cell):
    lat0, lng0, lat1, lng1 = cell
    q = ('[out:json][timeout:60];'
         f'node["amenity"~"^({AMENITY})$"]({lat0},{lng0},{lat1},{lng1});out;'
         f'node["shop"~"^({SHOP})$"]({lat0},{lng0},{lat1},{lng1});out;')
    data = "data=" + urllib.parse.quote(q)
    last = None
    for ep in OVERPASS_ENDPOINTS:
        try:
            req = urllib.request.Request(
                ep, data=data.encode("utf-8"),
                headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                         "User-Agent": "city-pulse-map/1.0"},
            )
            with urllib.request.urlopen(req, timeout=70) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            return [(e.get("lat"), e.get("lon")) for e in payload.get("elements", [])
                    if e.get("lat") is not None]
        except Exception as e:
            last = e
            print(f"  · {ep} 失败({type(e).__name__})")
    if last:
        raise last
    return []


def cells():
    out = []
    la = LAT0
    while la < LAT1:
        ln = LNG0
        while ln < LNG1:
            out.append((round(la, 3), round(ln, 3),
                        round(min(la + CELL, LAT1), 3), round(min(ln + CELL, LNG1), 3)))
            ln += CELL
        la += CELL
    return out


def main():
    points = []
    cells_list = cells()
    print(f"分 {len(cells_list)} 格")
    for cell in cells_list:
        ok = False
        for attempt in range(2):
            try:
                pts = fetch(cell)
                points.extend(pts)
                ok = True
                break
            except Exception as e:
                print(f"格 {cell[0]},{cell[1]} 失败({type(e).__name__})，重试")
                time.sleep(2)
        time.sleep(0.9)

    print(f"共 {len(points)} 个 POI")
    if len(points) < 500:   # 太少了视为失败，不动现有数据
        print("◆ 抓取的点太少，保留现有 hz_density.json（演示）")
        return
    grid = {}
    for lat, lon in points:
        k = (math.floor(lat / STEP), math.floor(lon / STEP))
        grid[k] = grid.get(k, 0) + 1
    cells_out = [{"lat": round(k[0] * STEP + STEP / 2, 4),
                  "lng": round(k[1] * STEP + STEP / 2, 4),
                  "value": v} for k, v in grid.items()]
    cells_out.sort(key=lambda c: c["value"], reverse=True)
    maxv = cells_out[0]["value"]
    result = {"meta": {"source": "OpenStreetMap", "desc": "杭州 POI 密度（真实 OSM 数据）",
                       "total_poi": len(points), "cells": len(cells_out), "max": maxv},
              "cells": cells_out}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    print(f"写入 {OUT}：{len(cells_out)} 网格，最大 POI 数 {maxv}")


if __name__ == "__main__":
    main()
