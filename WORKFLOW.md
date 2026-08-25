# 一天话题节奏 · 协作工作流

本仓库 = **官方权威仓库**（GitHub: `Arcer123/oneday-rhythm` → Cloudflare Pages 自动发布）。
所有改动、所有协作 agent 的产出都要落到这里，通过本仓库提交与上线，避免改动堆积在别处。

## 目录结构

- 根目录：**Web 版 PWA**（`index.html` 主入口、`sw.js` 网络优先、`functions/` 抓热搜的 Serverless）
- `native_shell/`：**安卓 APK 的 WebView 壳源码**（只负责加载公网页，基本不用改）

## 两条更新轨道

### A. 改功能（99% 的情况）→ 全自动同步，不用重装

1. 改根目录 `index.html`（或功能/数据脚本）
2. 提交并推送：`git add -A && git commit -m "..." && git push origin main`
3. Cloudflare Pages 1–2 分钟内自动重新发布
4. 手机打开 App（壳）或 PWA 即最新版；壳右下角圆形刷新按钮可强制拉最新

### B. 改壳本身（图标/应用名/默认地址）→ 才需要重新打包

- 改动都在 `native_shell/`
- 一键打包：`zsh native_shell/build_apk.sh`
- 产物：`~/dev/oneday/build/app/outputs/flutter-apk/app-release.apk`

## 约定（给协作 agent）

- 唯一的源码权威位置就是**本仓库**。不要在 `~/dev/oneday` 或旧目录
  `New project/oneday_rhythm_app` 里改东西，那里只是残留的旧副本。
- 每次改动都必须 `git add -A && git commit`，完成一件就 `git push`，避免改动堆积。
- 不要提交构建产物（`build/`、`.dart_tool/`、`android/.gradle/`）。
