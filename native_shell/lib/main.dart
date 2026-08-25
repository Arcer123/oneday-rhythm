import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

void main() => runApp(const OneDayApp());

/// 极薄的原生壳：只负责加载公网 PWA 页面。
///
/// 这样做的意义：所有界面和功能都来自服务器，服务器更新后手机打开即同步，
/// 不需要再重新打包 APK、不需要重装。只有当你改了默认地址/图标/应用名等
/// 壳本身的设置时才需要重新打包。
class OneDayApp extends StatelessWidget {
  const OneDayApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '一天话题节奏',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        useMaterial3: true,
        colorSchemeSeed: Colors.blueGrey,
      ),
      home: const WebShell(),
    );
  }
}

class WebShell extends StatefulWidget {
  const WebShell({super.key});

  @override
  State<WebShell> createState() => _WebShellState();
}

class _WebShellState extends State<WebShell> {
  // 在 build_apk.sh 里通过 --dart-define=APP_URL=... 注入，默认公网地址
  static const String _startUrl = String.fromEnvironment(
    'APP_URL',
    defaultValue: 'https://oneday-rhythm.pages.dev',
  );

  late final WebViewController _controller;
  bool _loading = true;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0xFF0d1117))
      ..setNavigationDelegate(NavigationDelegate(
        onPageStarted: (_) {
          if (mounted) setState(() => _loading = true);
        },
        onPageFinished: (_) {
          if (mounted) setState(() => _loading = false);
        },
        onWebResourceError: (err) {
          // 只对主框架报错弹提示，忽略子资源（如地图瓦片）的个别失败。
          // 部分安卓版本对子资源会返回 null，用 == true 可安全忽略。
          if (err.isForMainFrame == true && mounted) {
            setState(() {
              _error = err.description?.isNotEmpty == true
                  ? err.description!
                  : '网络错误，请检查网络后重试';
              _loading = false;
            });
          }
        },
      ));
    _load();
  }

  Future<void> _load({bool forceFresh = false}) async {
    setState(() {
      _loading = true;
      _error = '';
    });
    // 强制刷新时清掉 WebView 缓存，保证拿到服务器最新版
    if (forceFresh) {
      await _controller.clearCache();
    }
    await _controller.loadRequest(Uri.parse(_startUrl));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          WebViewWidget(controller: _controller),
          if (_loading)
            const Positioned.fill(
              child: ColoredBox(
                color: Color(0xFF0d1117),
                child: Center(child: CircularProgressIndicator()),
              ),
            ),
          if (_error.isNotEmpty)
            Positioned.fill(
              child: ColoredBox(
                color: const Color(0xFF0d1117),
                child: Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.wifi_off, size: 44, color: Colors.white70),
                      const SizedBox(height: 12),
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 32),
                        child: Text(
                          '加载失败：$_error',
                          textAlign: TextAlign.center,
                          style: const TextStyle(color: Colors.white70),
                        ),
                      ),
                      const SizedBox(height: 16),
                      ElevatedButton.icon(
                        onPressed: () => _load(forceFresh: true),
                        icon: const Icon(Icons.refresh),
                        label: const Text('重试'),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          // 手动刷新：拉取服务器最新版
          SafeArea(
            child: Align(
              alignment: Alignment.bottomRight,
              child: Padding(
                padding: const EdgeInsets.only(right: 12, bottom: 20),
                child: FloatingActionButton.small(
                  heroTag: 'refresh_fab',
                  backgroundColor: const Color(0xFF161b22),
                  foregroundColor: Colors.white,
                  onPressed: _loading ? null : () => _load(forceFresh: true),
                  child: const Icon(Icons.refresh),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
