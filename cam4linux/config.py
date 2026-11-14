"""Config (~/.config/cam4linux/config.json) and runtime status file shared by GUI and daemon."""

import copy
import json
import os
import tempfile

CONFIG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "cam4linux")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
RUNTIME_DIR = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/tmp", "cam4linux-%d" % os.getuid())
STATUS_FILE = os.path.join(RUNTIME_DIR, "status.json")
LOCK_FILE = os.path.join(RUNTIME_DIR, "daemon.lock")

# Presets: list of (temp °C, duty %)
PRESETS = {
    "silent":      [[30, 25], [50, 30], [65, 45], [75, 65], [85, 100]],
    "balanced":    [[30, 30], [45, 35], [60, 55], [75, 80], [85, 100]],
    "performance": [[30, 45], [45, 55], [60, 75], [70, 90], [80, 100]],
    "full":        [[0, 100], [100, 100]],
}

DEFAULT_FAN = {
    "name": "",             # empty = translated default ("Fan 1")
    "mode": "curve",        # curve | fixed
    "fixed": 50,
    "sources": [],          # sensor ids, the hottest one counts
    "curve": PRESETS["balanced"],
    "stop": {"enabled": False, "below": 40, "above": 45},  # fan stop with hysteresis (°C)
}

# DC controlled fans: the Smart Device V2 does not go below ~6 V, so duties below
# this value make no difference (measured: 1-35 % all ~6.2 V, 50 % ~7.1 V)
DC_FLOOR = 40

DEFAULT_LED = {
    "mode": "fixed",
    "colors": ["#3c78ff"],
    "speed": "normal",
    "direction": "forward",
}

DEFAULT = {
    "interval": 1.0,        # seconds between temperature polls
    "ramp_down": 3.0,       # max duty decrease per second (%) - avoids audible pumping
    "exit_duty": 60,        # duty set when the daemon stops
    "language": "auto",     # auto = system language, or a code from cam4linux/lang
    "fans": {},
    "lighting": {"sync": True, "channels": {}},
}


def fan_defaults(n, sources):
    f = copy.deepcopy(DEFAULT_FAN)
    f["sources"] = list(sources)
    return f


def load():
    cfg = copy.deepcopy(DEFAULT)
    try:
        with open(CONFIG_FILE) as f:
            user = json.load(f)
        for k, v in user.items():
            cfg[k] = v
    except (OSError, ValueError):
        pass
    cfg.setdefault("lighting", {}).setdefault("channels", {})
    cfg["lighting"].setdefault("sync", True)
    return cfg


def _atomic_write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def save(cfg):
    _atomic_write(CONFIG_FILE, cfg)


def config_mtime():
    try:
        return os.stat(CONFIG_FILE).st_mtime_ns
    except OSError:
        return 0


def write_status(status):
    os.makedirs(RUNTIME_DIR, mode=0o700, exist_ok=True)
    _atomic_write(STATUS_FILE, status)


def read_status():
    try:
        with open(STATUS_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None
