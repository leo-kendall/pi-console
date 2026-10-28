# Changelog

## 0.6.0-beta.1

- 保存多个服务器配置，独立加密配对、应用入口与偏好，切换时清理旧会话和读数。
- 手机管理设备名称、访问角色、撤销配对和服务、容器的具体动作授权。
- 从官方发布检查更新，后台下载并校验 SHA256、包名和兼容签名，再由 Android 确认安装。
- 日志持续跟随、暂停、筛选与导出；新增多指标和进程历史、可调告警防抖及手机免打扰。
- 本机 RDP、经典 VNC、实体键鼠、组合键和显式双向文本剪贴板。
- 文件后台队列、暂停续传、批量操作及本机授权目录，单文件最高 8 GiB。
- 环境检查、源码升级私有备份、失败回退与卸载预览。

黑块显示问题仍未关闭。其他系统的完整桌面登录、Android 后台服务、文件提供器和实际安装更新需实体设备验收。

## 0.5.0-beta.2

- Added a three-step setup guide: server address, device pairing and read-only feature checks.
- Added credential-free HTTPS diagnostics with DNS, certificate, timeout, redirect and endpoint hints.
- Kept manual pairing available for older backends without the diagnostic endpoint.
- Preserved unsaved addresses when refreshing settings and ignored outdated diagnostic responses.
- Clarified expired pairing codes and pairing retry limits.
- Added browser regressions for setup, stale requests and narrow-screen layouts.

Remote-desktop edge black regions remain unresolved. Desktop protocol support and physical keyboard support are unchanged.

## 0.5.0-beta.1

First public test release.

- Android app with an editable HTTPS endpoint and per-device pairing.
- Live system metrics, sampling history, alerts and a health summary.
- Automatic service/container discovery, configured controls and logs, and one-time confirmation to stop eligible running applications.
- Process memory/CPU views and guarded application termination.
- File uploads, downloads, renaming and trash/restore in an isolated directory.
- Optional GNOME Remote Login/RDP desktop with landscape fullscreen and adaptive resolution.
- Storage analysis, limited cache cleanup, configuration backup and custom application links.
- User-service installation and receipt-based removal of optional components.
- Local tests, GitHub Actions checks and Android development builds.

Known issues:

- Pointer movement to desktop edges/corners can produce a black area on some Android devices. Diagnostic sampling is included; the rendering issue is not fixed.
- Raspberry Pi OS VNC/WayVNC and hardware keyboard passthrough are not implemented.
- Test APKs use development signing. The app icon has separate, uncleared third-party branding rights.
