"""Temperature sources: every hwmon temp sensor plus NVIDIA GPUs via nvidia-smi."""

import glob
import os
import shutil
import subprocess
import time

HWMON_ROOT = "/sys/class/hwmon"

# Sensor groups of well known hwmon drivers (translated in the GUI: sensor.group.<group>)
_GROUPS = {
    "k10temp": "cpu_amd",
    "zenpower": "cpu_amd",
    "coretemp": "cpu_intel",
    "amdgpu": "gpu_amd",
    "nvme": "nvme",
    "jc42": "ram",
    "spd5118": "ram",
}
_NUMBERED = ("nvme", "jc42", "spd5118")


def _read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


class Sensors(object):
    """
    Sensor IDs are stable across reboots (unlike hwmonN numbers):
        hwmon/<driver>#<n>/<label>   e.g. hwmon/k10temp#0/Tctl
        nvidia/<gpu index>

    read_all() returns {id: {"group", "name", "num", "label", "temp"}}:
    group is a known category or None (then name is the raw driver name),
    num distinguishes several devices of one kind (1-based) or is None.
    """

    NVIDIA_INTERVAL = 2.0

    def __init__(self):
        self._nvidia = shutil.which("nvidia-smi")
        self._nvidia_cache = {}
        self._nvidia_time = 0.0
        self.rescan()

    def rescan(self):
        self._hwmon = {}  # id -> (info dict, path)
        seen = {}
        paths = sorted(glob.glob(os.path.join(HWMON_ROOT, "hwmon*")),
                       key=lambda p: int(p.rsplit("hwmon", 1)[1]))
        for path in paths:
            name = _read(os.path.join(path, "name")) or "unknown"
            if name == "nzxtsmart2":
                continue
            n = seen.get(name, 0)
            seen[name] = n + 1
            num = n + 1 if (n > 0 or name in _NUMBERED) else None
            for inp in sorted(glob.glob(os.path.join(path, "temp*_input"))):
                base = inp[:-len("_input")]
                label = _read(base + "_label") or os.path.basename(base)
                sid = "hwmon/%s#%d/%s" % (name, n, label)
                info = {"group": _GROUPS.get(name), "name": name, "num": num, "label": label}
                self._hwmon[sid] = (info, inp)

    def _poll_nvidia(self):
        if not self._nvidia:
            return {}
        now = time.monotonic()
        if now - self._nvidia_time < self.NVIDIA_INTERVAL:
            return self._nvidia_cache
        self._nvidia_time = now
        try:
            out = subprocess.run(
                [self._nvidia, "--query-gpu=index,name,temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3).stdout
            res = {}
            for line in out.splitlines():
                idx, name, temp = [x.strip() for x in line.split(",")]
                res["nvidia/" + idx] = {"group": "gpu_nvidia", "name": "nvidia", "num": None,
                                        "label": name.replace("NVIDIA ", ""), "temp": float(temp)}
            self._nvidia_cache = res
        except (OSError, ValueError, subprocess.SubprocessError):
            self._nvidia_cache = {}
        return self._nvidia_cache

    def read_all(self):
        """Return {id: info dict with "temp" in °C or None}."""
        res = {}
        for sid, (info, path) in self._hwmon.items():
            raw = _read(path)
            try:
                temp = int(raw) / 1000.0
            except (TypeError, ValueError):
                temp = None
            res[sid] = dict(info, temp=temp)
        res.update(self._poll_nvidia())
        return res


def default_cpu(ids):
    for pref in ("hwmon/k10temp#0/Tctl", "hwmon/zenpower#0/Tdie", "hwmon/coretemp#0/Package id 0"):
        if pref in ids:
            return pref
    for i in ids:
        if i.startswith(("hwmon/k10temp", "hwmon/coretemp", "hwmon/zenpower")):
            return i
    return None


def default_gpu(ids):
    for i in sorted(ids):
        if i.startswith("nvidia/") or i.startswith("hwmon/amdgpu"):
            return i
    return None
