#!/bin/zsh
# 一键上线：改动 -> 提交 -> 推 GitHub -> Cloudflare 自动重新发布 -> 手机/App 打开即同步。
#
# 用法：zsh deploy.sh "更新说明"
# 说明：仓库已连 GitHub(Arcer123/oneday-rhythm) + Cloudflare Pages，
#       推送 main 会触发自动构建。原生壳(native_shell/)几乎不需要重打包。
set -e

cd "$(cd "$(dirname "$0")" && pwd)" || exit 1

if [ -n "$1" ]; then
  MSG="$1"
else
  MSG="chore: update $(date '+%Y-%m-%d %H:%M')"
fi

echo "==> 暂存所有改动"
git add -A

echo "==> 提交：$MSG"
if ! git commit -m "$MSG"; then
  echo "(没有改动可提交，直接推送)"
fi

echo "==> 推送到 GitHub（main）"
git push origin main

echo ""
echo "✅ 已推送。Cloudflare Pages 会在 1-2 分钟内自动重新发布。"
echo "   手机打开 App(壳) 或 PWA 即自动同步；可点壳右下角圆形刷新按钮强制拉最新。"
echo "   仅当改 native_shell/ 里的图标/应用名/默认地址时，才需要重新打包 APK。"
