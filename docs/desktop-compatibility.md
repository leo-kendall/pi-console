# 远程桌面兼容范围与配置

桌面连接需要服务器上已有图形会话及兼容的桌面服务。监控后端可连接，不代表图形桌面已经配置。Pi Console 通过 HTTPS API 和仅监听 `127.0.0.1:14822` 的 guacd，连接固定的本机 RDP 或 VNC 服务；手机不直接连接 RDP/VNC 端口。

| 服务器环境 | 支持范围 |
| --- | --- |
| GNOME Remote Desktop / RDP | 保留已有 GNOME `connection.json` 格式，默认 NLA；必须固定 SHA-256 证书指纹。现有可选 GNOME 安装器仍仅适用于其文档列出的条件。 |
| xrdp 或已有 RDP 服务 | 可显式配置本机端口、NLA 或 TLS、账号、密码、域及证书指纹；不会安装或替换服务。实际认证与图形会话配置由该服务决定。 |
| VNC / WayVNC | RFB 3.3、3.7、3.8；仅支持单独提供的 None 或经典 VNC 密码认证。密码为 1–8 个 ASCII 字符；服务须监听回环地址。 |
| 要求 VeNCrypt、TLS、RA2 等安全模式的 VNC/WayVNC | 当前不支持，连接前会明确拒绝；不会自动关闭认证或把服务改成弱认证。混合提供多种认证模式也拒绝，避免 guacd 自行选择其他模式。 |
| 无图形桌面 / Lite 镜像 | 需先自行部署桌面及兼容服务。其他监控功能不依赖桌面。 |

已验证范围是协议模拟、隔离的真实 guacd 与合成 RDP/VNC 服务、浏览器和 Android 编译；没有把这些测试当成 Raspberry Pi OS、xrdp 或其他发行版的实体硬件兼容认证。WayVNC 名称本身不能保证认证模式兼容。黑块显示问题的调查仍保持暂停，此功能没有改动渲染方案。

## 配置已有服务

凭据只保存在服务器的 `remote-desktop/connection.json`。它必须为当前后端用户或 root 拥有的普通文件，权限不允许组和其他用户读取（建议 `0600`）；符号链接被拒绝。文件不通过 API 返回，也不要把它加入版本控制。目标只能是字面值 `127.0.0.1` 或 `::1`，端口 1–65535，不能从请求传入任意目标。

原有 GNOME 格式保持有效：

```json
{"username":"desktop-user","password":"replace-locally","fingerprint":"SHA256=AA:...:AA"}
```

上例指纹仅为示意，必须替换为服务器证书完整的 32 字节 SHA-256 指纹。新 RDP 配置示例（同样替换完整指纹）：

```json
{"protocol":"rdp","host":"127.0.0.1","port":3390,"security":"tls","username":"desktop-user","password":"replace-locally","domain":"","fingerprint":"SHA256=AA:...:AA"}
```

`security` 只能是 `nla`（默认）或 `tls`；固定证书验证始终启用。旧版 guacd 没有 `cert-fingerprints` 参数时会拒绝 RDP，而不是忽略证书。证书轮换时先在可信的服务器管理通道核对新指纹，再更新私有文件。

经典 VNC 密码配置：

```json
{"protocol":"vnc","host":"127.0.0.1","port":5900,"security":"vnc","password":"replace"}
```

对仅回环可达、已单独配置为无认证的服务，可显式使用 `"security":"none","password":""`。这不会调整服务器配置，也不会降级不兼容的服务。经典 VNC 没有传输加密，因此本机回环限制仍然必要；公网入口只需控制台 HTTPS。

先把完整配置放在自行创建的私有文件（如 `/private/path/desktop.json`），再执行：

```sh
python3 remote-desktop/configure.py preview < /private/path/desktop.json
python3 remote-desktop/configure.py configure < /private/path/desktop.json
python3 remote-desktop/configure.py probe
```

`preview` 只验证并输出脱敏计划；不写凭据、不连接目标、不运行安装器。`configure` 只新建 `0600` 凭据文件；已有文件或符号链接一律保留并拒绝覆盖。已有配置的管理员可备份私有文件后用本地编辑器更新；不要把凭据放入命令行参数或聊天中。`probe` 对 VNC 只进行版本/安全类型协商，不提交密码、不启动桌面会话；RDP 的真实 TLS 指纹与认证验证要通过 App 的受认证桌面连接执行。

以上命令不安装包、不启动或停用桌面服务、不修改 VNC/WayVNC/RDP、防火墙或显示会话。可选 GNOME 安装流程仍见[部署说明](deployment.md)；它不是通用 Linux、xrdp 或 WayVNC 安装器。单独的 guacd 桥接安装器继续仅管理有项目所有权收据的本机容器。

## 键盘、鼠标与剪贴板

活动桌面支持物理键盘的按下/松开、左右 Ctrl/Alt/Shift/Super、方向键、F1–F12 和 Unicode 字符，按键组合通过 Guacamole 公共键盘接口传递。Android 返回键保留为本机操作，系统本身截留的快捷键无法承诺送达。软键盘仍通过现有文字输入框发送。

桌面控件提供 Ctrl/Alt/Shift/Super 锁定键，可与硬件按键及其他锁定键组合；再次点击取消，或点“释放按键”。失焦、隐藏、断开或切换服务器会释放远程按键和鼠标按钮。编辑本机输入框/设置时停止原生键盘捕获，鼠标只在桌面区域捕获；保留触控板、拖动、左右/中键和滚轮。水平硬件滚轮使用 Shift+滚轮，应用是否支持横向滚动取决于远程程序。

“发送手机剪贴板”只在点击时读取本机纯文本，并通过 Guacamole 剪贴板流发送；“复制远程剪贴板”只在点击时写入手机剪贴板。不会轮询或自动同步手机剪贴板；不读取 URI、图片或调用剪贴板内容提供器。双向纯文本均限制 16 KiB UTF-8，超限拒绝，断开清空缓存。远程桌面服务或应用也可能禁止剪贴板。

## 验证与排查

连接失败先核对私有文件权限、固定本机端口、VNC 安全类型、RDP 证书指纹和现有桌面服务状态；配置工具输出不包含密码。guacd 继续使用 warning 日志级别，不要为了排查把含认证或桌面内容的协议载荷写入日志。

可复现测试（需已有 Python、Node 22+、JDK、Android SDK、Firefox；真实 transport 测试只使用已缓存不可变 guacd 镜像，不拉取镜像）：

```sh
python3 -m unittest discover -s tests -p 'test_desktop*.py'
python3 -m unittest discover -s remote-desktop -p 'test_*.py'
PI_ANDROID_JAR=/path/to/android.jar python3 tests/run_desktop_java.py
PI_DESKTOP_GUACD_IMAGE=guacamole/guacd@sha256:8974eaa9ba32f713daf311e7cc8cd7e4cdfba1edea39eed75524e78ef4b08f4f python3 -m unittest discover -s tests -p test_desktop_guacd_integration.py -v
flock /tmp/pi-console-browser.lock python3 scripts/test_browser.py test_desktop_input_ui.mjs test_desktop_edge_ui.mjs
```

部分发行版打包的 Firefox 无法访问宿主 `/tmp` profile，可把 `TMPDIR` 指向工作目录中的私有测试目录。Android 构建方式见[构建说明](build.md)。显示诊断保持现有统计方式，统计不能代表已验证实体手机的黑块问题。
