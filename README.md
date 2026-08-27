# 一天话题节奏 & 杭州城市热力

一个零依赖、浏览器即开即用的轻量 Web 应用，包含两个独立功能。

## 快速开始

```bash
cd social-heatmap
python3 server.py 8090
```

浏览器打开 <http://127.0.0.1:8090>。

## 安装到手机（PWA）

这是一个 PWA，iPhone 上可当作 app 使用：

1. 确保手机与这台 Mac 在**同一个 Wi-Fi**；
2. 用 iPhone 的 **Safari** 打开 `http://192.168.3.59:8090`（IP 随网络变化，用 `ipconfig getifaddr en0` 查最新）；
3. 点底部「分享」→「添加到主屏幕」→ 会生成一个独立图标，点开即全屏运行。

> 说明：离线缓存（Service Worker）在 `localhost` / HTTPS 下才完整生效；局域网 HTTP 下「添加到主屏幕」仍可用，但完整 PWA 增强建议部署到 HTTPS。
>
> 想要真正的**原生 iOS app**（上架 App Store），当前机器仅装有 CommandLine Tools（无完整 Xcode）。需先安装 Xcode，或用云 Mac；数据接口层保持不变，前端可用 SwiftUI 重写。

## 部署到公网（免费 HTTPS）

项目已按 **Cloudflare Pages** 结构改好（静态前端 + `functions/` 里的 Serverless 函数 + KV 存数据）。免费、全自动 HTTPS、支持 PWA。完整步骤见 [DEPLOY.md](DEPLOY.md)。

需要：一个 GitHub 账号（或直接用 Direct Upload）+ 一个 Cloudflare 账号。部署得到 `https://xxx.pages.dev` 后，手机即可一键安装。

## 功能

### 1. 一天话题节奏

一张 **0–24 小时 × 话题类别** 的热力图。用颜色深浅直观展示大家一天在聊什么：

- 白天：工作·通勤、社会·新闻、消费·购物 占据主导
- 深夜：情感·emo、娱乐·明星 明显升温

页面底部有 **☀️ 白天大家在焦虑 / 关注** 和 **🌙 深夜大家在聊** 两个话题对比面板。

右上角「⚡ 抓取此刻热搜」会去抓 **微博实时热搜**，标到时间轴上的"此刻"竖线上，并判断主导情绪。

> 数据说明：热力分布默认使用**演示基线**（符合常识的日均节奏）。每次抓取"此刻热搜"时，接口都会把带时间戳的热搜存入 `data/records/hot_history.json`（最多保留 240 次），并**实时统计**出真实的 24h 节奏。页面会显示「采样累计次数 · 覆盖时段 · 学习进度」，采样越多，热力图越趋近真实分布（未被采样的时段暂用演示基线补全）。

**自动采样**（无需手动点按钮也能攒数据）：
- **本地 `server.py`**：启动即自动开启后台采样线程，默认每 **15 分钟**抓一次热搜（用环境变量 `SAMPLE_INTERVAL_MIN` 可改，如 `SAMPLE_INTERVAL_MIN=5 python3 server.py`）。
- **页面打开时**：前端会每 15 分钟静默请求一次 `/api/rhythm?live=1`，照样积累样本（本地/云端都适用）。
- **Cloudflare 部署版**：Serverless 无法常驻线程，可让外界定时任务（UptimeRobot / GitHub Actions / Cloudflare Cron Worker 等）周期调用 `https://你的域名/api/rhythm?live=1` 达到等效的自动采样。

### 2. 杭州城市热力（实时天气 / 空气）

基于 Open-Meteo 公开接口，绘制杭州实时的城市级热力图层，可在「🌡️ 温度 / 🌧️ 降水 / 🌫️ 空气(AQI)」之间切换：
- **空气层**是真实 **European AQI**（Open-Meteo 空气质量接口），按 0.04° 格点取值，替代了原来的假空气种子点。
- 另有「🏢 繁华（`hz_density.json`，由 `fetch_density.py` 抓 **高德 / 百度 POI** 生成）」与「📰 事件（`events.json`）」图层。

> 底图默认用 **Esri 街道图**，加载失败会自动兜底到 **CARTO → OpenStreetMap**（均为 WGS84/Web Mercator，与热力点对齐），并在面板提示当前底图源与切换状态。`events.json` 为**示例数据（非实时）**，页面会明确标注。

## 目录结构

```
social-heatmap/
├── server.py                    # 标准库 HTTP 服务器（无第三方依赖）
├── index.html                   # 前端（ECharts + Leaflet）
├── manifest.json                # PWA 配置（可添加到手机主屏）
├── sw.js                        # Service Worker（离线缓存 app shell）
├── icon-192.png / icon-512.png / apple-touch-icon.png   # 应用图标
├── DEPLOY.md                    # Cloudflare Pages 部署指南
├── functions/api/               # Cloudflare Serverless 函数（rhythm）
├── fetch_density.py             # 抓高德/百度/OSM POI → hz_density.json（繁华度）
├── hz_density.json              # 繁华度热力数据（真实 POI）
├── events.json                  # 事件数据
├── vendor/                      # 本地化前端库 + 中国 GeoJSON
└── data/
    ├── emotion_demo.json        # （保留）情绪演示数据接口
    └── records/hot_history.json # 热搜采样历史（用于统计真实的一天分布）
```

## 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/rhythm` | 一天话题节奏。`?live=1` 抓取微博热搜并记录采样 |
| GET | `/api/emotion` | （保留）省份情绪接口，`?live=1` 抓取微博热搜 |
| GET | `/hz_density.json` | 繁华度热力数据（静态托管） |
| GET | `/events.json` | 事件数据（静态托管） |

## 技术栈

- 后端：Python 标准库 `http.server`，无 pip 依赖（`urllib` 抓微博热搜）
- 前端：ECharts 5（热力图）+ Leaflet 1.1（vendor 内置）+ leaflet.heat（杭州热力）
- 库文件在 `vendor/`，可离线跑（杭州底图需联网，优先 Esri，失败自动切 CARTO/OSM）

## 后续可接的真实数据

- **话题节奏**：微博热搜按小时采样累积（已做）、话题阅读量时间序列、评论情感分析
- **空气**：Open-Meteo 空气质量 AQI（已接）；如需国标/站点级可换 aqicn / 国控站
- **繁华度**：高德 / 百度 POI（脚本已备：设置 `AMAP_KEY` / `BAIDU_AK` 后运行 `python3 fetch_density.py` 生成真实数据）
- 项目目前是 Web 版；接口结构可直接迁移到 iOS（SwiftUI 调同一套接口）
