# SPDX-License-Identifier: Apache-2.0
"""Filesystem and preflight checks shared by the scoped RDP installer."""
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(path):
    path = Path(path).absolute()
    if ".." in path.parts:
        raise RuntimeError("parent traversal is not allowed")
    for component in (path, *path.parents):
        if component.is_symlink():
            raise RuntimeError(f"symlink path refused: {component}")
    return path


def save_json(path, value):
    path = safe_path(path)
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode()
    fd, name = tempfile.mkstemp(prefix=".state-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


def check_baseline(configured, active, enabled, port_busy, credentials_present):
    checks = ((configured, "existing GNOME configuration"),
              (active, "remote desktop is already active"),
              (enabled, "remote desktop is already enabled"),
              (port_busy, "TCP 3389 is occupied"),
              (credentials_present, "existing remote desktop data/credentials"))
    for failed, message in checks:
        if failed:
            raise RuntimeError(message + "; refusing to overwrite")


def verify_owned(path, hashes):
    path = safe_path(path)
    if not path.exists():
        return
    if not stat.S_ISREG(path.stat().st_mode) or sha(path.read_bytes()) not in hashes:
        raise RuntimeError(f"managed file changed; retained: {path}")


def remove_owned(path, hashes):
    verify_owned(path, hashes)
    Path(path).unlink(missing_ok=True)


def nft_signature(document):
    def clean(value):
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items()
                    if k not in ("handle", "packets", "bytes")}
        if isinstance(value, list):
            return [clean(v) for v in value if not isinstance(v, dict) or "metainfo" not in v]
        return value
    return sha(json.dumps(clean(document), sort_keys=True).encode())
