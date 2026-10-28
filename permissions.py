# SPDX-License-Identifier: Apache-2.0
"""Role policy shared by all API entry points; POST is writable by default."""
LEVELS={'viewer':0,'operator':1,'admin':2}
READ_POST={'/api/files/list','/api/files/stat','/api/files/read','/api/files/roots','/api/files/trash/list','/api/files/upload/status','/api/files/uploads','/api/logs/tail','/api/processes/history','/api/devices/rename','/api/unpair'}
ADMIN_PATHS={'/api/devices','/api/devices/revoke','/api/devices/role','/api/devices/pair-code','/api/grants','/api/grants/set','/api/grants/remove','/api/audit'}

def route_role(method,path):
 if path in ADMIN_PATHS:return 'admin'
 if method=='GET' or method=='POST' and path in READ_POST:return 'viewer'
 return 'operator'

def valid_name(value):
 return isinstance(value,str) and 1<=len(value)<=64 and not any(ord(c)<32 or ord(c)==127 for c in value)
