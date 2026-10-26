# SPDX-License-Identifier: Apache-2.0
"""Read-only POST dispatch. Caller MUST authenticate and enforce resource grants.

Route only POST for PATHS; shared router keeps its role enforcement at the boundary.
"""
from control import ApiError
PATHS=frozenset(('/api/logs/tail','/api/processes/history'))
def dispatch(path,data,owner,logs,processes):
 if not isinstance(data,dict):raise ApiError('无效请求')
 if path=='/api/logs/tail':
  if not {'resource'}<=set(data) or not set(data)<={'resource','cursor'}:raise ApiError('无效日志请求')
  return logs.tail(owner,data['resource'],data.get('cursor'))
 if path=='/api/processes/history':
  if set(data)!={'pid','start'}:raise ApiError('无效进程历史请求')
  return processes.history(data['pid'],data['start'])
 raise ApiError('接口不存在',404)
