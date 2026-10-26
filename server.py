# SPDX-License-Identifier: Apache-2.0
"""Loopback monitoring and authenticated control API for the Pi console."""

import argparse
import json
import os
from pathlib import Path
import socketserver
import stat
import sys
import threading
import time
from urllib.parse import urlsplit, parse_qs
from control import Control, ApiError
from desktop import Desktop
from telemetry import Telemetry
from processes import Processes
from alerts import Alerts
from storage import Storage
from files import Files
from health import report

sys.dont_write_bytecode = True
from metrics import collect_status
from config import SETTINGS
from resource_end import ResourceEnd,annotate_inventory


ROOT = Path(__file__).resolve().parent
APK = ROOT / "dist" / "pi-console.apk"
MAX_LINE = 2048
MAX_HEADERS = 8192
MAX_HEADER_COUNT = 32
MAX_JSON = 1024 * 1024
MAX_APK = 128 * 1024 * 1024
CACHE_SECONDS = 3.0


class StatusCache:
    def __init__(self):
        self.lock = threading.Lock()
        self.expires = 0.0
        self.payload = None

    def get(self):
        with self.lock:
            if self.payload is not None and time.monotonic() < self.expires:
                return self.payload
            sample = collect_status()
            sample["name"] = SETTINGS["name"]
            payload = json.dumps(sample, ensure_ascii=False, separators=(",", ":"),
                                 allow_nan=False).encode("utf-8")
            if len(payload) > MAX_JSON:
                raise ValueError("status response exceeds limit")
            self.payload = payload
            self.expires = time.monotonic() + CACHE_SECONDS
            return payload


CACHE = StatusCache()
CONTROL = None
PROCESSES = Processes()
ALERTS = None
STORAGE = Storage()
FILES = None
DESKTOP = None
RESOURCE_END = None
TELEMETRY = Telemetry()
RESOURCE_LOCK = threading.Lock()
RESOURCE_CACHE = [0, None]


