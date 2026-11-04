# 部署指南：让闲置 Android 手机成为服务器控制台

先完成“后端 → HTTPS → 手机配对”，就能在手机上查看服务器状态。需要日常图形操作时再配置远程桌面：闲置手机可以作为树莓派或其他 Linux 主机的远程屏幕、触控板和键鼠入口，减少为日常 GUI 操作单独准备显示器的需要。

远程桌面依赖主机已有图形桌面和兼容的 RDP/VNC 服务。它不是 HDMI 采集，不能显示固件、开机早期画面或桌面服务尚未启动时的输出。首次装系统、网络故障和桌面恢复仍应保留 SSH、串口或临时显示器等管理入口。

给 AI 执行部署时使用[部署运行手册](deployment-ai.md)；功能与使用边界见[功能介绍](features.md)。

## 1. 准备环境

| 必需 | 要求 |
| --- | --- |
| Linux 主机 | Python 3.11+、系统时区数据、可用的 systemd 用户会话；以下托管安装流程以普通用户运行 |
| 手机 | Android 8.0/API 26 或以上；启用并更新 Android System WebView，部分系统由 Chrome 提供 WebView |
| 网络入口 | 手机可达的 HTTPS 地址，证书链受 Android 系统信任且与地址匹配；可使用公网、局域网或 VPN |
| 初始管理通道 | 可登录主机的终端，如 SSH；具有自己的普通 Linux 账户 |

Android 版本号只是安装下限。界面还需要实际 WebView 支持所用 JavaScript、布局及 Canvas 功能；旧组件即使能安装 APK 也可能无法运行。出现“需要更新网页组件”时，在系统设置、系统更新或可信应用商店启用/更新 WebView 或 Chrome，再点“重试”。无法更新组件的旧设备不能保证可用。支持目标面向符合条件的 Android 手机，不以小米或其他品牌名称作兼容认证；实体设备、GPU、刘海和系统快捷键仍需实际验收。具体条件见 [Android 兼容说明](android-compatibility.md)。

Docker、图形桌面和 root 辅助执行器均为可选项。基本监控不要求 Docker、Tailscale 或 GNOME。后端使用 Python 标准库，无需先安装 Android SDK 或构建 APK。容器管理需要后端用户能访问本机 Docker socket；这个权限很高，不要为消除提示而随意加组或放宽 socket 权限。

## 2. 获取 App 与后端

