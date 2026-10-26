# Android 构建

## 标准环境

使用 JDK 17+、Python 3.11+、Android SDK Platform 35 和 Build Tools 35.0.0。先从发布者取得 SDK、审阅并接受相应条款。仓库不附带 SDK、JDK、Gradle、签名密钥或下载的工具链。

```sh
export ANDROID_HOME=/path/to/android-sdk
export JAVA_HOME=/path/to/jdk
python3 -B scripts/test_java.py
python3 -B scripts/build_android.py
```

产物为 `build/pi-console-debug.apk`，使用本地生成的开发密钥。此密钥只用于开发，不用于正式商业发布；`build/` 整体被 Git 和源码导出器排除。脚本自身不会联网下载构建依赖。

标准 Google SDK 工具需要匹配构建主机架构。ARM64 Linux 如使用其他兼容工具链，可显式设置 `PI_ANDROID_AAPT2`、`PI_ANDROID_ZIPALIGN`、`PI_ANDROID_D8_JAR`、`PI_ANDROID_APKSIGNER_JAR`、`PI_ANDROID_RESOURCE_JAR`；不得把工具链文件或其下载凭据提交到仓库。ARM64 本机构建可使用这些覆盖项；GitHub Actions 使用标准 SDK。

## 正式签名

妥善保管自己的长期签名密钥并备份；同一包名的后续更新需使用匹配的签名。包名为 `dev.piconsole`。测试版使用开发密钥；改用生产密钥后，原开发版通常需要卸载后安装。

```sh
export PI_CONSOLE_KEYSTORE=/private/location/release.p12
export PI_CONSOLE_KEY_ALIAS=YOUR_ALIAS
read -rs PI_CONSOLE_KEYSTORE_PASSWORD
export PI_CONSOLE_KEYSTORE_PASSWORD
python3 -B scripts/build_android.py --release
unset PI_CONSOLE_KEYSTORE_PASSWORD
```

密码通过环境传给签名工具，不应写进命令行常量、源码或 CI 日志。正式产物是 `build/pi-console-release.apk`。目前脚本适用于密钥密码与 keystore 密码相同的 PKCS12；其他密钥形式先自行适配并验证。

许可证及 Guacamole 声明同时打入 APK，在“设置 → 开源许可证”可查看。GitHub CI 只上传开发 APK，不创建正式 Release。每次 CI 使用新的临时开发密钥，不适合用作连续覆盖升级的安装包；需要持续分发时应使用自己保管的固定签名。

## 可选界面烟测

使用 Node 22+ 与支持 WebDriver BiDi 的 Firefox，先创建临时 profile 并启动 `firefox --headless --no-remote --profile /path/to/temp-profile --remote-debugging-port 19226 about:blank`。另开终端运行 `python3 -B scripts/preview_ui.py`，再运行 `node scripts/test_ui.mjs`。预览只监听本机 18777，全部数据和原生边界均为模拟，绝不连接真实服务器。检查后停止这两个临时进程并删除临时 profile。该测试不验证 Android Keystore、TLS 或真实服务执行。

服务列表布局与状态本地化回归：在同一预览与临时 Firefox 会话下运行 `node scripts/test_resource_layout_ui.mjs`，覆盖 320、360、412、768 像素宽度、深浅主题、连续长名称，以及缺失或未知的状态值。

桌面边缘诊断交互回归：在同一模拟预览与临时 Firefox 下运行 `node scripts/test_desktop_edge_ui.mjs`，验证四角输入会自动采样、无需打开控件或主动重绘、记录数量受限、复制报告和断开连接取消。原生窗口范围与错误处理由 `tests/test_desktop_probe.py` 用 Android API 替身运行真实 Java 采样代码；这些测试不代替实体手机上的 PixelCopy 与绘制验证。
