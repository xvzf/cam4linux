#!/usr/bin/env python3
"""
CAM4LINUX - a control suite for nzxt devices
Copyright (C) 2016 Matthias Riegler <matthias@xvzf.tech>

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
"""

__all__ = ["grid", "camservice"]
from nzxt.grid import Grid
from nzxt.camservice import Camservice