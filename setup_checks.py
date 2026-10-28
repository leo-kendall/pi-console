# SPDX-License-Identifier: Apache-2.0
"""Read-only setup hints. Configuration presence is not a live service probe."""
from desktop import capabilities


def desktop_check(root):
 config=capabilities(root)['configuration']
 if config['state']=='unconfigured':return 'optional','未配置桌面；不影响监控和其他管理功能。'
 if config['state']!='configured':return 'attention','桌面配置缺失、权限或格式异常，请在服务器检查。'
 return 'configured','已找到 '+config['protocol'].upper()+' 本机桌面配置；尚未验证桌面服务、桥接和登录是否可用。'


def report(root,resources,admin_ready):
 state,detail=desktop_check(root)
 return {'checks':[
  {'id':'resources','title':'服务与容器授权','state':'configured' if resources else 'optional',
   'detail':f'持久授权清单包含 {len(resources)} 个对象；实际操作仍会检查对象与权限。' if resources else '自动发现仍可使用；持久启停和日志授权尚未配置。'},
  {'id':'process_admin','title':'其他用户的应用进程','state':'configured' if admin_ready else 'optional',
   'detail':'管理员执行器文件已安装；实际权限以操作时校验为准。' if admin_ready else '未安装管理员执行器；同用户应用可按进程规则结束，系统基础进程始终只读。'},
  {'id':'desktop','title':'远程桌面','state':state,'detail':detail}
 ]}
