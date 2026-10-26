# SPDX-License-Identifier: Apache-2.0
"""Host OS essentials are read-only; applications have no executable allowlist."""
from pathlib import Path
import re

# These are host operating-system / current desktop-session foundations.
# Service ownership (root vs user) and being under system.slice are not reasons
# by themselves to forbid an application's termination.
CORE_NAMES={
 'systemd','init','systemd-udevd','systemd-logind','systemd-journald',
 'systemd-networkd','systemd-resolved','systemd-oomd','systemd-timesyncd',
 'NetworkManager','dbus-daemon','dbus-broker','dbus-broker-launch',
 'gdm','gdm3','gdm-session-worker','gdm-wayland-session','gdm-x-session',
 'gnome-shell','gnome-session-binary','Xorg','Xwayland',
}
CORE_UNITS={
 'systemd-udevd.service','systemd-logind.service','systemd-journald.service',
 'systemd-networkd.service','systemd-resolved.service','systemd-oomd.service',
 'NetworkManager.service','wpa_supplicant.service','iwd.service','dhcpcd.service','dhclient.service',
 'gdm.service','gdm3.service','display-manager.service',
 'org.gnome.Shell@ubuntu.service','org.gnome.Shell@wayland.service',
 'org.gnome.Shell@x11.service',
}
CONTAINER_GROUP=re.compile(r'(?:^|/)(?:docker-[0-9a-f]{12,64}\.scope|docker/[0-9a-f]{12,64}|(?:cri-containerd|crio)-[0-9a-f]{12,64}\.scope)(?:/|$)')


def executable_name(p):
 return Path(p.get('exe','').removesuffix(' (deleted)')).name or p.get('name','').strip().split(':')[0]


def is_container(p):
 return bool(CONTAINER_GROUP.search(p.get('cgroup','')))


def critical_reason(p):
 if p['pid']<=1:return '系统初始化进程，结束会影响系统运行'
 if p.get('flags',0)&0x00200000:return '内核线程，属于系统运行基础'
 if is_container(p):return None
 group=p.get('cgroup','');units=group.split('/');name=executable_name(p)
 # A unit and a host role are required. Names alone do not confer core status,
 # and user applications are frequently activated inside dbus.service itself.
 if group.startswith('/system.slice/') and any(u in CORE_UNITS for u in units):return '系统核心、网络或图形登录基础服务，结束会影响正常运行'
 if any(u.startswith('org.gnome.Shell@') and u.endswith('.service') for u in units) and '/session.slice/' in group:return '当前桌面会话基础服务，结束会影响桌面正常运行'
 if group.endswith('/init.scope') and name in ('systemd','init'):return '系统或用户会话管理进程，结束会影响正常运行'
 if any(u in {'dbus.service','dbus-broker.service'} for u in units) and name in {'dbus-daemon','dbus-broker','dbus-broker-launch'}:return '系统或当前会话消息总线，结束会影响正常运行'
 trusted=p.get('trusted_exe',False) and p.get('exe','').startswith(('/usr/','/bin/','/sbin/','/lib/'))
 session_context='/session.slice/' in group or bool(re.search(r'/session-[0-9]+\.scope(?:/|$)',group)) or any(u.startswith('gnome-session-') and u.endswith('.service') for u in units)
 session_names=CORE_NAMES-{'dbus-daemon','dbus-broker','dbus-broker-launch'}
 if trusted and session_context and (name in session_names or name.startswith(('gnome-session','gdm-','gsd-'))):return '当前图形登录与桌面基础进程，结束会影响桌面正常运行'
 return None


def impact(p,parents=None):
 parts=[];names={executable_name(p),p.get('name','')};groups=p.get('cgroup','')
 parent_id=p.get('ppid');visited=set()
 while parents and parent_id in parents and parent_id not in visited:
  visited.add(parent_id);a=parents[parent_id];names.add(executable_name(a));groups+=' '+a.get('cgroup','');parent_id=a.get('ppid')
 if {'codex','codex-code-mode-host'}&names or 'codex-remote-control.service' in groups:parts.append('会中断关联的 Codex 任务或远程控制连接')
 if 'pi-console.service' in p.get('cgroup',''):parts.append('本 App 后台可能离线，需要通过 SSH 或树莓派终端重新启动控制台服务')
 if names&{'tailscaled','tailscale','sshd','ssh','mosh-server','gnome-remote-desktop','guacd','caddy','cloudflared','clash-verge','verge-mihomo'} or any(x in groups for x in ['codex-proxy.service','gnome-remote-desktop.service','clash-verge-service.service']):parts.append('可能中断网络、代理或当前远程连接')
 if is_container(p):parts.append('属于容器应用；关联功能会中断，容器或工作进程可能自动重启')
 if any(x in executable_name(p).lower() for x in ['postgres','mysqld','mariadb','redis']):parts.append('数据库连接会中断，依赖它的应用将暂时不可用')
 return '；'.join(parts)


def process_policy(p,parents=None,uid=None,protected=None):
 reason=critical_reason(p)
 if reason:return False,reason
 if p.get('state') in ('Z','X','x'):return False,'进程已经退出或等待回收，无法再次结束'
 if not p.get('uids'):return False,'进程身份不可用，请刷新后重试'
 return True,'非系统关键应用进程，可正常结束此 PID。未保存内容可能丢失；服务管理器或容器可能自动重启它。'
