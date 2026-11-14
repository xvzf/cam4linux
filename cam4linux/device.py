"""
NZXT Smart Device V2 / RGB & Fan Controller / HUE 2.

Readings (RPM, voltage, current) come from the in-kernel 'nzxt-smart2' hwmon
driver, which is world readable. Commands (fan duty, LEDs) go to the matching
/dev/hidrawN node, which a udev rule (TAG+="uaccess") makes accessible to the
logged-in user - no root daemon needed.

Protocol bytes follow liquidctl's SmartDevice2 driver
(https://github.com/liquidctl/liquidctl, GPL-3.0-or-later).
"""

import glob
import os
import select

VENDOR = 0x1E71
# product id -> (name, fan channels, led channels)
PRODUCTS = {
    0x2006: ("NZXT Smart Device V2", 3, 2),
    0x200D: ("NZXT Smart Device V2", 3, 2),
    0x200F: ("NZXT Smart Device V2", 3, 2),
    0x2009: ("NZXT RGB & Fan Controller", 3, 2),
    0x200E: ("NZXT RGB & Fan Controller", 3, 2),
    0x2010: ("NZXT RGB & Fan Controller", 3, 2),
    0x2001: ("NZXT HUE 2", 0, 4),
    0x2002: ("NZXT HUE 2 Ambient", 0, 2),
}

ACCESSORIES = {
    0x01: "HUE+ LED Strip", 0x02: "Aer RGB 1", 0x04: "HUE 2 LED Strip 300 mm",
    0x05: "HUE 2 LED Strip 250 mm", 0x06: "HUE 2 LED Strip 200 mm", 0x07: "HUE 2 Cable Comb",
    0x09: "HUE 2 Underglow 300 mm", 0x0A: "HUE 2 Underglow 200 mm", 0x0B: "Aer RGB 2 120 mm",
    0x0C: "Aer RGB 2 140 mm", 0x10: "Kraken X Pump Ring", 0x11: "Kraken X Pump Logo",
    0x13: "F120 RGB", 0x14: "F140 RGB", 0x17: "F140 RGB Core", 0x1B: "F240 RGB Core",
    0x1D: "F360 RGB Core",
}

# mode -> (mode byte, variant, moving flag, min colors, max colors)
COLOR_MODES = {
    "off":                  (0x00, 0x00, 0x00, 0, 0),
    "fixed":                (0x00, 0x00, 0x00, 1, 1),
    "fading":               (0x01, 0x00, 0x00, 1, 8),
    "spectrum-wave":        (0x02, 0x00, 0x00, 0, 0),
    "marquee-3":            (0x03, 0x00, 0x00, 1, 1),
    "marquee-4":            (0x03, 0x01, 0x00, 1, 1),
    "marquee-5":            (0x03, 0x02, 0x00, 1, 1),
    "marquee-6":            (0x03, 0x03, 0x00, 1, 1),
    "covering-marquee":     (0x04, 0x00, 0x00, 1, 8),
    "alternating-3":        (0x05, 0x00, 0x00, 2, 2),
    "alternating-4":        (0x05, 0x01, 0x00, 2, 2),
    "alternating-5":        (0x05, 0x02, 0x00, 2, 2),
    "alternating-6":        (0x05, 0x03, 0x00, 2, 2),
    "moving-alternating-3": (0x05, 0x00, 0x10, 2, 2),
    "moving-alternating-4": (0x05, 0x01, 0x10, 2, 2),
    "moving-alternating-5": (0x05, 0x02, 0x10, 2, 2),
    "moving-alternating-6": (0x05, 0x03, 0x10, 2, 2),
    "pulse":                (0x06, 0x00, 0x00, 1, 8),
    "breathing":            (0x07, 0x00, 0x00, 1, 8),
    "candle":               (0x08, 0x00, 0x00, 1, 1),
    "starry-night":         (0x09, 0x00, 0x00, 1, 1),
    "rainbow-flow":         (0x0B, 0x00, 0x00, 0, 0),
    "super-rainbow":        (0x0C, 0x00, 0x00, 0, 0),
    "rainbow-pulse":        (0x0D, 0x00, 0x00, 0, 0),
}

SPEEDS = ["slowest", "slower", "normal", "faster", "fastest"]
REPORT_LEN = 64


def _read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def _parse_color(c):
    """'#rrggbb' or [r, g, b] -> [r, g, b]"""
    if isinstance(c, str):
        c = c.lstrip("#")
        return [int(c[i:i + 2], 16) for i in (0, 2, 4)]
    return [int(x) & 0xFF for x in c]


class DeviceError(Exception):
    """code is a translation key suffix (error.<code>), args are its parameters."""

    def __init__(self, code, **args):
        super().__init__("%s %s" % (code, args))
        self.code = code
        self.args_ = args

    def as_dict(self):
        return {"code": self.code, "args": self.args_}


def find_devices():
    """Return a list of dicts with hidraw node, hwmon path and product info."""
    found = []
    for hiddir in sorted(glob.glob("/sys/bus/hid/devices/*")):
        # name looks like 0003:1E71:2006.0002
        try:
            _, vid, rest = os.path.basename(hiddir).split(":")
            pid = int(rest.split(".")[0], 16)
            vid = int(vid, 16)
        except ValueError:
            continue
        if vid != VENDOR or pid not in PRODUCTS:
            continue
        hidraw = glob.glob(os.path.join(hiddir, "hidraw", "hidraw*"))
        hwmon = glob.glob(os.path.join(hiddir, "hwmon", "hwmon*"))
        name, fans, leds = PRODUCTS[pid]
        found.append({
            "name": name, "pid": pid, "fans": fans, "leds": leds,
            "hidraw": "/dev/" + os.path.basename(hidraw[0]) if hidraw else None,
            "hwmon": hwmon[0] if hwmon else None,
        })
    return found


