"""
Background control loop: polls temperatures, applies fan curves and LED settings.

Runs as the logged-in user (systemd user service). Reloads the config whenever
the GUI saves it and re-applies everything after suspend/resume or a replug.
"""

import fcntl
import logging
import os
import signal
import sys
import time

from . import config
from .device import SmartDevice2, DeviceError, find_devices
from .sensors import Sensors, default_cpu, default_gpu

log = logging.getLogger("cam4linux")


def interpolate(curve, temp):
    pts = sorted((float(t), float(d)) for t, d in curve)
    if not pts:
        return 100.0
    if temp <= pts[0][0]:
        return pts[0][1]
    for (t0, d0), (t1, d1) in zip(pts, pts[1:]):
        if temp <= t1:
            if t1 == t0:
                return d1
            return d0 + (d1 - d0) * (temp - t0) / (t1 - t0)
    return pts[-1][1]


def _suspend_offset():
    """Grows by the time spent suspended."""
    return time.clock_gettime(time.CLOCK_BOOTTIME) - time.clock_gettime(time.CLOCK_MONOTONIC)


class Daemon(object):

    def __init__(self):
        self.sensors = Sensors()
        self.dev = None
        self.cfg = None
        self.cfg_mtime = -1
        self.duty = {}            # ramped curve target per fan (base for ramping)
        self.sent = {}            # what was actually sent to the device
        self.stopped = {}         # fan stop state (hysteresis)
        self.seen_spinning = set()
        self.stall_since = {}
        self.kick_until = {}
        self.led_applied = False
        self.error = None
        self.running = True
        self.last_rescan = 0.0
        self._fallback_sources = self.default_sources

    # ------------------------------------------------------------ device
    def _connect(self):
        devs = find_devices()
        if not devs:
            self.dev = None
            self.error = {"code": "no_device", "args": {}}
            return
        if self.dev and self.dev.hidraw == devs[0]["hidraw"] and self.dev.writable and not self.error:
            return
        if self.dev:
            self.dev.close()
        self.dev = SmartDevice2(devs[0])
        self.duty, self.sent = {}, {}
        self.led_applied = False
        try:
            self.dev.initialize()
            self.error = None
            log.info("%s (firmware %s) on %s, LED accessories: %s", self.dev.name, self.dev.firmware,
                     self.dev.hidraw, self.dev.accessories)
        except DeviceError as e:
            if e.as_dict() != self.error:
                log.warning("%s", e)
            self.error = e.as_dict()

    def _complete_config(self, cfg):
        """Fill in fans/sources that are not configured yet (first start)."""
        if not self.dev:
            return cfg
        srcs = self.default_sources
        changed = False
        for ch in range(1, self.dev.fan_count + 1):
            if str(ch) not in cfg["fans"]:
                cfg["fans"][str(ch)] = config.fan_defaults(ch, srcs)
                changed = True
        if changed:
            config.save(cfg)
        return cfg

    @property
    def default_sources(self):
        ids = list(self.sensors.read_all().keys())
        return [s for s in (default_cpu(ids), default_gpu(ids)) if s] or ids[:1]

    # -------------------------------------------------------------- loop
    def apply_leds(self):
        if not self.dev or not self.dev.led_count:
            return
        light = self.cfg["lighting"]
        chans = light.get("channels", {})
        if light.get("sync", True):
            jobs = [(0, chans.get("1", config.DEFAULT_LED))]
        else:
            jobs = [(c, chans.get(str(c), config.DEFAULT_LED)) for c in range(1, self.dev.led_count + 1)]
        for cid, c in jobs:
            self.dev.set_color(cid, c.get("mode", "fixed"), c.get("colors", []),
                               c.get("speed", "normal"), c.get("direction", "forward"))
        self.led_applied = True

    def step(self, dt):
        temps = self.sensors.read_all()
        targets, fan_status = {}, {}
        fans = self.dev.read_fans() if self.dev else {}

        now = time.monotonic()
        for ch in range(1, (self.dev.fan_count if self.dev else 0) + 1):
            fc = self.cfg["fans"].get(str(ch), config.DEFAULT_FAN)
            sources = fc.get("sources") or self._fallback_sources
            vals = [temps[s]["temp"] for s in sources if s in temps and temps[s]["temp"] is not None]
            temp = max(vals) if vals else None
            curve_mode = fc.get("mode") != "fixed"
            if not curve_mode:
                target = float(fc.get("fixed", 50))
            elif temp is None:
                target = 100.0   # sensor lost -> be safe
            else:
                target = interpolate(fc.get("curve", []), temp)

            # Fan stop with hysteresis: off at/below 'below', on again at/above 'above'
            stop = fc.get("stop") or {}
            stopped = self.stopped.get(ch, False)
            if curve_mode and stop.get("enabled") and temp is not None:
                if stopped and temp >= float(stop.get("above", 50)):
                    stopped = False
                elif not stopped and temp <= float(stop.get("below", 45)):
                    stopped = True
            else:
                stopped = False
            self.stopped[ch] = stopped

            if stopped:
                target = 0.0
            else:
                # Ramp: go up immediately, go down slowly
                prev = self.duty.get(ch)
                if prev and target < prev:
                    target = max(target, prev - float(self.cfg.get("ramp_down", 3.0)) * dt)
            targets[ch] = max(0.0, min(100.0, target))

            # Stall guard: a fan that has spun before but stays at 0 RPM although it
            # should run gets a short 100 % kick
            rpm = fans.get(ch, {}).get("rpm")
            if rpm:
                self.seen_spinning.add(ch)
            if targets[ch] > 0 and rpm == 0 and ch in self.seen_spinning and self.sent.get(ch):
                since = self.stall_since.setdefault(ch, now)
                if now - since > 8:
                    log.warning("fan %d does not spin, kick-starting", ch)
                    self.kick_until[ch] = now + 3
                    self.stall_since.pop(ch, None)
            else:
                self.stall_since.pop(ch, None)
            kick = self.kick_until.get(ch, 0) > now

            fan_status[str(ch)] = dict(fans.get(ch, {}), temp=temp, target=round(targets[ch], 1),
                                       stopped=stopped, kick=kick)

        if self.dev and targets:
            out = {ch: (100.0 if self.kick_until.get(ch, 0) > now else d) for ch, d in targets.items()}
            changed = any(self.sent.get(ch) is None or round(d) != round(self.sent[ch]) for ch, d in out.items())
            try:
                if changed:
                    self.dev.set_duties(out)
                self.sent.update(out)
                self.duty.update(targets)
                if not self.led_applied:
                    self.apply_leds()
                self.error = None
            except DeviceError as e:
                self.error = e.as_dict()
                self.duty, self.sent = {}, {}
                self.led_applied = False

        config.write_status({
            "time": time.time(),
            "pid": os.getpid(),
            "error": self.error,
            "device": None if not self.dev else {
                "name": self.dev.name, "firmware": self.dev.firmware,
                "fans": self.dev.fan_count, "leds": self.dev.led_count,
                "accessories": {str(k): v for k, v in self.dev.accessories.items()},
                "writable": self.dev.writable,
            },
            "sensors": temps,
            "fans": fan_status,
        })

    def run(self):
        signal.signal(signal.SIGTERM, lambda *a: setattr(self, "running", False))
        signal.signal(signal.SIGINT, lambda *a: setattr(self, "running", False))
        signal.signal(signal.SIGHUP, lambda *a: setattr(self, "cfg_mtime", -1))

        self._connect()
        last = time.monotonic()
        suspend = _suspend_offset()

        while self.running:
            now = time.monotonic()
            # Re-initialize after resume, on errors and every 30s (hotplug)
            off = _suspend_offset()
            if off - suspend > 2 or self.error or now - self.last_rescan > 30:
                if off - suspend > 2:
                    log.info("resume detected, re-initializing")
                    if self.dev:
                        self.dev.close()
                    self.dev = None
                    self.sensors.rescan()
                    self._fallback_sources = self.default_sources
                suspend = off
                self.last_rescan = now
                self._connect()

            mt = config.config_mtime()
            if mt != self.cfg_mtime:
                self.cfg_mtime = mt
                self.cfg = self._complete_config(config.load())
                self.cfg_mtime = config.config_mtime()
                self.led_applied = False
                self.duty, self.sent = {}, {}

            try:
                self.step(max(0.0, now - last))
            except Exception:
                log.exception("error in control loop")
            last = now
            time.sleep(max(0.25, float(self.cfg.get("interval", 1.0))))

        # Leave the fans in a safe state
        if self.dev:
            try:
                d = float(self.cfg.get("exit_duty", 60))
                self.dev.set_duties({ch: d for ch in range(1, self.dev.fan_count + 1)})
            except DeviceError:
                pass
            self.dev.close()
        try:
            os.unlink(config.STATUS_FILE)
        except OSError:
            pass


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
    os.makedirs(config.RUNTIME_DIR, mode=0o700, exist_ok=True)
    lock = open(config.LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log.error("cam4linux daemon is already running")
        return 1
    Daemon().run()
    return 0
