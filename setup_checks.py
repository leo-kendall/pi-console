# SPDX-License-Identifier: Apache-2.0
"""Read-only setup hints. Configuration presence is not a live service probe."""
import json,os,stat
from desktop import certificate_pin
from control import ApiError


def desktop_check(root):
 path=root/'remote-desktop/connection.json'
 try:
  fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 except FileNotFoundError:
  return 'optional','未配置桌面；不影响监控和其他管理功能。'
 except OSError:
  return 'attention','桌面配置无法安全读取，请检查配置文件及权限。'
 try:
  with os.fdopen(fd,'rb') as stream:
   info=os.fstat(stream.fileno())
   if not stat.S_ISREG(info.st_mode) or info.st_mode&0o077 or info.st_size>65536:
    return 'attention','桌面配置权限或文件类型异常，请在服务器检查。'
   payload=stream.read(65537)
   if len(payload)>65536:raise ValueError()
   config=json.loads(payload)
   if not isinstance(config,dict) or any(not isinstance(config.get(k),str) or not config[k] for k in ('username','password','fingerprint')):raise ValueError()
   certificate_pin(config['fingerprint'])
 except (OSError,ValueError,TypeError,ApiError):
  return 'attention','桌面配置不完整或格式异常，请在服务器检查。'
 return 'configured','已找到 GNOME/RDP 配置；尚未验证桌面服务、桥接和登录是否可用。'


def report(root,resources,admin_ready):
 state,detail=desktop_check(root)
 return {'checks':[
  {'id':'resources','title':'服务与容器授权','state':'configured' if resources else 'optional',
   'detail':f'持久授权清单包含 {len(resources)} 个对象；实际操作仍会检查对象与权限。' if resources else '自动发现仍可使用；持久启停和日志授权尚未配置。'},
  {'id':'process_admin','title':'其他用户的应用进程','state':'configured' if admin_ready else 'optional',
   'detail':'管理员执行器文件已安装；实际权限以操作时校验为准。' if admin_ready else '未安装管理员执行器；同用户应用可按进程规则结束，系统基础进程始终只读。'},
  {'id':'desktop','title':'远程桌面','state':state,'detail':detail}
 ]}
