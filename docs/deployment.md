# 部署

## 基础环境

- Linux、Python 3.11+、systemd 用户会话；后端以普通用户运行。
- Android 8.0+ 与近期 Android System WebView。
- 提供手机可访问、证书受系统信任的 HTTPS 入口；支持公网、局域网或 VPN，Tailscale 是可选部署方式。
- Docker 仅用于可选容器管理及 guacd；加入 Docker socket 用户组等同于授予很高的主机权限，应由部署者自行决定。

仓库可放在普通用户拥有的目录中。路径含换行、引号、美元符号、反斜杠或 `%` 时，安装器会拒绝生成 systemd 单元。

## 配置

`config.json` 是本机文件，已被 Git 忽略。也可用 `PI_CONSOLE_CONFIG` 指定其他路径。配置有未知字段、重复键或非法目标时后端拒绝启动；卸载入口不依赖配置解析成功。

`resources` 默认空，只有显式加入的资源可启停。`kind=user` 指 systemd 用户服务，目标须为 `.service` 单元；`container` 指精确容器名称。`system` 仅支持固定辅助对象 `display → pi-console-display.service` 和 `printer → cups-browsed.service`，不能传入任意系统单元。

已安装的服务与容器会自动扫描并显示，新增对象不自动获得持久控制权限，但符合条件的运行对象可以单次确认结束；不需要先填配置才能看见。只有控制授权变更才需要修改 `resources` 并重启；发现新对象不需要手动改清单。详见[自动发现](auto-discovery.md)。

`storage_roots` 决定只读空间分析的可选目录，不授予任意路径删除权限。`disks` 是需监控的实际挂载点列表，默认只有 `/`。删除监控对象后重启服务会协调旧告警。配置文件不保存密码。

`name` 为手机显示的服务器名称；`desktop_timezone` 为远程桌面时区，默认 `UTC`，可改为系统时区库中的名称，例如 `Europe/Berlin`。各部署者使用自己的 `config.json` 和运行数据，不随源码或 APK 分发。详细首次配置流程见 [个人配置说明](configuration.md)。

## 启动与配对

先用运行后端的 Linux 用户进入当前 HTTPS 入口对应的项目目录（包含 `server.py` 和 `control.py`）。将示例路径替换为自己的安装目录；本页其余相对路径命令也在这个目录中执行。

```sh
cd /path/to/pi-console
python3 -B manage.py install
python3 -B manage.py install --apply
systemctl --user status pi-console.service
python3 -B control.py pair
```

开机且未登录时继续运行用户服务，需要系统管理员显式启用该用户的 linger：

```sh
sudo loginctl enable-linger YOUR_LINUX_USER
```

安装器不会自行改变 linger，卸载也不会关闭用户原先拥有的 linger。反向代理由部署者管理，Caddy 示例只展示本项目站点并默认限制 Tailscale 私网；公网或其他局域网部署需显式调整网络访问规则，配置 HTTPS、访问控制及请求限流。后端仍监听回环地址，RDP/guacd 也不应直接开放到公网。不要覆盖已有站点配置。调试可用 `curl http://127.0.0.1:18765/health`。

App 设置中填写完整 HTTPS API 基础地址，再输入一次性配对码。配对码十分钟有效且只能使用一次；最多十六台配对设备。`python3 -B control.py revoke-all` 撤销所有设备。

## 可选管理员功能

结束其他用户的应用进程需要单独安装受限执行器：

```sh
sudo /usr/bin/python3 -I -B process-control/manage.py install --user YOUR_LINUX_USER
```

只对核验后的单个进程发送 SIGTERM；无任意命令、信号或进程组接口。结束数据库、远程连接或控制台应用仍会中断其工作；托管程序可能自动重启。这个权限具有实际影响，不应把配对令牌授予不可信用户。

固定辅助系统服务的执行器单独安装：

```sh
sudo /usr/bin/python3 -I -B system-control/manage.py install --user YOUR_LINUX_USER
```

这些安装器使用 root 所有的文件、sudoers 和恢复记录。预先存在、被更改或不属于本项目的文件会保留。普通监控及同用户进程无需这些授权。

## 可选远程桌面

当前方案依赖已安装并支持 Remote Login 的 GNOME Remote Desktop、`grdctl`、OpenSSL、nftables、可用的桌面账户与 Docker。是否可用取决于桌面后端及版本，不能仅按 Ubuntu 或其他发行版名称判断。Raspberry Pi OS 默认桌面和其他 VNC/WayVNC、xrdp 环境尚未集成适配；请先查看[远程桌面兼容范围](desktop-compatibility.md)，再决定是否适用本安装器。

```sh
sudo /usr/bin/python3 -I -B remote-desktop/manage.py preview
sudo /usr/bin/python3 -I -B remote-desktop/manage.py install --user YOUR_LINUX_USER --address YOUR_TAILSCALE_IP
python3 -B bridge_manage.py install
```

安装器拒绝覆盖已有 RDP 配置/凭据及已占用端口。桥接只监听 `127.0.0.1:14822`；RDP 的主机防火墙限制为本机及 Tailscale。不要将 guacd 暴露到公网。独立会话与已有本地桌面可能冲突，强制结束旧会话会关闭该桌面的应用和未保存工作。

已有其他 GNOME/RDP 部署时，先阅读 `remote-desktop/manage.py` 的预览及前置检查，自行适配现有部署；不要为了通过安装检查而删除别人的配置。当前 guacd 镜像固定 digest，跨架构兼容性应在目标机器上确认。
