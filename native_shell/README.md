# native_shell · 安卓 WebView 壳

这个壳把公网 PWA 包成一个「真 App」：有桌面图标、启动即加载
`https://oneday-rhythm.pages.dev`。因为**界面和功能全部来自服务器**，
所以改功能**不需要重装 APK**——服务器更新后手机打开即同步。

只有改**壳本身**的东西（图标、应用名、默认地址）才需要重新打包。

## 重新打包

在仓库根目录运行：

```bash
zsh native_shell/build_apk.sh
```

产物：`~/dev/oneday/build/app/outputs/flutter-apk/app-release.apk`
