# SPDX-License-Identifier: Apache-2.0
"""Strict file API dispatch, including named roots and resumable transfers."""
import hashlib
from control import ApiError
from files import MAX_FILE

def dispatch(method,path,data,owner,registry,control):
 if registry is None:raise ApiError('文件区不可用',503)
 action=path.removeprefix('/api/files/')
 if method=='GET' and action=='roots':return registry.roots() if hasattr(registry,'roots') else {'roots':[{'id':'default','name':'独立文件区','writable':registry.writable,'max_file_bytes':MAX_FILE}]}
 body=dict(data);root=body.pop('root','default')
 if hasattr(registry,'space'):space=registry.space(root)
 elif root=='default':space=registry
 else:raise ApiError('此后端尚未配置这个文件目录',403)
 if method=='GET' and action=='list':return space.list('')
 if method=='GET' and action=='trash':return space.trash_list(owner)
 if method!='POST':raise ApiError('接口不存在',404)
 fields=set(body)
 if action=='trash/list' and not fields:return space.trash_list(owner)
 if action=='list' and fields=={'path'}:return space.list(body['path'])
 if action=='stat' and fields=={'path'}:return space.stat(owner,body['path'])
 if action=='read' and fields=={'path','offset','ticket'}:return space.read(owner,body['path'],body['offset'],body['ticket'])
 if action=='upload/status' and fields=={'id'}:return space.upload_status(owner,body['id'])
 if action=='uploads' and not fields:return space.resumable(owner)
 if action=='upload/start' and fields in ({'directory','name','size'},{'directory','name','size','request'}):return space.create_upload(owner,body['directory'],body['name'],body['size'],body.get('request'))
 if action=='upload/chunk' and fields=={'id','offset','data'}:return space.append(owner,body['id'],body['offset'],body['data'])
 if action=='upload/abort' and fields=={'id'}:space.abort(owner,body['id']);return {'ok':True}
 space.write_check()
 if action=='upload/finish' and fields=={'id','sha256','request'}:
  space.ident(body['id']);return control.enqueue(owner,'upload-'+body['id'],'upload',body['request'],lambda:space.finish(owner,body['id'],body['sha256']))
 if action=='mkdir' and fields=={'path','name','request'}:return control.enqueue(owner,'files-mkdir-'+root,'mkdir',body['request'],lambda:space.mkdir(body['path'],body['name']))
 if action in ('rename','trash') and fields==({'path','name','ticket','request'} if action=='rename' else {'path','ticket','request'}):
  resource='file-'+hashlib.sha256((root+':'+str(body['path'])).encode()).hexdigest()[:20]
  job=(lambda:space.rename(owner,body['path'],body['name'],body['ticket'])) if action=='rename' else (lambda:space.trash(owner,body['path'],body['ticket']))
  return control.enqueue(owner,resource,action,body['request'],job)
 if action=='restore' and fields=={'id','request'}:
  space.ident(body['id']);return control.enqueue(owner,'trash-'+body['id'],'restore',body['request'],lambda:space.restore(owner,body['id']))
 if action=='batch-trash' and fields=={'items','request'}:return control.enqueue(owner,'files-batch-'+root,'trash',body['request'],lambda:space.batch_trash(owner,body['items'],body['request']))
 raise ApiError('无效文件请求')
