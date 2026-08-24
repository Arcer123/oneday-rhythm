#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从下载的浙江 OSM pbf 解析杭州 POI，聚合成真实"繁华度"热力。
只统计杭州 bbox 内、且带常见 POI 标签的节点。
"""

import json
import math
import osmium

PBF = "/Users/admin/dev/zhejiang.osm.pbf"
OUT = "/Users/admin/Documents/ChatGPT/New project/social-heatmap/hz_density.json"
STEP = 0.02
LAT0, LAT1, LNG0, LNG1 = 30.00, 30.42, 120.00, 120.42

AMENITY = {"restaurant", "cafe", "school", "hospital", "bank", "cinema",
           "marketplace", "university", "library"}
SHOP = {"mall", "supermarket", "department_store"}
LEISURE = {"park", "fitness_centre", "playground", "stadium"}
TOURISM = {"hotel", "museum", "attraction"}


class POIHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.pts = []

    def node(self, n):
        lat, lon = n.location.lat, n.location.lon
        if not (LAT0 <= lat <= LAT1 and LNG0 <= lon <= LNG1):
            return
        tags = {t.k: t.v for t in n.tags}
        keep = (tags.get("amenity") in AMENITY or tags.get("shop") in SHOP
                or tags.get("leisure") in LEISURE or tags.get("tourism") in TOURISM
                or tags.get("railway") == "station" or tags.get("highway") == "bus_stop")
        if keep:
            self.pts.append((lat, lon))


def main():
    h = POIHandler()
    print("解析 pbf...")
    h.apply_file(PBF)
    print(f"共 {len(h.pts)} 个 POI 节点")
    grid = {}
    for lat, lon in h.pts:
        k = (math.floor(lat / STEP), math.floor(lon / STEP))
        grid[k] = grid.get(k, 0) + 1
    cells = [{"lat": round(k[0] * STEP + STEP / 2, 4),
              "lng": round(k[1] * STEP + STEP / 2, 4),
              "value": v} for k, v in grid.items()]
    cells.sort(key=lambda c: c["value"], reverse=True)
    maxv = cells[0]["value"] if cells else 1
    result = {"meta": {"source": "OpenStreetMap", "desc": "杭州 POI 密度（真实 OSM 数据，pbf 快照）",
                       "total_poi": len(h.pts), "cells": len(cells), "max": maxv},
              "cells": cells}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    print(f"写入 {OUT}：{len(cells)} 网格，最大 POI 数 {maxv}")


if __name__ == "__main__":
    main()