class SmartDevice2(object):

    def __init__(self, info):
        self.info = info
        self.name = info["name"]
        self.fan_count = info["fans"]
        self.led_count = info["leds"]
        self.hidraw = info["hidraw"]
        self.hwmon = info["hwmon"]
        self.fd = None
        self.firmware = None
        self.accessories = {}  # led channel (1-based) -> [accessory ids]

    # ---------------------------------------------------------------- hidraw
    def open(self):
        if self.fd is not None:
            return
        if not self.hidraw:
            raise DeviceError("no_hidraw", device=self.name)
        try:
            self.fd = os.open(self.hidraw, os.O_RDWR | os.O_NONBLOCK)
        except PermissionError:
            raise DeviceError("no_access", node=self.hidraw)
        except OSError as e:
            raise DeviceError("open_failed", node=self.hidraw, reason=e.strerror)

    def close(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None

    @property
    def writable(self):
        return self.fd is not None

    def _write(self, data):
        self.open()
        buf = bytes(data) + bytes(REPORT_LEN - len(data))
        try:
            os.write(self.fd, buf)
        except OSError as e:
            self.close()
            raise DeviceError("write_failed", node=self.hidraw, reason=e.strerror)

    def _drain(self):
        while True:
            try:
                if not os.read(self.fd, REPORT_LEN):
                    return
            except BlockingIOError:
                return
            except OSError:
                return

    def _read_until(self, prefixes, timeout=1.0, attempts=24):
        """Read reports until every prefix was seen. Returns {prefix: msg}."""
        res = {}
        for _ in range(attempts):
            r, _, _ = select.select([self.fd], [], [], timeout)
            if not r:
                break
            try:
                msg = os.read(self.fd, REPORT_LEN)
            except BlockingIOError:
                continue
            p = bytes(msg[0:2])
            if p in prefixes and p not in res:
                res[p] = msg
            if len(res) == len(prefixes):
                break
        return res

    def initialize(self):
        """Query firmware version and connected LED accessories."""
        self.open()
        self._drain()
        self._write([0x10, 0x01])  # firmware info
        if self.led_count:
            self._write([0x20, 0x03])  # lighting info
        want = [b"\x11\x01"] + ([b"\x21\x03"] if self.led_count else [])
        msgs = self._read_until(want)

        fw = msgs.get(b"\x11\x01")
        if fw and len(fw) > 0x13:
            self.firmware = "%d.%d.%d" % (fw[0x11], fw[0x12], fw[0x13])

        led = msgs.get(b"\x21\x03")
        self.accessories = {}
        if led and len(led) > 15:
            for c in range(min(led[14], self.led_count)):
                ids = []
                for a in range(6):
                    off = 15 + c * 6 + a
                    if off >= len(led) or led[off] == 0:
                        break
                    ids.append(led[off])
                self.accessories[c + 1] = ids

    # ------------------------------------------------------------------ fans
    def set_duties(self, duties):
        """duties: {channel (1-based): percent}. One HID report for all channels."""
        msg = [0x62, 0x01, 0x00, 0x00, 0x00, 0x00]
        for ch, duty in duties.items():
            if 1 <= ch <= self.fan_count:
                msg[2] |= 1 << (ch - 1)
                msg[2 + ch] = max(0, min(100, int(round(duty))))
        if msg[2]:
            self._write(msg)

    def _hw(self, attr):
        if not self.hwmon:
            return None
        v = _read(os.path.join(self.hwmon, attr))
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    def read_fans(self):
        """{channel: {rpm, duty, mode, watts}} from hwmon (read only)."""
        res = {}
        for ch in range(1, self.fan_count + 1):
            rpm = self._hw("fan%d_input" % ch)
            pwm = self._hw("pwm%d" % ch)
            mode = self._hw("pwm%d_mode" % ch)
            mv = self._hw("in%d_input" % (ch - 1))
            ma = self._hw("curr%d_input" % ch)
            res[ch] = {
                "rpm": rpm,
                "duty": None if pwm is None else round(pwm * 100 / 255),
                "mode": {0: "DC", 1: "PWM"}.get(mode),
                "watts": None if mv is None or ma is None else round(mv * ma / 1e6, 2),
            }
        return res

    # ------------------------------------------------------------------ LEDs
    def set_color(self, channel, mode, colors=(), speed="normal", direction="forward"):
        """channel: 1-based LED channel or 0 for all channels (sync)."""
        if mode not in COLOR_MODES:
            raise DeviceError("unknown_mode", mode=mode)
        if not self.led_count:
            return
        mval, variant, moving, mincol, maxcol = COLOR_MODES[mode]
        cid = (1 << self.led_count) - 1 if channel == 0 else 1 << (channel - 1)

        # Device expects GRB
        colors = [[g, r, b] for r, g, b in (_parse_color(c) for c in colors)]
        if maxcol == 0:
            colors = [[0, 0, 0]]
        else:
            if len(colors) < mincol:
                colors += [[0xFF, 0xFF, 0xFF]] * (mincol - len(colors))
            colors = colors[:maxcol]

        sval = SPEEDS.index(speed) if speed in SPEEDS else 2
        byte7 = (moving & 0x10) >> 4
        byte8 = 1 if direction == "backward" else 0
        byte9 = variant if mval == 0x03 else len(colors)
        byte10 = variant if mval == 0x05 else 0x00
        payload = [0x28, 0x03, cid, 0x00, mval, sval, byte7, byte8, byte9, byte10]
        for c in colors:
            payload += c
        self._write(payload)
