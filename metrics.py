# SPDX-License-Identifier: Apache-2.0
"""Read-only, dependency-free host status collection."""
from datetime import datetime
import json
import math
from pathlib import Path
import shutil
import subprocess

from config import SETTINGS
SERVICES = tuple(v[2] for v in SETTINGS['resources'].values() if v[1]=='user')


def _capture(reader):
    try:
        return {"status": "ok", "value": reader()}
    except subprocess.TimeoutExpired:
        return {"status": "unavailable", "error": "读取命令超时（5 秒）"}
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        return {"status": "unavailable", "error": f"无法读取或数据无效（{type(exc).__name__}）"}


def _finite_nonnegative(value):
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError("invalid measurement")
    return value


def _temperature(root):
    for zone in sorted(root.glob("thermal_zone*")):
        kind = (zone / "type").read_text().strip().lower()
        if "cpu" in kind or "soc" in kind:
            value = float((zone / "temp").read_text()) / 1000
            if not math.isfinite(value) or not -40 <= value <= 150:
                raise ValueError("invalid temperature")
            return value
    raise FileNotFoundError("CPU thermal interface")


def _memory(proc_root):
    fields = {}
    for line in (proc_root / "meminfo").read_text().splitlines():
        name, _, content = line.partition(":")
        if name in ("MemTotal", "MemAvailable"):
            number, unit = content.split()
            if unit != "kB":
                raise ValueError("invalid memory units")
            fields[name] = int(number) * 1024
    total, available = fields["MemTotal"], fields["MemAvailable"]
    if not 0 < total <= 2**64 - 1 or not 0 <= available <= total:
        raise ValueError("invalid memory")
    return {"total": total, "available": available}


def _load(proc_root):
    values = (proc_root / "loadavg").read_text().split()[:3]
    if len(values) != 3:
        raise ValueError("invalid load")
    return [_finite_nonnegative(x) for x in values]


def _command(args, runner):
    result = runner(args, capture_output=True, text=True, timeout=5,
                    stdin=subprocess.DEVNULL, check=False)
    if result.returncode:
        raise OSError("status command unavailable")
    return result.stdout


def _services(runner):
    if not SERVICES:return []
    raw = _command(["systemctl", "--user", "show", *SERVICES,
                    "-p", "Id", "-p", "ActiveState", "-p", "SubState",
                    "-p", "UnitFileState"], runner)
    result = []
    for block in raw.strip().split("\n\n"):
        properties = dict(line.split("=", 1) for line in block.splitlines() if "=" in line)
        if properties.get("Id") in SERVICES:
            result.append({"name": properties["Id"], "active": properties["ActiveState"],
                           "sub": properties["SubState"], "enabled": properties.get("UnitFileState", "unknown")})
    if len(result) != len(SERVICES):
        raise ValueError("incomplete service output")
    return result


def _containers(runner):
    template = '{"id":{{json .ID}},"name":{{json .Names}},"state":{{json .State}},"status":{{json .Status}}}'
    raw = _command(["docker", "--host=unix:///var/run/docker.sock", "ps", "-a", "--format", template], runner)
    result = []
    for line in raw.splitlines():
        item = json.loads(line)
        result.append({key: item[key] for key in ("id", "name", "state", "status")})
    return result


def collect_status(proc_root=Path("/proc"), thermal_root=Path("/sys/class/thermal"),
                   disk_path=Path.home(), runner=subprocess.run):
    def disk():
        usage = shutil.disk_usage(disk_path)
        return {"total": usage.total, "used": usage.used, "free": usage.free}

    return {"sampled_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "metrics": {
                "cpu_temperature_c": _capture(lambda: _temperature(thermal_root)),
                "load_1_5_15": _capture(lambda: _load(proc_root)),
                "memory_bytes": _capture(lambda: _memory(proc_root)),
                "disk_bytes": _capture(disk),
                "uptime_seconds": _capture(lambda: _finite_nonnegative((proc_root / "uptime").read_text().split()[0])),
                "services": _capture(lambda: _services(runner)),
                "containers": _capture(lambda: _containers(runner)),
            }}
