# 一天话题节奏 · 协作约定（Agent Rules）

任何 agent 进入本仓库必须先读本文件再动手。本文件优先于其它文档的模糊表述。

## 唯一权威来源

- 本仓库 GitHub：`Arcer123/oneday-rhythm`。推送到 `main` 会触发 Cloudflare Pages 自动重新发布。
- 所有改动必须落在**本仓库**。**禁止**修改 `/Users/admin/dev/oneday`（构建目录）或
  `New project/oneday_rhythm_app`（已废弃的旧壳副本）。

## 目录职责

- 根目录：Web 版 PWA（`index.html` 主入口、`sw.js` 网络优先、`functions/` Serverless）。
- `native_shell/`：安卓 WebView 壳源码（只加载公网页，**基本不用改**）。

## 远程同步原则

- **99% 的改动都在 Web 版**（`index.html` / 数据 / 功能脚本）。改完推上去，手机/App 打开即自动同步，无需重装。
- 只有当改动涉及 App 图标、应用名、默认地址等"壳"本身时，才改 `native_shell/`。

## 禁止事项

- 禁止提交构建产物：`build/`、`.dart_tool/`、`android/.gradle/`、`*.iml`。
- 禁止改动被忽略的数据目录：`data/`、`screenshots/`。
- 只读任务（审查 / 审计）**不得写入、不得 push**，只返回报告。
- **子 agent 只 commit，不擅自 push 到线上**；上线/发布统一由主 agent 把关执行。

## 常用命令

- 本地起服务：`python3 server.py 8090`
- 一键上线：`zsh deploy.sh "更新说明"`（= `git add -A` + `git commit` + `git push origin main`）
- 重打 APK：`zsh native_shell/build_apk.sh`（产物 `~/dev/oneday/build/app/outputs/flutter-apk/app-release.apk`）

## 任务收尾要求

- 做完改动后：`git add -A && git commit -m "..."`，然后汇报改了哪些文件、是否影响线上。
- 若要上线，把上线动作交给主 agent（执行 `zsh deploy.sh "..."`），不要自己 push 线上。
