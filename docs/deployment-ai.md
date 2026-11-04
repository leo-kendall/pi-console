# AI/LLM 部署运行手册

供有终端访问权限的 AI 助手逐步执行。人类说明见[部署指南](deployment.md)，桌面协议细节见[兼容范围](desktop-compatibility.md)。本手册不是一键部署脚本；示例地址、路径、用户名及版本必须替换，不能把示例当作真实环境。

## 输入与默认值

开始前建立部署记录，仅保存必要的非秘密信息：

```yaml
source_repository: https://github.com/leo-kendall/pi-console
release_tag: REQUIRED
install_path: REQUIRED
linux_user: REQUIRED
os_distribution_and_version: REQUIRED
cpu_architecture: detect
https_base_url: REQUIRED
network_scope: REQUIRED  # public | lan | vpn
alternate_https_base_url: null  # 可选：同一后端的第二条入口
alternate_network_scope: null
proxy_type_and_config_path: discover_or_ask
certificate_method: discover_or_ask
phone_android_and_webview: discover_or_ask
components:
  backend: true
  container_control: false
  process_helper: false
  system_service_helper: false
  desktop: false
  linger: false
desktop_protocol: null  # rdp | vnc，桌面开启时必填
desktop_service_and_session: null
desktop_loopback_port: null
rdp_security_and_verified_fingerprint: null
vnc_security_mode: null
private_desktop_json_path: null
existing_deployment_and_receipts: discover
authorized_scope: retain_existing_session_authorization
```

默认只部署普通用户后端和 HTTPS 连接，不启用 root 助手、桌面、Docker 权限变更或 linger。默认监控 `/`，不授予服务持久控制，不开放系统目录写入。APK 使用官方同版本 Release 固定签名包，不以 CI debug 包替代。

用户名、安装路径、域名/HTTPS 地址和 Linux 发行版版本先从现有环境与授权上下文获取；仍无法确定时必须询问，不可猜测。请求桌面时，协议、桌面服务/会话类型及认证模式也必须确定。没有可用域名/可信证书方案时可继续本机后端准备，但不能宣称手机部署完成。密码、令牌、配对码和私钥只走用户的私有本地输入渠道，不要求粘贴进聊天。

## 授权、前置检查与停止条件

沿用当前会话中用户已授予的操作范围，不对已授权步骤反复索要批准。新增破坏性、不可逆或超出范围的操作才单独说明具体变更及原因。保持一个可用的 SSH/其他管理通道；不要注销当前桌面、清空应用数据或更换 APK 签名来绕过问题。

满足以下条件才执行安装：目标为受用户管理的 Linux；普通用户有安装目录写权限；Python 3.11+ 和时区数据可用；托管用户服务会话可用；确认目录没有其他部署或未知所有权冲突。发行版包管理器命令应依据实际 OS 的官方说明选择，不能把一套 GNOME/xrdp/WayVNC 安装命令应用到所有发行版。

立即停止受影响步骤并报告可复核原因：

- 缺失关键输入、凭据来源不可信，或计划超出授权范围。
- 现有服务、端口、代理站点、文件或安装收据冲突；不得删除收据、扩大文件权限或覆盖他人配置。
- 源码/安装包摘要不匹配、来源无法确认、APK 签名不兼容或版本倒退。
- 必需环境检查失败、`systemctl --user` 总线不可用、升级事务未恢复。
- HTTPS 证书链或名称校验失败；不得用 `curl -k`、禁用证书验证或纯 HTTP 手机入口绕过。
- 要求公开 RDP/VNC/guacd/18765 原始端口，或把未鉴权主机控制接口上线。
- 桌面不兼容、安全模式不支持、RDP 指纹未经可信通道核对；不得自动降低认证。

可选组件失败时保留已验证的基础监控，明确标记该组件未完成，不把全部功能标为通过。

## 执行顺序

每步记录退出码和脱敏结果；不要记录配置正文、Authorization、口令、二维码或协议载荷。不启用 shell `set -x`，不调用会直接打印桌面密码的 `remote-desktop/manage.py credentials`。命令出错时先诊断，不循环重试写操作。

### A. 发现环境并取得固定源码

以下只读检查可并行执行；检查结果中的本机用户名、路径、IP 不进入公开报告：

