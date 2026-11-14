#!/usr/bin/env python3
"""
CAM4LINUX - a control suite for nzxt devices

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
"""

import glob
import os

HWMON_ROOT = "/sys/class/hwmon"
HWMON_NAME = "nzxtsmart2"


def find_hwmon(name=HWMON_NAME, root=HWMON_ROOT):
    """Return all hwmon directories whose 'name' matches (sorted)."""
    found = []
    for path in sorted(glob.glob(os.path.join(root, "hwmon*"))):
        try:
            with open(os.path.join(path, "name")) as f:
                if f.read().strip() == name:
                    found.append(path)
        except OSError:
            pass
    return found


class SmartDevice2(object):
    """
    NZXT Smart Device V2 / RGB & Fan Controller (USB 1e71:2006, 2009, 200e, 2010, ...).

    Unlike the old Grid, these are HID devices. Since Linux 5.17 the in-kernel
    driver 'nzxt-smart2' handles the protocol and exposes the fan channels via
    hwmon, so we just talk to sysfs:

        fanN_input   RPM
        currN_input  current in mA
        inN_input    voltage in mV (in0 = fan 1)
        pwmN         duty cycle 0..255 (write requires root)
        pwmN_enable  1 = manual control

    The device has no fan curves of its own - once a duty is set it stays.
    """

    def __init__(self, hwmon=None, index=0):
        super(SmartDevice2, self).__init__()
        if hwmon is None:
            devices = find_hwmon()
            if len(devices) <= index:
                raise RuntimeError(
                    "No NZXT Smart Device V2 found in %s (is the nzxt-smart2 kernel module loaded?)"
                    % HWMON_ROOT)
            hwmon = devices[index]
        self.hwmon = hwmon
        self.channels = sorted(
            int(os.path.basename(p)[3:-len("_input")])
            for p in glob.glob(os.path.join(hwmon, "fan*_input")))

    def _read(self, attr, default=-1):
        try:
            with open(os.path.join(self.hwmon, attr)) as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            return default

    def _write(self, attr, value):
        with open(os.path.join(self.hwmon, attr), "w") as f:
            f.write(str(int(value)))

    # Ports are 0-based like in the Grid class, hwmon channels are 1-based
    def get_rpm(self, index):
        return self._read("fan%d_input" % (index + 1))

    def get_percentage(self, index):
        pwm = self._read("pwm%d" % (index + 1))
        return -1 if pwm < 0 else round(pwm * 100 / 255)

    def get_power(self, index):
        mv = self._read("in%d_input" % index)
        ma = self._read("curr%d_input" % (index + 1))
        if mv < 0 or ma < 0:
            return -1.0
        return round(mv * ma / 1e6, 2)

    def set_percentage(self, index, p):
        ch = index + 1
        if ch not in self.channels or not 0 <= p <= 100:
            return -1
        if self._read("pwm%d_enable" % ch) != 1:
            self._write("pwm%d_enable" % ch, 1)
        self._write("pwm%d" % ch, round(p * 255 / 100))
        return 0

    def get_json(self):
        ports = [c - 1 for c in self.channels]
        return {
            "rpm":     {i: self.get_rpm(i) for i in ports},
            "power":   {i: self.get_power(i) for i in ports},
            "percent": {i: self.get_percentage(i) for i in ports},
            "type": "smartdevice2"
        }

    def set_json(self, toset):
        try:
            values = {int(k): int(v) for k, v in toset.items()}
        except (TypeError, ValueError):
            return "ERROR"
        if any(k + 1 not in self.channels or not 0 <= v <= 100 for k, v in values.items()):
            return "ERROR"
        try:
            for k, v in values.items():
                self.set_percentage(k, v)
        except PermissionError:
            return "ERROR: permission denied (run cam4linux as root)"
        except OSError as e:
            return "ERROR: %s" % e
        return "OK"