从[官方 GitHub Releases](https://github.com/leo-kendall/pi-console/releases)选择同一版本的发布 APK 和源码，测试版需主动选择相应 beta。优先安装发布页的 `pi-console.apk` 或 `pi-console-release.apk`，核对随包校验信息；安装来源权限由 Android 系统确认。GitHub Actions 的 debug APK 使用临时开发签名，不适合作为长期覆盖更新的安装包。自行构建见[构建说明](build.md)。

后端可解压官方源码包，也可克隆仓库。以下适用于尚未存在该目录的新安装；将版本占位符替换为发布页真实 tag，不要原样执行：

```sh
git clone https://github.com/leo-kendall/pi-console.git "$HOME/pi-console"
cd "$HOME/pi-console"
git checkout YOUR_RELEASE_TAG
python3 --version
/usr/bin/python3 --version
python3 -B maintenance.py doctor
```

预期两处 Python 都至少 3.11，环境检查必需项通过；托管服务固定使用 `/usr/bin/python3`。Docker 缺失是可选提示。已有部署请进入原目录并使用第 9 节升级流程，不要再次克隆覆盖它。目录应属于运行后端的用户；包含换行、引号、美元符号、反斜杠或 `%` 的路径不支持生成 systemd 单元。

## 3. 最小配置和启动

后续命令都在含 `server.py`、`control.py` 的后端目录执行，使用同一个普通 Linux 用户。首次可不创建配置，默认资源控制清单为空，磁盘监控为 `/`。需要命名服务器时，可创建最小配置；已有 `config.json` 时下面命令会拒绝覆盖：

```sh
python3 -B - <<'PY'
import json, os
fd = os.open('config.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as output:
    json.dump({'name': 'My server', 'resources': {}, 'disks': ['/']}, output, indent=2)
    output.write('\n')
PY
python3 -B -c 'from config import SETTINGS; print("Configuration OK")'
python3 -B manage.py install
python3 -B manage.py install --apply
systemctl --user status pi-console.service --no-pager
curl --fail --show-error http://127.0.0.1:18765/health
```

第一次 `install` 只显示预览；`--apply` 才写入并启动这个 checkout 的用户服务。预期服务为 `active (running)`，健康接口返回 `{"status":"ok"}`。后端仅监听 `127.0.0.1:18765`，此时手机尚不能直接连接它。不要用 sudo 安装后端。

若要求主机开机且用户未登录时也运行，经管理员确认该账户用途后执行：

```sh
sudo loginctl enable-linger YOUR_LINUX_USER
```

安装器不自行修改 linger。`systemctl --user` 提示无法连接总线时，应先修复该用户的登录/用户服务环境，不能用 root 服务替代来绕过问题。

## 4. 配置手机可达的 HTTPS

使用自己管理的 Caddy、Nginx 或其他 HTTPS 反向代理，将一个专用站点或路径转发到 `127.0.0.1:18765`。下面是与仓库示例一致的路径结构，仅供合并到现有代理配置；`console.example.test` 是不能直接申请公网证书的示例名，必须换成自己可管理、可签发可信证书的实际地址：

```caddyfile
console.example.test {
    handle_path /pi-console/* {
        reverse_proxy 127.0.0.1:18765
    }
    respond 404
}
```

此结构对应手机基础地址 `https://console.example.test/pi-console/`，代理移除 `/pi-console/` 前缀。若选择独立根路径站点，则基础地址和路由应一起调整。不要把 `/api`、`/health` 或 APK 内部的 `https://pi-console.local/` 填成基础地址。

实际启用入口前完成证书、网络访问策略和请求限流配置。公网必须保留配对鉴权并限制配对尝试；不能公开无认证的主机控制接口。局域网和 VPN 也需要手机信任的证书；仅在手机浏览器中点过证书例外或安装用户 CA，不代表 App 使用的系统信任链已经通过。不要关闭 TLS 校验。可在私网中使用实际域名及可验证的可信证书，DNS 指向手机能访问的私网地址。VPN 是可选方案。

[仓库 Caddy 示例](../deploy/Caddyfile.example)额外只允许 Tailscale/回环来源；直接复制到普通 LAN 或公网会返回 403。根据实际网络修改这一站点的规则，勿覆盖其他站点。代理软件的安装、DNS 和证书签发由部署者管理，项目安装器不会完成这些步骤。

在另一台可访问该入口的机器上进行只读检查；地址替换为自己的实际地址：

```sh
curl --fail --show-error https://console.example.test/pi-console/health
curl --fail --show-error https://console.example.test/pi-console/api/connection
```

预期分别为 `{"status":"ok"}` 与含 `"app":"pi-console","protocol":1` 的 JSON。不要加 `-k`。不要转发 18765、RDP/VNC 或 guacd 原始端口到公网。

## 5. 配对并验证手机

1. App 中打开“设置 → 服务器连接”，填写完整 HTTPS 基础地址，点“检测这个地址”。检测通过后保存。
2. 在该地址对应的后端目录，用运行后端的用户执行：

   ```sh
   python3 -B control.py pair
   ```

3. 将终端生成的 8 位码输入手机。配对码十分钟有效、仅用一次；重新生成会替换未使用的旧码。不要把码或配对令牌贴进公开日志。
4. 点“检查连接与功能”，确认状态可读，再查看监控页。检查不会启停服务、写配置或创建桌面会话；缺少可选执行器或桌面不代表基础连接失败。

本地 CLI 首次配对授予管理员角色。后续可在“工具箱 → 配对设备”命名设备、分配管理员/操作员/只读角色、生成指定角色的配对码及单独撤销设备；至少保留一台管理员。最多配对 16 台设备。丢失手机时从其他管理员设备撤销它，或在服务器执行 `python3 -B control.py revoke-all` 撤销全部配对。

需要在同一台树莓派的 Tailscale 与 Cloudflare 入口之间手动切换时，把两个实际 HTTPS 地址分别保存到“我的服务器”，各首次配对一次即可；以后直接切换配置。现有公网配置和配对可以保留。具体步骤见[双入口使用说明](profiles-updates.md#同一台服务器保存两条连接)。

## 6. 按需启用控制与文件

服务和容器会自动发现；被发现不等于已获持久控制授权。在手机“控制授权”中授予具体对象、具体动作，或配置本机 `resources` 清单。用户服务目标必须是确切的 `.service`，容器为确切名称；系统基础组件保持保护。配置中的 `system` 项仅接受固定辅助对象，其他符合条件系统服务的授权走受限执行器。见[自动发现](auto-discovery.md)。

普通监控和同用户进程不需要 root 辅助组件。确需结束其他用户的合格应用进程时，先预览，再安装 SIGTERM 受限执行器：

```sh
sudo /usr/bin/python3 -I -B process-control/manage.py preview
sudo /usr/bin/python3 -I -B process-control/manage.py install --user YOUR_LINUX_USER
```

确需控制符合策略的系统服务时，单独安装服务执行器：

```sh
sudo /usr/bin/python3 -I -B system-control/manage.py preview
sudo /usr/bin/python3 -I -B system-control/manage.py install --user YOUR_LINUX_USER
```

它们写入 root 所有的助手、sudoers 和恢复记录，没有任意 shell 接口。结束应用、停止服务仍可能丢失未保存工作或中断连接；托管进程也可能自动重启。安装拒绝未知或被改过的文件时，应核对所有权，不要删除记录强行继续。

`storage_roots` 是只读空间分析目录；`file_roots` 才决定文件页可浏览目录和是否可写，另受设备角色约束。不要把全盘开放成可写目录。字段、权限和重启要求见[配置说明](configuration.md)，传输和回收区见[文件说明](file-transfers.md)。

## 7. 把手机用作日常远程屏幕

先确认主机已经有图形桌面、可登录的桌面账号和兼容的本机 RDP 或 VNC 服务。Raspberry Pi OS、Ubuntu、Debian 等名称不能保证协议、认证模式和会话配置兼容；Lite/无桌面系统需要先装桌面。RDP 可能创建独立会话，VNC 是否共享当前桌面取决于服务；不要为了连接而强制注销正在工作的桌面。

通用接入流程适用于已配置的 GNOME RDP、xrdp 或兼容 VNC：

1. 按[远程桌面兼容说明](desktop-compatibility.md)创建私有 JSON。目标只允许 `127.0.0.1` 或 `::1`；RDP 必须有通过可信管理通道核对的完整 SHA-256 证书指纹。VNC 仅支持文档列出的单一 None/经典密码认证模式；不要为兼容关闭现有强认证。
2. 将配置放在服务器私有文件中，权限为 `0600`。替换下方示例路径，不在命令行、聊天或截图放密码。

   ```sh
   python3 -B remote-desktop/configure.py preview < /private/path/desktop.json
   python3 -B remote-desktop/configure.py configure < /private/path/desktop.json
   python3 -B remote-desktop/configure.py probe
   ```

   `preview` 不写入、不连接；`configure` 仅新建 `remote-desktop/connection.json`，拒绝覆盖。VNC 的 `probe` 不登录；RDP 返回 `requires-guacd-connect`，不能当成指纹与账号已验证。
3. 后端用户能访问 Docker、目标架构可运行固定 guacd 镜像时安装桥接：

   ```sh
   python3 -B bridge_manage.py install
   python3 -B bridge_manage.py status
   ```

   预期桥接监听 `127.0.0.1:14822`，状态为 running、有所有权记录。首次可能拉取固定 digest 镜像；Docker 权限或镜像架构错误应先解决，不要改成任意可变镜像。仅控制台 HTTPS 面向手机。
4. 手机进入桌面页连接，确认登录、四角点击、文字输入、旋转和断开重连。RDP 真实连接这一步才验证证书指纹及认证。
5. 在连接前或连接后“控件 → 显示设置”选择自动尺寸、固定预设或自定义尺寸和比例；连接中也可应用。固定尺寸不随旋转改变，画面保持等比。远端必须支持调整，以远端确认的实际尺寸为准，未确认时保留现有画面并提示。

手机触控可作触控板，也可连接蓝牙/USB 键盘鼠标。App 在前台且桌面活动时，**Ctrl+Alt+空格**在“远程桌面”和“手机”键鼠目标间切换；控件按钮也可切换。离开 App 后不是全局快捷键，Android 截留的系统按键不能保证送达。软键盘通过文字输入框发送；剪贴板仅在点击时传输纯文本，非自动同步。

### 可选：项目提供的 GNOME 安装器

这条分支只适用于已有支持 Remote Login 的 GNOME Remote Desktop、`grdctl`、OpenSSL、nftables、可用桌面账户及 Tailscale 的环境；不是通用桌面安装脚本，也不自动安装桌面或软件包。普通 LAN/公网控制台可使用前面的通用本机 RDP/VNC 配置，不必安装 Tailscale。

```sh
sudo /usr/bin/python3 -I -B remote-desktop/manage.py preview
sudo /usr/bin/python3 -I -B remote-desktop/manage.py install --user YOUR_LINUX_USER --address YOUR_TAILSCALE_IP
```

此安装器管理 GNOME Remote Login、证书与防火墙，仅允许本机及 Tailscale 访问 RDP。它拒绝已有 RDP 配置/凭据、活动服务或端口占用；预览说明不是成功的实际环境检查。已有桌面服务时使用通用配置，不要删除别人的配置来通过检查。随后仍需桥接并用手机验证。

## 8. 常见问题

| 现象 | 先检查 |
| --- | --- |
| APK 无法覆盖安装 | 官方固定签名、versionCode 是否更高；debug 和不同签名不能互相覆盖。卸载会丢失本机配对，先看[更新说明](profiles-updates.md) |
| 白屏或网页组件提示 | 更新/启用 WebView 或 Chrome 并重试；仍失败则核对同签名发布 APK、Android/WebView 版本，不以品牌判断 |
| 本机健康接口失败 | `systemctl --user status pi-console.service --no-pager`；用 `journalctl --user -u pi-console.service -n 80 --no-pager` 查看错误，分享前脱敏 |
| 本机健康但手机失败 | DNS、手机网络、证书链/名称、代理路径和访问规则；网页能打开不等于 API 路径正确 |
| 403 / 404 / 接口版本不符 | Caddy 示例私网限制、前缀是否移除、基础地址是否多写 `/api`；App 与后端是否同版 |
| 配对码无效或过期 | 在当前 HTTPS 入口对应的目录重新生成；确认非另一份 checkout，勿同时生成多次 |
| 监控正常但控制不可用 | 角色、对象授权、Docker 权限、可选助手和系统保护策略；功能检查不替代真实授权验证 |
| 桌面失败或黑屏 | 图形会话、协议/认证模式、本机端口、私有文件权限、RDP 指纹和 guacd；仅装 App 不会产生桌面 |
| 比例/旋转或鼠标位置异常 | 恢复自动尺寸，记录实际远端尺寸、Android/WebView 版本及脱敏显示诊断；远端尺寸响应和手机 GPU 需实测 |

## 9. 更新、备份、回退和卸载

升级前保留 SSH 等备用入口，私下备份 `config.json`、外部配置、`state/`、`data/`、桌面连接配置及用户文件。备份含设备身份和密码，不能发布到 GitHub。手机设置导出不含配对令牌，不能代替服务器备份。

下载并核对官方源码 ZIP 后，在原目录先预览升级；以下适用于安装器管理的用户服务：

```sh
python3 -B maintenance.py upgrade /path/to/pi-console-source-VERSION.zip
python3 -B maintenance.py upgrade /path/to/pi-console-source-VERSION.zip --apply --restart
```

记录输出中的 `backup` 编号。失败时工具会尝试还原源码并启动旧版；需要手工回退时：

```sh
python3 -B maintenance.py rollback BACKUP_ID
python3 -B maintenance.py rollback BACKUP_ID --apply --restart
```

升级备份不复制上传文件、照片或数据库，回退也不回滚后来新增的授权或用户数据。`PI_CONSOLE_CONFIG` 指向的项目外文件需单独备份。详见[维护说明](maintenance.md)。App 使用同签名官方包更新以保留配置；APK 与后端需要更新时分别执行和验证。

卸载先预览 `python3 -B maintenance.py uninstall-preview`，按[卸载说明](uninstall.md)依次移除实际安装的可选组件及用户服务。默认保留源码和私有数据，反向代理、DNS、VPN、共享软件包和 linger 由部署者按原记录处理。代码授权与图标例外见[商业使用说明](commercial-use.md)。
