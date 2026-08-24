#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成杭州"繁华程度"演示热力数据（基于真实商圈/景点的热点分布）。
输出 hz_density.json，被前端作为静态数据加载。
meta.source = "demo"; 将来可替换为真实 OSM POI（见 fetch_density.py）。
"""

import json
import math

STEP = 0.02
LAT0, LAT1, LNG0, LNG1 = 30.00, 30.42, 120.00, 120.42
SIGMA = 0.02

# (lat, lng, peak) —— 杭州主要人流/商圈热点
HOTSPOTS = [
    (30.25, 120.16, 96),   # 湖滨/延安路
    (30.28, 120.16, 82),   # 武林广场
    (30.24, 120.14, 88),   # 西湖景区
    (30.25, 120.21, 72),   # 钱江新城
    (30.21, 120.21, 70),   # 滨江
    (30.31, 120.34, 58),   # 下沙
    (30.29, 120.21, 66),   # 杭州东站
    (30.27, 120.07, 54),   # 西溪
    (30.39, 120.03, 40),   # 良渚
    (30.18, 120.26, 56),   # 萧山
]


def frange(a, b, step):
    out = []
    v = a
    while v <= b + 1e-9:
        out.append(v)
        v += step
    return out


def value(lat, lng):
    total = 0.0
    for hlat, hlng, peak in HOTSPOTS:
        d = (lat - hlat) ** 2 + (lng - hlng) ** 2
        total += peak * math.exp(-d / (2 * SIGMA * SIGMA))
    return total


def main():
    cells = []
    for la in frange(LAT0, LAT1, STEP):
        for ln in frange(LNG0, LNG1, STEP):
            v = value(la, ln)
            if v > 2:
                cells.append({"lat": round(la, 4), "lng": round(ln, 4), "value": round(v, 1)})
    cells.sort(key=lambda c: c["value"], reverse=True)
    result = {"meta": {"source": "demo", "desc": "繁华度演示数据（杭州热点分布）",
                       "cells": len(cells)},
              "cells": cells}
    out = "/Users/admin/Documents/ChatGPT/New project/social-heatmap/hz_density.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    print(f"写入 {out}：{len(cells)} 个网格，最大值 {cells[0]['value']}")


if __name__ == "__main__":
    main()
