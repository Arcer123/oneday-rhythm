# 部署到 Cloudflare Pages（免费 HTTPS + PWA）

本项目 = 静态前端（网页 + PWA）+ Serverless 函数（`functions/`，负责抓热搜、存热搜采样）。
用 **Cloudflare Pages** 一个平台就能跑全部，全免费，自带 HTTPS、CDN、PWA。

## 你需要准备

- 一个 **GitHub** 账号（把代码托管上去，推荐用 Git 集成部署，Functions 最稳）
- 一个 **Cloudflare** 账号（免费）

> 如果不想用 GitHub，也可以用 Pages 的 **Direct Upload** 直接拖拽上传，但 Functions 建议用 Git 集成。

## 步骤

### 1. 把代码推到 GitHub

在项目根目录（`social-heatmap/`）执行：

```bash
cd social-heatmap
git init
git add -A
git commit -m "one-day rhythm + hangzhou city heatmap (PWA)"
```

然后在 GitHub 上建一个仓库，按提示 `git remote add` + `git push` 推上去。

### 2. 创建 Cloudflare KV 命名空间
数据（热搜采样）存在 Cloudflare 的**键值存储（KV）**里，需要先建一个：

1. 登录 Cloudflare 控制台 → 左侧「Workers & Pages」→ 「KV」；
2. 点「Create namespace」，名字填 `DATA`，记下它的 **namespace ID**。

### 3. 创建 Pages 项目（Git 集成）
1. 「Workers & Pages」→「Create application」→「Pages」→「Connect to Git」；
2. 授权 GitHub，选中刚才的仓库；
3. 构建设置：
   - **Framework preset**：`None`
   - **Build command**：留空
   - **Build output directory**：`/`
4. 点「Save and Deploy」。

部署完会得到一个网址，形如 `https://<项目名>.pages.dev`。

### 4. 绑定 KV
1. 进入该 Pages 项目 → 「Settings」→「Functions」→「KV namespace bindings」；
2. 「Add binding」，**Variable name 填 `DATA`**，选第 2 步创建的 namespace；
3. 保存。

### 5. 重新部署（让绑定生效）
在项目页点「Deployments」→ 重新部署一次（或推一次代码触发），绑定即可生效。

## 完成后

- 手机打开 `https://<项目名>.pages.dev`，此时是 **HTTPS**，Service Worker 会生效；
- iPhone Safari 或安卓 Chrome →「添加到主屏幕 / 安装应用」，即可像 app 一样用；
- 数据存在 Cloudflare KV 里，全球都能访问，且持久。

> 「抓取此刻热搜」在云端由函数抓取（Cloudflare 边缘 IP 可能被微博限制，失败会自动回退演示数据——这是微博的接口限制，正常现象）。

## 本地开发

本地仍用 Python：

```bash
python3 server.py 8090
```

打开 `http://127.0.0.1:8090`。本地用 `server.py`，云端用 `functions/`，接口一致（`/api/rhythm`），前端代码不用改。

## 日常更新流程（一键上线）

日常改功能（99% 的情况）走这条链路，**无需重打包、无需重装**：

1. 在根目录改 `index.html`（或功能/数据脚本）；
2. 一键发布：`zsh deploy.sh "更新说明"`；
3. Cloudflare Pages 1-2 分钟内自动重新发布到 `https://oneday-rhythm.pages.dev`；
4. 手机打开 App（原生壳）或 PWA 即自动同步，壳右下角圆形刷新按钮可强制拉最新。

只有改原生壳本身（图标/应用名/默认地址）时才需要重新打包：

```bash
zsh native_shell/build_apk.sh
# 产物：~/dev/oneday/build/app/outputs/flutter-apk/app-release.apk
```
