# Pi Console 能做什么

Pi Console 把 Android 手机变成自己 Linux 主机的随身控制台。一个实用场景是利用闲置手机，给树莓派或家里的小服务器提供日常远程屏幕：打开桌面程序、改设置、查看任务，减少专门接一台显示器的需要。横屏使用，再接蓝牙或 USB 键盘鼠标，更接近小型工作台。

## 一个 App 处理常见维护

| 需要做的事 | Pi Console 提供的能力 |
| --- | --- |
| 看主机是否健康 | CPU、内存、磁盘、网络等状态、历史趋势与告警；支持手动开启后台提醒 |
| 找到应用或服务 | 自动发现本机 systemd 服务和 Docker 容器，筛选、搜索、查看授权日志 |
| 处理卡住的任务 | 按角色和授权启停具体对象，查看进程及实际影响；危险操作需要确认，关键系统对象受保护 |
| 传文件 | 管理管理员开放的目录；上传、下载、暂停/继续、批量操作和回收恢复，写入同时受目录权限与设备角色限制 |
| 操作图形界面 | 通过已配置的本机 RDP/VNC 桌面服务，在手机显示远程桌面并使用触控、物理键盘鼠标 |
| 打开自己的 Web 应用 | 自行添加常用网站和应用入口，和主机维护功能放在一起 |
| 管理多台机器 | 最多保存 32 台 HTTPS 服务器，每台有独立配对、入口和外观，一次连接一台 |

具体指标和提醒见[监控说明](observability.md)，文件传输的恢复条件见[文件说明](file-transfers.md)。自动发现只代表看见对象，持久控制仍需明确授权，见[自动发现说明](auto-discovery.md)。

## 手机作为屏幕和输入设备

远程桌面提供自动尺寸、固定像素预设、自定义尺寸和 16:9、16:10、4:3、3:2、21:9 等比例选择。连接中也能应用显示设置，画面等比显示；远端是否能改变分辨率由桌面服务决定。手机旋转时，固定尺寸保持原请求，自动尺寸按可用区域计算。

触控可用于移动、点击和拖动。物理键盘支持常用组合键、方向键和 F1–F12；控件提供 Ctrl/Alt/Shift/Super 锁定键。App 在前台且桌面活动时，**Ctrl+Alt+空格**可切换键鼠控制手机或远程桌面，也可用界面按钮切换。软键盘通过文字输入框发送。纯文本剪贴板按按钮传输，不会持续读取手机剪贴板。

它适合已联网、桌面服务可用后的日常 GUI 工作。它不是 HDMI 采集卡，无法显示 BIOS/固件或 RDP/VNC 启动之前的开机画面；初次装系统和网络救援仍需要备用管理通道。远程桌面可能是独立会话，也可能共享当前桌面，取决于主机服务。画面延迟、文本清晰度和交互体验受网络、手机 GPU/WebView 及服务器负载影响，不能承诺替代所有本地显示器场景。

## 自己部署、自己决定权限

后端运行在自己的 Linux 主机上，手机只连接自己填写的 HTTPS 地址。发布的 APK 不预置个人服务器地址、配对令牌或桌面密码。设备凭证用 Android Keystore 加密存储；服务器配置和运行数据保存在各自部署中。应用的手动“检查官方更新”会访问 GitHub，自己添加的网站也有各自的外部连接。

一次性配对码代替在手机保存 Linux 管理员密码。服务器支持管理员、操作员和只读角色，可命名设备、单独撤销授权；控制具体服务、文件目录和可选管理员功能由主机部署者决定。这是供可信操作者使用的自托管控制台，角色不提供独立租户的数据隔离。

## 使用前要知道

- APK 面向 **Android 8.0+**，同时需要可运行当前界面的 WebView；请启用并更新 Android System WebView 或 Chrome。支持范围按系统与实际能力判断，不能根据品牌承诺全部手机可用；现有测试不等于大规模实体手机兼容认证。
- 基础监控需要 Python 3.11+ 和可用的 Linux 用户服务环境；图形桌面、Docker 与 root 辅助执行器按需配置。
- 桌面需要已经配置好的图形会话与兼容的本机 RDP 或经典 VNC。WayVNC 只支持兼容的 None/经典密码模式，VeNCrypt、TLS、RA2 等 VNC 模式不支持，不会自动降低服务器认证要求。
- 公网、局域网和 VPN 均可接入；必须使用手机系统信任的 HTTPS 证书并保留配对鉴权。仅导入用户 CA 不保证 App 信任，Tailscale 不是 App 必需条件。
- 当前分发的是 Android APK，没有 iOS 版本。项目仍处于测试版，应先在自己的主机和手机上验收。

从[部署指南](deployment.md)和 [Android 兼容说明](android-compatibility.md)开始；让 AI 协助时提供[部署运行手册](deployment-ai.md)。代码采用 Apache-2.0，当前图标有独立的权利限制，分发与商用请保留并遵守[商业使用说明](commercial-use.md)中的声明。

## English overview

Pi Console turns an idle Android phone into a personal Linux console. With a configured graphical session and compatible local RDP or classic VNC server, the phone can act as a daily remote screen, touchpad, and keyboard/mouse gateway for a Raspberry Pi or another Linux host, reducing the need for a separate monitor for routine GUI work.

One app brings together host monitoring, authorized service/container control, logs, files, web app shortcuts, and remote desktop. Desktop resolution and aspect ratio can be adjusted before or during a session, subject to server support. While the app is in the foreground with an active desktop, Ctrl+Alt+Space switches physical keyboard/mouse control between the phone and remote desktop.

The app targets Android 8.0+ with a capable, updated WebView; this is a capability requirement, not blanket certification of any phone brand. HTTPS with a system-trusted certificate is required over public networks, LAN, or VPN. Desktop is not HDMI capture and cannot show firmware or early boot. Keep SSH or another recovery path. See the [deployment guide](deployment.md), [desktop compatibility](desktop-compatibility.md), and [license/icon notice](commercial-use.md).