```sh
id -un
cat /etc/os-release
uname -m
python3 --version
/usr/bin/python3 --version
systemctl --user is-system-running
```

`degraded` 需要核对失败单元，不必假定整个用户管理器不可用。确认 `/usr/bin/python3` 也满足 3.11+，托管单元固定使用此路径。没有该目录且属于新安装时执行：

```sh
git clone https://github.com/leo-kendall/pi-console.git /path/to/pi-console
cd /path/to/pi-console
git checkout YOUR_RELEASE_TAG
git status --short
python3 -B maintenance.py doctor
```

将所有占位符替换为已确认输入。也可使用已核验官方源码 ZIP 解压得到的目录。已有安装进入原目录，走 G 节更新，不能反复 clone 或强行 checkout 未提交修改。预期 `doctor` 的必需检查通过；Docker 缺失只影响可选功能。`doctor` 不验证外部 HTTPS 或实际桌面登录。

### B. 配置并启动后端

没有本机配置时可使用默认值，或用[人类指南第 3 节](deployment.md#3-最小配置和启动)的独占创建方式生成 `0600` 最小 `config.json`。不要把完整示例中的虚构服务照抄为授权目标。已有文件保留并本地检查，只读取必要字段；禁止打印秘密配置。

```sh
python3 -B -c 'from config import SETTINGS; print("Configuration OK")'
python3 -B manage.py install
python3 -B manage.py install --apply
systemctl --user is-active pi-console.service
curl --fail --show-error http://127.0.0.1:18765/health
```

预期依次为配置通过、`Preview only`、安装退出码 0、`active`、`{"status":"ok"}`。首次安装命令没有成功文字，不能据此判定失败。`install --apply` 对匹配所有权的安装可重复执行，会启动服务，但不能保证重启已经运行的后端；配置变更后使用 `systemctl --user restart pi-console.service` 并重新检查健康。未知/被更改单元会被拒绝保留。

仅已要求未登录开机运行时执行：

```sh
sudo loginctl enable-linger YOUR_LINUX_USER
```

记录是否原已开启，卸载不能无条件关闭。不要把 Docker 加组、sudoers 或桌面安装作为基础部署的隐含步骤。

### C. HTTPS 入口

1. 读取现有代理的相关站点和网络策略，选择专用站点或路径，保留其他服务。根据实际代理生成具体可审阅配置；证书签发、DNS 和防火墙命令必须对应当前环境。不要直接覆盖全局配置。
2. 后端目标固定 `127.0.0.1:18765`。若使用仓库 Caddy 的 `/pi-console/` 路径，必须去掉该前缀后转发，手机基础 URL 保留此路径。
3. 启用手机系统信任且地址匹配的 HTTPS 证书。`.test` 仅是示例，不能当作真实公网签发域名。公网保留配对鉴权和访问/请求限流策略；LAN/VPN 也不豁免证书要求。
4. 先用代理自身的校验命令验证，再在现有授权范围内 reload。不得猜测配置文件路径或把 Tailscale 作为默认必装软件。仓库 Caddy 示例只允许 Tailscale/回环来源，其他网络需具体调整。
5. 用实际地址从目标网络执行：

```sh
curl --fail --show-error https://console.example.test/pi-console/health
curl --fail --show-error https://console.example.test/pi-console/api/connection
```

预期 HTTP 200，分别为 `status=ok` 与 `app=pi-console, protocol=1`。不能跟随到登录网页后当作 JSON 成功，不能增加证书忽略参数。公网代理若增加认证门，必须与原生客户端实际支持的连接方式匹配并验收，不能只验证浏览器登录。

**已要求 Tailscale／公网双入口时：**保留当前可用入口，核对两条代理都指向同一后端。发现 Tailscale 设备域名、已有 Serve/Funnel 配置及端口占用后，可在一个空闲的专用 HTTPS 端口提供第二入口；不要覆盖其他服务的 443，也不要用 `tailscale serve reset` 清空配置。以下仅是后端实际位于 `127.0.0.1:18765`、8443 空闲时的示例：

```sh
tailscale serve --bg --https=8443 http://127.0.0.1:18765
```

此例在 Tailscale 域名的 8443 根路径提供后端，App 的第二基础 URL 是 `https://YOUR_DEVICE.YOUR_TAILNET.ts.net:8443`，无需追加 `/pi-console`。Serve 仅用于 tailnet，不为此启用公网 Funnel。若命令要求账户首次启用 Serve／HTTPS，让账户所有者完成官方启用页；期间可继续检查现有入口，不能声称第二入口已可用。见 [Tailscale Serve 文档](https://tailscale.com/docs/reference/tailscale-cli/serve)。

从对应网络用正常 TLS 校验验证第二入口的 `/health`、`/api/connection` 和未鉴权 `/api/status`，分别预期 200、200、401；同时复查原公网入口。保存原代理配置，仅撤销自己新建且目标仍匹配的专用入口。让用户在 App“我的服务器”添加第二配置，各入口独立完成首次配对，之后手动切换；不导出、复制或在两个配置间挪用加密凭证。切换时桌面会断开、持续监控会停止。不要把另一个配置的首次配对说成每次切换都要重新配对。

### D. 安装 App、配对和只读验收

让用户在 Android 安装同版本官方 Release APK，并确认 Android 8.0+、WebView 可用，按 [Android 兼容说明](android-compatibility.md)验收实际能力。Android 系统安装确认是用户操作。已有同签名包可覆盖更新；签名不符时停止，不自动卸载。

App 输入实际 HTTPS 基础 URL，先检测再保存。在地址对应的后端目录执行一次：

```sh
python3 -B control.py pair
```

只在私有终端让用户读取 8 位码并在十分钟内输入 App；公开报告用 `[REDACTED]`。此命令有状态变化：会替换旧的未使用配对码，不能作为循环健康探测。CLI 不支持 `--role`；管理员可在手机生成其他角色的配对码。已有有效配对无需重新生成。

用 App“检查连接与功能”读取状态和鉴权 `/api/setup`，再查看监控。该检查不证明 sudo 实际执行或桌面登录成功。需要只读设备时，由管理员在配对设备页设置角色；不要为测试而降级最后一台管理员。

### E. 可选控制分支

只有明确需要相应能力时执行已授权的安装。每个组件先预览，确认精确用户，再安装：

```sh
sudo /usr/bin/python3 -I -B process-control/manage.py preview
sudo /usr/bin/python3 -I -B process-control/manage.py install --user YOUR_LINUX_USER
sudo /usr/bin/python3 -I -B system-control/manage.py preview
sudo /usr/bin/python3 -I -B system-control/manage.py install --user YOUR_LINUX_USER
```

不需要两个组件时只执行对应的一组。安装创建受限 root 助手和 sudoers，不提供任意命令。安装器核对已有资源/记录；未知修改时停止。服务/容器发现不自动授予持久控制；用明确对象、明确动作授权。对用户指定的可中断测试对象验证操作，不停止数据库、网络、当前管理通道或关键系统对象来做烟测。

文件目录由本地 `file_roots` 配置，写入还受角色限制；`storage_roots` 只用于空间分析。变更配置后重启后端并验收，见[配置说明](configuration.md)。

### F. 可选远程桌面分支

必须已知：实际桌面服务、图形会话、Linux 账号、协议、本机端口、认证模式、RDP 的可信指纹、可用 Docker 和目标镜像架构。没有图形会话则先报告缺失；安装图形桌面属于单独的 OS 相关任务，不能靠桥接替代。

**已有 RDP/VNC：**在主机私有文件中准备符合[兼容说明](desktop-compatibility.md)的 JSON。密码不进入参数、聊天或日志；文件须为 `0600`。服务必须限制在本机可达，目标只接受字面值 `127.0.0.1` 或 `::1`。

```sh
python3 -B remote-desktop/configure.py preview < /private/path/desktop.json
python3 -B remote-desktop/configure.py configure < /private/path/desktop.json
python3 -B remote-desktop/configure.py probe
python3 -B bridge_manage.py install
python3 -B bridge_manage.py status
```

预期预览 `credential_file=unchanged`，配置 `created-private`，桥接安装监听 `127.0.0.1:14822`，状态 `present=true, state=running, receipt=true`。`configure` 为只创建：重跑会拒绝已有文件，已有正确配置应跳过；需要修改时先私有备份再本地编辑，不删除后重试。VNC probe 只查协议/安全类型；RDP 的 `requires-guacd-connect` 不是认证成功。桥接安装可复用匹配记录的已运行容器，遇到外来容器拒绝；首次可能下载固定 digest 镜像。

**GNOME 安装器：**仅在用户选择且满足已有 GNOME Remote Login、`grdctl`、OpenSSL、nftables、桌面账号和 Tailscale 条件时使用：

```sh
sudo /usr/bin/python3 -I -B remote-desktop/manage.py preview
sudo /usr/bin/python3 -I -B remote-desktop/manage.py install --user YOUR_LINUX_USER --address YOUR_TAILSCALE_IP
```

预览只是计划，不是完整环境验证。此分支会改 GNOME 配置与防火墙，不是通用 xrdp/WayVNC 安装器；它不安装软件包。已有配置、活动 RDP 或端口冲突时改用通用接入，不能强行覆盖。随后仍需安装桥接。

最后由手机真实连接桌面，验收 RDP 证书/账号、四角触控、文字/物理键鼠、前台 Ctrl+Alt+空格切换、旋转、自动/固定/比例设置与连接中应用。尺寸以远端确认值为准。WayVNC 只有兼容的单一 None/经典密码模式；VeNCrypt/TLS/RA2 等模式拒绝即为范围限制，不能自动降级。不要强制注销已有桌面或公开桌面端口。

### G. 更新、备份与回退

保留备用管理通道。私下备份本机配置、`state/`、`data/`、桌面文件及真正的用户数据；项目外配置另备份。核验官方源码包后：

```sh
python3 -B maintenance.py doctor
python3 -B maintenance.py upgrade /path/to/pi-console-source-VERSION.zip
python3 -B maintenance.py upgrade /path/to/pi-console-source-VERSION.zip --apply --restart
```

`--restart` 仅用于项目安装器管理且收据匹配的服务。记录输出 `backup`，升级后重新执行本机/HTTPS/手机验证。内部备份包括被替换源码及若干私有配置，不包含所有上传文件、照片或数据库；备份不是公开发布物。重复升级可能再建备份，不能把它当成无副作用的状态查询。

失败时先确认工具自动恢复结果；必要时使用具体回退编号：

```sh
python3 -B maintenance.py rollback BACKUP_ID
python3 -B maintenance.py rollback BACKUP_ID --apply --restart
```

回退只恢复所替换源码，不回滚后续手机授权/用户数据；检测到手工源码修改或收据变化会停止。不要删除 `state/maintenance` 绕过检查。反向代理变更按部署前保存的该站点配置单独恢复；源码回退不还原代理或 OS 组件。手机 APK 回退受 Android 版本与签名限制，不自动卸载或强行降级。

卸载先运行 `python3 -B maintenance.py uninstall-preview`，再按[卸载说明](uninstall.md)仅移除本次实际安装且有记录的组件。默认保留私有数据，不自动删除 VPN、DNS、共享镜像、软件包、用户文件或 linger。

## 最终验收与交付

| 检查 | 通过标准 | 未通过时 |
| --- | --- | --- |
| 后端 | 普通用户服务 active；本机 `/health` 为 ok | 停止上线，检查服务/配置 |
| HTTPS | 目标网络证书校验通过；健康及身份 JSON 正确 | 不配对、不绕过 TLS |
| 手机基本功能 | 官方 APK 启动；地址检测、配对及状态读取成功 | 记录 Android/WebView 和脱敏错误 |
| 角色 | 管理员保留；需要的只读设备不能写入 | 不交付扩大权限的临时设置 |
| 可选控制 | 指定安全对象操作成功、未授权对象保持限制 | 标注该组件未验证 |
| 可选桌面 | 真实会话、证书认证、触控/键鼠/旋转/尺寸通过 | 基础监控可交付，桌面标记未完成 |
| 更新恢复 | 记录当前版本、备份位置/编号和管理入口 | 保留现场，不清理恢复记录 |
| 公共材料 | 无真实域名/IP、个人路径、令牌、密码或密钥 | 脱敏后再分享 |

交付报告列出部署版本、实际启用的组件、验证结果、跳过项及原因、私有备份位置、回退/卸载入口。自动化测试、模拟协议或 APK 编译通过不能代替真实手机/发行版认证。保留[商业使用说明](commercial-use.md)中的 Apache-2.0 及图标权利例外，不替用户推定额外授权。
