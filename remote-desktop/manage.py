#!/usr/bin/python3
# SPDX-License-Identifier: Apache-2.0
"""Scoped GNOME RDP setup. Use sudo python3 -I -B ... install/uninstall."""
import argparse
import base64
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
SOURCE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("rdp_safety", SOURCE / "safety.py")
safety = importlib.util.module_from_spec(spec)
spec.loader.exec_module(safety)
SERVICE = "gnome-remote-desktop.service"
CONFIG_SERVICE = "gnome-remote-desktop-configuration.service"
GUARD = "pi-console-rdp-guard.service"
TABLE = "pi_console_rdp"
IP = "127.0.0.1"
UFW_RULE = ["allow", "in", "on", "tailscale0", "to", "any", "port", "3389",
            "proto", "tcp", "comment", "pi-console-rdp"]


def run(args, input=None, check=True):
    return subprocess.run([str(x) for x in args], input=input, text=True,
                          capture_output=True, timeout=45, check=check,
                          env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"})


class Manager:
    def __init__(self, system_root=Path("/"), project=SOURCE.parent, runner=run, user=None, address=IP):
        self.root, self.project, self.run = Path(system_root), Path(project), runner
        self.user=user
        import ipaddress
        self.address=str(ipaddress.ip_address(address))
        self.state_dir = self.path("var/lib/pi-console-rdp-state")
        self.state = self.state_dir / "state.json"
        self.data = self.path("var/lib/pi-console-rdp")
        self.config = self.path("etc/gnome-remote-desktop/grd.conf")
        self.home = self.path("var/lib/gnome-remote-desktop")
        self.receipt = self.project / "state/remote-desktop.json"
        self.connection = self.project / "remote-desktop/connection.json"
        self.rules = self.path("etc/nftables.d/pi-console-rdp.nft")
        self.guard_unit = self.path("etc/systemd/system") / GUARD
        self.dropins = [self.path("etc/systemd/system") / (unit + ".d/70-pi-console-rdp.conf")
                        for unit in (SERVICE, CONFIG_SERVICE)]
        self.record = None

    def path(self, relative):
        return self.root / relative

    def cmd(self, *args, **kwargs):
        return self.run(list(args), **kwargs)

    def unit(self, name):
        raw = self.cmd("/usr/bin/systemctl", "show", name, "-p", "ActiveState", "-p", "UnitFileState").stdout
        return dict(line.split("=", 1) for line in raw.splitlines() if "=" in line)

    def nft(self):
        tables = json.loads(self.cmd("/usr/sbin/nft", "-j", "list", "tables").stdout)
        if not any(row.get("table", {}).get("name") == TABLE and
                   row["table"].get("family") == "inet" for row in tables["nftables"]):
            return None
        return json.loads(self.cmd("/usr/sbin/nft", "-j", "list", "table", "inet", TABLE).stdout)

    def save(self):
        safety.save_json(self.state, self.record)

    def load(self):
        safety.safe_path(self.state)
        if self.state.stat().st_uid != os.geteuid() or self.state.stat().st_mode & 0o077:
            raise RuntimeError("recovery state ownership/permissions changed")
        self.record = json.loads(self.state.read_text())
        if self.record.get("version") != 1:
            raise RuntimeError("unsupported recovery record")

    def mkdir(self, path, mode=0o755, owner=None):
        path = safety.safe_path(path)
        if path.is_dir():
            return
        if not path.parent.is_dir():
            self.mkdir(path.parent)
        self.record["dirs"].append(str(path))
        self.save()
        path.mkdir(mode=mode)
        if owner:
            os.chown(path, *owner)

    def write(self, path, data, mode=0o644, owner=None):
        path = safety.safe_path(path)
        if path.exists():
            raise RuntimeError(f"refusing existing file: {path}")
        self.mkdir(path.parent)
        self.record["files"][str(path)] = [safety.sha(data)]
        self.record.setdefault("contents", {})[str(path)] = base64.b64encode(data).decode()
        self.save()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
        with os.fdopen(fd, "wb") as stream:
            if owner:
                os.fchown(stream.fileno(), *owner)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())

    def preflight(self):
        for binary in ("/usr/sbin/nft", "/usr/sbin/runuser", "/usr/bin/grdctl", "/usr/bin/openssl"):
            if not Path(binary).is_file():
                raise RuntimeError(f"required existing component absent: {binary}")
        for path in (self.state_dir, self.data, self.rules, self.guard_unit, *self.dropins,
                     self.receipt, self.connection):
            safety.safe_path(path)
            if path.exists():
                raise RuntimeError(f"existing managed path; inspect/uninstall first: {path}")
        old_data = safety.safe_path(self.home / ".local/share/gnome-remote-desktop")
        service = self.unit(SERVICE)
        configuration = self.unit(CONFIG_SERVICE)
        safety.safe_path(self.config)
        safety.check_baseline(self.config.exists(),
                              service.get("ActiveState") != "inactive" or configuration.get("ActiveState") != "inactive",
                              service.get("UnitFileState") != "disabled" or configuration.get("UnitFileState") != "disabled",
                              bool(self.cmd("/usr/bin/ss", "-ltnH", "sport = :3389").stdout.strip()),
                              old_data.exists() and bool(list(old_data.iterdir())))
        if self.nft() is not None:
            raise RuntimeError("managed nft table already exists")
        self.cmd("/usr/bin/ip", "link", "show", "dev", "tailscale0")
        if self.unit("gdm.service").get("ActiveState") != "active":
            raise RuntimeError("existing GNOME login manager is not active")
        ufw_active = False
        if Path("/usr/sbin/ufw").exists():
            ufw_active = self.cmd("/usr/sbin/ufw", "status").stdout.startswith("Status: active")
            added = self.cmd("/usr/sbin/ufw", "show", "added").stdout
            if "pi-console-rdp" in added:
                raise RuntimeError("existing managed UFW rule")
            if ufw_active and re.search(r"\b3389\b", added):
                raise RuntimeError("existing UFW rules for 3389 require review before setup")
        return ufw_active

    def environment(self):
        return ["HOME=" + str(self.home), "USER=gnome-remote-desktop", "LOGNAME=gnome-remote-desktop",
                "PATH=/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL=C",
                "XDG_DATA_HOME=" + str(self.data / "data"),
                "XDG_CONFIG_HOME=" + str(self.data / "config"),
                "XDG_CACHE_HOME=" + str(self.data / "cache")]

    def set_credentials(self, username, password):
        # grdctl 50.2 constructs a new buffered reader for each prompt. Passing
        # two lines together loses the second line and crashes on EOF. Supply
        # the public username as an argument and only the secret on stdin.
        self.cmd("/usr/sbin/runuser", "-u", "gnome-remote-desktop", "--",
                 "/usr/bin/env", "-i", *self.environment(),
                 "/usr/bin/grdctl", "rdp", "set-credentials", username, input=password + "\n")

    def install(self):
        ufw_active = self.preflight()
        account = pwd.getpwnam("gnome-remote-desktop")
        owner = (account.pw_uid, account.pw_gid)
        if not self.user:raise RuntimeError("install requires --user for an existing desktop account")
        target = pwd.getpwnam(self.user)
        if target.pw_uid==0:raise RuntimeError("root desktop account refused")
        self.state_dir.mkdir(mode=0o700)
        self.record = {"version": 1, "phase": "installing", "files": {}, "contents": {},
                       "dirs": [], "ufw_added": False, "nft_signature": None,
                       "credential_hashes": {}, "credential_pending": False,
                       "marker": secrets.token_hex(16)}
        self.save()
        try:
            self.write(self.receipt, b'{"component":"pi-console-rdp","state":"/var/lib/pi-console-rdp-state"}\n',
                       0o600, (target.pw_uid, target.pw_gid))
            self.mkdir(self.data, 0o700, owner)
            self.write(self.data / ".owner", self.record["marker"].encode(), 0o600, owner)
            self.cmd("/usr/bin/openssl", "req", "-x509", "-newkey", "rsa:3072", "-nodes", "-days", "365",
                     "-subj", "/CN=pi-console-rdp", "-addext", "subjectAltName=IP:" + self.address,
                     "-keyout", str(self.data / "tls.key"), "-out", str(self.data / "tls.crt"))
            for name in ("tls.key", "tls.crt"):
                path = self.data / name
                os.chown(path, *owner)
                os.chmod(path, 0o600)
                self.record["credential_hashes"][str(path)] = safety.sha(path.read_bytes())
            self.save()
            username, password = "pi-console", secrets.token_urlsafe(24)
            self.record["credential_pending"] = True
            self.save()
            self.set_credentials(username, password)
            credentials = self.data / "data/gnome-remote-desktop"
            for path in credentials.rglob("*"):
                safety.safe_path(path)
                if path.is_file():
                    self.record["credential_hashes"][str(path)] = safety.sha(path.read_bytes())
            self.record["credential_pending"] = False
            self.save()
            rules = ('table inet pi_console_rdp {\n  chain input {\n'
                     '    type filter hook input priority -150; policy accept;\n'
                     '    iifname != "tailscale0" iifname != "lo" tcp dport 3389 counter drop\n'
                     '  }\n}\n').encode()
            self.write(self.rules, rules)
            self.cmd("/usr/sbin/nft", "--check", "-f", str(self.rules))
            unit = ("[Unit]\nDescription=Pi console RDP private-network guard\nBefore=" + SERVICE +
                    "\n[Service]\nType=oneshot\nRemainAfterExit=yes\nExecStart=/usr/sbin/nft -f " + str(self.rules) +
                    "\nExecStop=-/usr/sbin/nft delete table inet pi_console_rdp\n").encode()
            self.write(self.guard_unit, unit)
            environment = "[Service]\n" + "".join('Environment="' + value + '"\n' for value in self.environment()
                                                   if value.startswith("XDG_"))
            for index, path in enumerate(self.dropins):
                prefix = "[Unit]\nRequires=" + GUARD + "\nAfter=" + GUARD + "\n" if index == 0 else ""
                self.write(path, (prefix + environment).encode())
            self.write(self.config, ("[RDP]\nenabled=true\nport=3389\ntls-cert=" + str(self.data / "tls.crt") +
                                    "\ntls-key=" + str(self.data / "tls.key") + "\n").encode(), 0o600, owner)
            self.cmd("/usr/bin/systemctl", "daemon-reload")
            self.cmd("/usr/bin/systemctl", "start", GUARD)
            table = self.nft()
            if table is None:
                raise RuntimeError("private-network guard not installed")
            self.record["nft_signature"] = safety.nft_signature(table)
            self.save()
            if ufw_active:
                self.record["ufw_added"] = True
                self.save()
                self.cmd("/usr/sbin/ufw", "insert", "1", *UFW_RULE)
            fingerprint = self.cmd("/usr/bin/openssl", "x509", "-in", str(self.data / "tls.crt"),
                                   "-noout", "-fingerprint", "-sha256").stdout.strip()
            connection = dict(address=self.address + ":3389", username=username, password=password,
                              fingerprint=fingerprint, ubuntu_user=self.user)
            self.write(self.connection, (json.dumps(connection, ensure_ascii=False) + "\n").encode(),
                       0o600, (target.pw_uid, target.pw_gid))
            # Connection export contains a secret; retain only its digest in recovery state.
            self.record["contents"].pop(str(self.connection), None)
            self.save()
            self.cmd("/usr/bin/systemctl", "enable", "--now", SERVICE)
            for _ in range(10):
                if self.cmd("/usr/bin/ss", "-ltnH", "sport = :3389").stdout.strip():
                    break
                time.sleep(0.5)
            else:
                raise RuntimeError("RDP listener did not appear")
            state = self.unit(SERVICE)
            if state.get("ActiveState") != "active" or state.get("UnitFileState") != "enabled":
                raise RuntimeError("remote desktop did not reach active/enabled")
            self.record["phase"] = "installed"
            self.save()
            print("RDP enabled at " + self.address + ":3389; firewall guard active. Phone connection still needs verification.")
            print("Read private credentials locally: python3 -I -B " + str(SOURCE / "manage.py") + " credentials")
        except BaseException:
            # Leave guard and recovery data in place until explicit scoped cleanup.
            self.cmd("/usr/bin/systemctl", "stop", SERVICE, check=False)
            self.cmd("/usr/bin/systemctl", "disable", SERVICE, check=False)
            raise

    def validate_files(self):
        for name, hashes in self.record["files"].items():
            try:
                safety.verify_owned(Path(name), hashes)
            except RuntimeError:
                partial = self.record.get("phase") == "installing" or self.record.get("recovering_install")
                encoded = self.record.get("contents", {}).get(name)
                if not partial or not encoded:
                    raise
                path = safety.safe_path(name)
                if not base64.b64decode(encoded).startswith(path.read_bytes()):
                    raise
        for name, digest in self.record.get("credential_hashes", {}).items():
            safety.verify_owned(Path(name), [digest])

    def uninstall(self):
        safety.safe_path(self.state)
        if not self.state.exists():
            # A crash can occur between the final unlink and rmdir. Recover only
            # an empty directory with every known managed resource already gone.
            resources = (self.data, self.config, self.rules, self.guard_unit,
                         *self.dropins, self.receipt, self.connection)
            if any(safety.safe_path(p).exists() for p in resources):
                raise RuntimeError("recovery record missing while managed resources remain")
            if self.state_dir.exists() and any(self.state_dir.iterdir()):
                raise RuntimeError("unexpected files in recovery directory")
            state = self.unit(SERVICE)
            if state.get("ActiveState") != "inactive" or state.get("UnitFileState") != "disabled" or self.nft() is not None:
                raise RuntimeError("recovery record missing while remote desktop or guard remains")
            if Path("/usr/sbin/ufw").exists() and "pi-console-rdp" in self.cmd("/usr/sbin/ufw", "show", "added").stdout:
                raise RuntimeError("recovery record missing while firewall rule remains")
            if self.state_dir.exists():
                self.state_dir.rmdir()
            print("Final recovery directory cleared; no managed resources remain.")
            return
        self.load()
        self.validate_files()
        table = self.nft()
        if table is not None and self.record.get("nft_signature") and safety.nft_signature(table) != self.record["nft_signature"]:
            raise RuntimeError("managed firewall table changed; refusing cleanup")
        self.record["recovering_install"] = self.record.get("recovering_install", False) or self.record["phase"] == "installing"
        self.record["phase"] = "removing"
        self.save()
        self.cmd("/usr/bin/systemctl", "stop", SERVICE)
        if self.unit(SERVICE).get("ActiveState") != "inactive":
            raise RuntimeError("RDP service is not stopped")
        self.cmd("/usr/bin/systemctl", "disable", SERVICE)
        self.cmd("/usr/bin/systemctl", "stop", CONFIG_SERVICE)
        self.cmd("/usr/bin/systemctl", "stop", GUARD, check=False)
        if self.nft() is not None:
            self.cmd("/usr/sbin/nft", "delete", "table", "inet", TABLE)
        if self.record.get("ufw_added"):
            added = self.cmd("/usr/sbin/ufw", "show", "added").stdout
            if "pi-console-rdp" in added:
                self.cmd("/usr/sbin/ufw", "--force", "delete", *UFW_RULE)
            self.record["ufw_added"] = False
            self.save()
        self.validate_files()
        # Delete the dedicated data tree only with our matching installation marker.
        if self.data.exists():
            safety.safe_path(self.data)
            marker = safety.safe_path(self.data / ".owner")
            if not marker.exists() and not any(self.data.iterdir()):
                self.data.rmdir()
            elif (marker.exists() and self.record.get("recovering_install")
                  and set(self.data.iterdir()) == {marker}
                  and self.record["marker"].encode().startswith(marker.read_bytes())):
                # No other data can have been created before the marker write
                # completed. This also handles a zero-byte interrupted write.
                marker.unlink()
                self.data.rmdir()
            elif marker.read_text() == self.record["marker"]:
                # Preserve ownership evidence until every other child is gone.
                for child in self.data.iterdir():
                    if child == marker:
                        continue
                    if child.is_dir() and not child.is_symlink():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
                marker.unlink()
                self.data.rmdir()
            else:
                raise RuntimeError("private data directory marker changed")
        for name in reversed(list(self.record["files"])):
            path = Path(name)
            if path.is_relative_to(self.data):
                continue
            # Files were validated above, including recognizable incomplete writes.
            safety.safe_path(path).unlink(missing_ok=True)
        self.cmd("/usr/bin/systemctl", "daemon-reload")
        if self.nft() is not None:
            raise RuntimeError("managed firewall table still exists")
        for name in reversed(self.record["dirs"]):
            path = safety.safe_path(name)
            if path.exists():
                path.rmdir()  # Unexpected remaining files preserve the recovery record.
        for path in self.state_dir.glob(".state-*"):
            safety.safe_path(path).unlink()
        self.state.unlink()
        try:
            self.state_dir.rmdir()
        except OSError:
            self.save()
            raise
        print("Remote desktop setup removed; pre-existing GNOME packages and local desktop retained.")

    def status(self):
        result = {"service": self.unit(SERVICE), "guard": self.unit(GUARD),
                  "listener": self.cmd("/usr/bin/ss", "-ltnH", "sport = :3389").stdout.strip(),
                  "managed_state_present": self.state_dir.exists()}
        if os.geteuid() == 0:
            result["firewall_table_present"] = self.nft() is not None
        print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", default="preview",
                        choices=("preview", "install", "status", "uninstall", "credentials"))
    parser.add_argument("--user", default=os.environ.get("SUDO_USER"))
    parser.add_argument("--address", default=IP, help="Tailscale IP for the RDP certificate")
    args = parser.parse_args()
    manager = Manager(user=args.user,address=args.address)
    try:
        if args.action == "preview":
            print("Will enable existing GNOME Remote Login on TCP 3389, with Tailscale-only network access (and local diagnostics).")
            print("Creates dedicated data/state directories, GNOME config, two systemd drop-ins, nft guard unit/rules; records an optional UFW allow rule if UFW is active.")
            print("No package installation, reboot, local logout, or changes to Codex/Immich.")
            print("Root preflight refuses existing RDP config, credentials, active service, occupied port or managed paths.")
        elif args.action == "status":
            manager.status()
        elif args.action == "credentials":
            path = safety.safe_path(manager.connection)
            if path.stat().st_uid not in (os.geteuid(), 0) or path.stat().st_mode & 0o077:
                raise RuntimeError("private credential file permissions changed")
            print(path.read_text())
        else:
            if os.geteuid() != 0:
                raise RuntimeError("administrator authentication required: use sudo python3 -I -B with this script")
            getattr(manager, args.action)()
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        # Do not print subprocess stdout/stderr, which may contain credential prompts.
        print("RDP setup: " + str(exc) + ". Any existing recovery record is retained.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