class Handler(socketserver.StreamRequestHandler):
    timeout = 15

    def _reply(self, status, body=b"", content_type="text/plain; charset=utf-8",
               extra=()):
        reason = {200: "OK", 400: "Bad Request", 401:"Unauthorized", 403:"Forbidden", 404: "Not Found",
                  409:"Conflict",410:"Gone",429:"Too Many Requests",502:"Bad Gateway",504:"Gateway Timeout",
                  413: "Content Too Large", 503: "Service Unavailable"}[status]
        lines = [f"HTTP/1.1 {status} {reason}\r\n",
                 f"Content-Length: {len(body)}\r\n",
                 f"Content-Type: {content_type}\r\n",
                 "Cache-Control: no-store\r\n", "X-Content-Type-Options: nosniff\r\n",
                 "Connection: close\r\n"]
        lines.extend(extra)
        self.wfile.write("".join(lines).encode("ascii") + b"\r\n" + body)

    def _request(self):
        line = self.rfile.readline(MAX_LINE + 1)
        if not line or len(line) > MAX_LINE or not line.endswith(b"\r\n"):
            raise ValueError("request line")
        try:
            method, path, version = line[:-2].decode("ascii").split(" ")
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError("request line") from exc
        if version not in ("HTTP/1.0", "HTTP/1.1") or not path.startswith("/"):
            raise ValueError("request target")
        headers = {}
        total = 0
        for _ in range(MAX_HEADER_COUNT + 1):
            raw = self.rfile.readline(MAX_HEADERS - total + 1)
            total += len(raw)
            if total > MAX_HEADERS or not raw or not raw.endswith(b"\r\n"):
                raise ValueError("headers")
            if raw == b"\r\n":
                break
            if raw[:1] in (b" ", b"\t") or b":" not in raw or b"\x00" in raw:
                raise ValueError("headers")
            name, value = raw[:-2].split(b":", 1)
            if not name or any(c not in b"!#$%&'*+-.^_`|~0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz" for c in name):
                raise ValueError("headers")
            key = name.lower()
            if key in headers:
                raise ValueError("duplicate header")
            headers[key] = value.strip()
        else:
            raise ValueError("headers")
        if b"transfer-encoding" in headers:
            raise ValueError("request body")
        length = 0
        if b"content-length" in headers:
            try:
                length = int(headers[b"content-length"])
            except ValueError as exc:
                raise ValueError("request body") from exc
            if length < 0 or length > 262144 or (method != "POST" and length):
                raise ValueError("request body")
        body = self.rfile.read(length) if length else b""
        if len(body) != length: raise ValueError("truncated body")
        return method, path, headers, body

    def handle(self):
        try:
            method, path, headers, body = self._request()
        except ValueError:
            self._reply(400, b"bad request\n")
            return
        if path.startswith("/api/"):
            self.api(method, path, headers, body)
        elif method != "GET":
            self._reply(404, b"not found\n")

        elif path == "/health":
            self._reply(200, b'{"status":"ok"}', "application/json; charset=utf-8")
        elif path == "/app.apk":
            self._send_apk()
        else:
            self._reply(404, b"not found\n")

    def api(self, method, path, headers, body):
        try:
            target = urlsplit(path)
            data = json.loads(body) if body else {}
            if not isinstance(data, dict): raise ApiError("无效请求")
            if method == "POST" and path == "/api/pair":
                if set(data) != {"code"}: raise ApiError("无效配对请求")
                result = CONTROL.pair(data["code"])
            else:
                auth = headers.get(b"authorization", b"").decode("ascii")
                owner = CONTROL.authenticate(auth[7:] if auth.startswith("Bearer ") else "")
                if method=="GET" and target.path=="/api/status":result=json.loads(CACHE.get())
                elif method=="GET" and target.path=="/api/history":result=TELEMETRY.history(parse_qs(target.query).get("window",["5m"])[0])
                elif method=="GET" and path=="/api/storage/roots":result={"roots":[{"id":k,"path":str(v)} for k,v in STORAGE.roots.items()]}
                elif method == "GET" and path == "/api/resources":
                    with RESOURCE_LOCK:
                        if time.monotonic() > RESOURCE_CACHE[0]:
                            snapshot = CONTROL.resources()
                            RESOURCE_CACHE[:] = [time.monotonic()+5, snapshot]
                        result = annotate_inventory(RESOURCE_CACHE[1])
                elif method=='POST' and path=='/api/resources/prepare-end':
                    if set(data)!={'resource'}:raise ApiError('无效授权请求')
                    try:result=RESOURCE_END.prepare(owner,data['resource'])
                    except ApiError as error:result={'ready':False,'reason':str(error),'requires_admin':error.code==403 and '管理员' in str(error)}
                elif method=='POST' and path=='/api/resources/end':
                    if set(data)!={'ticket','request'}:raise ApiError('无效结束请求')
                    result=RESOURCE_END.submit(owner,data['ticket'],data['request'])
                elif method=='GET' and path=='/api/backup':result={'schema':1,'alert_rules':ALERTS.snapshot()['rules']}
                elif method=='POST' and path=='/api/backup':
                    if set(data)!={'schema','alert_rules'} or type(data['schema'])!=int or data['schema']!=1:raise ApiError('备份格式不支持')
                    ALERTS.configure(data['alert_rules']);result={'ok':True}
                elif method=='GET' and path=='/api/operations':result=CONTROL.operations_for(owner)
                elif method=='GET' and path=='/api/startup':result=CONTROL.startup()
                elif method=='POST' and path=='/api/startup':
                    if set(data)!={'resource','action','request'} or data['resource'] not in {k for k,v in __import__('control').RESOURCES.items() if v[1]=='system'} or data['action'] not in ('enable','disable'):raise ApiError('不允许的启动设置')
                    result=CONTROL.action(owner,data['resource'],data['action'],data['request'])
                elif method=='GET' and path=='/api/health-report':result=report(TELEMETRY.history('60m')['points'])
                elif path.startswith('/api/files/'):
                    if FILES is None:raise ApiError('文件区不可用',503)
                    action=path.removeprefix('/api/files/')
                    if method=='GET' and action=='list':result=FILES.list('')
                    elif method=='GET' and action=='trash':result=FILES.trash_list(owner)
                    elif method!='POST':raise ApiError('接口不存在',404)
                    elif action=='list' and set(data)=={'path'}:result=FILES.list(data['path'])
                    elif action=='stat' and set(data)=={'path'}:result=FILES.stat(owner,data['path'])
                    elif action=='read' and set(data)=={'path','offset','ticket'}:result=FILES.read(owner,data['path'],data['offset'],data['ticket'])
                    elif action=='upload/start' and set(data)=={'directory','name','size'}:result=FILES.create_upload(owner,data['directory'],data['name'],data['size'])
                    elif action=='upload/chunk' and set(data)=={'id','offset','data'}:result=FILES.append(owner,data['id'],data['offset'],data['data'])
                    elif action=='upload/abort' and set(data)=={'id'}:FILES.abort(owner,data['id']);result={'ok':True}
                    elif action=='upload/finish' and set(data)=={'id','sha256','request'}:
                        FILES.ident(data['id']);result=CONTROL.enqueue(owner,'upload-'+data['id'],'upload',data['request'],lambda:FILES.finish(owner,data['id'],data['sha256']))
                    elif action=='mkdir' and set(data)=={'path','name','request'}:
                        result=CONTROL.enqueue(owner,'files-mkdir','mkdir',data['request'],lambda:FILES.mkdir(data['path'],data['name']))
                    elif action in ('rename','trash') and set(data)==({'path','name','ticket','request'} if action=='rename' else {'path','ticket','request'}):
                        import hashlib
                        resource='file-'+hashlib.sha256(str(data['path']).encode()).hexdigest()[:20]
                        job=(lambda:FILES.rename(owner,data['path'],data['name'],data['ticket'])) if action=='rename' else (lambda:FILES.trash(owner,data['path'],data['ticket']))
                        result=CONTROL.enqueue(owner,resource,action,data['request'],job)
                    elif action=='restore' and set(data)=={'id','request'}:
                        FILES.ident(data['id']);result=CONTROL.enqueue(owner,'trash-'+data['id'],'restore',data['request'],lambda:FILES.restore(owner,data['id']))
                    else:raise ApiError('无效文件请求')
                elif method == "GET" and target.path == "/api/storage/scan":
                    result=STORAGE.scan(parse_qs(target.query).get('root',['home'])[0])
                elif method == "GET" and path == "/api/storage/cleanup":
                    result=STORAGE.preview(owner,'preview')
                elif method == "POST" and path == "/api/storage/cleanup":
                    if set(data)!={'preview','request'}:raise ApiError('无效清理请求')
                    result=CONTROL.enqueue(owner,'storage-preview','clean',data['request'],lambda:STORAGE.clean(owner,data['preview']))
                elif method == "GET" and path == "/api/alerts":
                    result=ALERTS.snapshot()
                elif method == "POST" and path == "/api/alerts/rules":
                    result=ALERTS.configure(data)
                elif method == "GET" and path == "/api/processes":
                    result = PROCESSES.snapshot()
                elif method == "GET" and path.startswith("/api/processes/"):
                    result = PROCESSES.detail(owner,int(path.removeprefix("/api/processes/")))
                elif method == "POST" and path == "/api/processes/terminate":
                    if set(data)!={"pid","start","ticket","request"}:raise ApiError("无效进程操作")
                    pid,start,ticket=data["pid"],data["start"],data["ticket"]
                    PROCESSES.validate(owner,pid,start,ticket)
                    result=CONTROL.enqueue(owner,f"process-{pid}-{start}","terminate",data["request"],lambda:PROCESSES.terminate(owner,pid,start,ticket))
                elif method == "GET" and path.startswith("/api/logs/"):
                    result = CONTROL.logs(path.removeprefix("/api/logs/"))
                elif method == "POST" and path == "/api/actions":
                    if set(data) != {"resource","action","request"}: raise ApiError("无效操作请求")
                    result = CONTROL.action(owner, data["resource"], data["action"], data["request"])
                elif method == "GET" and path.startswith("/api/actions/by-request/"):
                    result = CONTROL.by_request(owner,path.removeprefix("/api/actions/by-request/"))
                elif method == "GET" and path.startswith("/api/actions/"):
                    result = CONTROL.operation(owner,path.removeprefix("/api/actions/"))
                    if result["state"] not in ("queued","running"): RESOURCE_CACHE[0] = 0
                elif method == "POST" and path == "/api/unpair":
                    DESKTOP.revoke(owner); CONTROL.revoke(owner); result={"ok":True}
                elif method == "POST" and path == "/api/desktop/open":
                    if set(data) != {"width","height"}:raise ApiError("无效桌面请求")
                    result=DESKTOP.open(owner,data["width"],data["height"])
                elif path.startswith("/api/desktop/"):
                    parts=path.split("/")
                    if len(parts)!=5:raise ApiError("接口不存在",404)
                    action,sid=parts[3:]
                    if method=="GET" and action=="read":result={"data":DESKTOP.get(owner,sid).read()}
                    elif method=="POST" and action=="write":
                        if set(data)!={"data"}:raise ApiError("无效桌面输入")
                        DESKTOP.get(owner,sid).write(data["data"]);result={"ok":True}
                    elif method=="POST" and action=="close":DESKTOP.close(owner,sid);result={"ok":True}
                    else:raise ApiError("接口不存在",404)
                else: raise ApiError("接口不存在",404)
            self._reply(200,json.dumps(result,ensure_ascii=False,allow_nan=False).encode(),"application/json; charset=utf-8")
        except ApiError as e:
            self._reply(e.code,json.dumps({"error":str(e)},ensure_ascii=False).encode(),"application/json; charset=utf-8")
        except (ValueError,TypeError,KeyError,UnicodeError):
            self._reply(400,b'{"error":"invalid request"}',"application/json")
        except OSError:
            self._reply(503,'{"error":"服务暂不可用，请刷新状态或检查权限"}'.encode(),"application/json")

    def _send_apk(self):
        try:
            fd = os.open(APK, os.O_RDONLY | os.O_NOFOLLOW)
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_APK:
                os.close(fd)
                raise ValueError("APK unavailable")
        except (OSError, ValueError):
            self._reply(404, b"not found\n")
            return
        with os.fdopen(fd, "rb") as stream:
            try:
                self.wfile.write(("HTTP/1.1 200 OK\r\n"
                                  f"Content-Length: {info.st_size}\r\n"
                                  "Content-Type: application/vnd.android.package-archive\r\n"
                                  "Content-Disposition: attachment; filename=\"pi-console.apk\"\r\n"
                                  "Cache-Control: no-store\r\n"
                                  "X-Content-Type-Options: nosniff\r\n"
                                  "Connection: close\r\n\r\n").encode("ascii"))
                while chunk := stream.read(65536):
                    self.wfile.write(chunk)
            except OSError:
                # A disconnected client or a changed file ends this one response.
                return


class LocalServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    slots = threading.BoundedSemaphore(24)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


def main():
    global CONTROL, DESKTOP, ALERTS, FILES, RESOURCE_END
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, choices=range(1024,65536), default=18765)
    args = parser.parse_args()
    CONTROL = Control()
    RESOURCE_END = ResourceEnd(CONTROL,PROCESSES)
    DESKTOP = Desktop()
    FILES = Files()
    FILES.start_cleanup()
    TELEMETRY.start()
    ALERTS = Alerts()
    ALERTS.start(TELEMETRY,CONTROL)
    with LocalServer(("127.0.0.1", args.port), Handler) as server:
        server.serve_forever(poll_interval=0.5)


if __name__ == "__main__":
    main()
