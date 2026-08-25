#!/bin/zsh
set -e

# ---------- 本机工具链（已装好）----------
export JAVA_HOME=/Users/admin/dev/jdk17/jdk-17.0.20.1+1/Contents/Home
export ANDROID_HOME=/Users/admin/dev/android-sdk
export ANDROID_SDK_ROOT=$ANDROID_HOME
export PATH="$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin:$JAVA_HOME/bin:$HOME/dev/flutter/bin:$PATH"

# 国内镜像
export FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn
export PUB_HOSTED_URL=https://pub.flutter-io.cn
export FLUTTER_GIT_URL=https://gitee.com/mirrors/flutter.git

# 公网页源；局域网调试时用 BASE_URL=http://<局域网IP>:8090 覆盖
BASE_URL="${BASE_URL:-https://oneday-rhythm.pages.dev}"

# 本脚本所在目录（仓库里的 native_shell = 壳源码的权威位置）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$SCRIPT_DIR"

# 构建目录（无空格，避免路径问题）
APP="${APP:-/Users/admin/dev/oneday}"

rm -rf "$APP"
mkdir -p "$APP"
cd "$APP"

flutter config --no-analytics

echo "==> 生成安卓平台骨架"
flutter create --no-pub --platforms android --org com.example --project-name oneday_rhythm .

echo "==> 放入我们的 WebView 壳源码"
cp "$SRC/lib/main.dart" lib/
cp "$SRC/pubspec.yaml" pubspec.yaml

echo "==> 配置网络权限与应用名（话题节奏）"
python3 - <<'PY'
p = 'android/app/src/main/AndroidManifest.xml'
s = open(p).read()
if 'android.permission.INTERNET' not in s:
    s = s.replace('<application',
        '<uses-permission android:name="android.permission.INTERNET"/>\n    <application', 1)
if 'usesCleartextTraffic' not in s:
    s = s.replace('<application',
        '<application android:usesCleartextTraffic="true"', 1)
s = s.replace('android:label="oneday_rhythm"', 'android:label="话题节奏"')
open(p, 'w').write(s)
PY

echo "==> 安装依赖"
flutter pub get

echo "==> 打包 APK"
flutter build apk --release --dart-define=APP_URL=$BASE_URL

echo ""
echo "✅ APK 生成于："
echo "$APP/build/app/outputs/flutter-apk/app-release.apk"
