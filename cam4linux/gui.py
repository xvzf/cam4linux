"""cam4linux GUI (PySide6). Edits the config, shows live data, keeps the daemon running."""

import copy
import os
import shutil
import subprocess
import sys
import tempfile
import time

from PySide6.QtCore import Qt, QTimer, QPointF, QRectF, Signal
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPainterPath, QPen, QFont
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFormLayout, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPushButton, QRadioButton, QSizePolicy, QSlider, QSpinBox,
    QTabWidget, QToolButton, QVBoxLayout, QWidget, QButtonGroup, QTreeWidget, QTreeWidgetItem,
)

from . import config, i18n
from .device import ACCESSORIES, COLOR_MODES, SPEEDS
from .daemon import interpolate
from .i18n import tr

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
UDEV_RULE = "/etc/udev/rules.d/70-cam4linux.rules"
SERVICE = "cam4linux.service"

# Order in the mode combo box; names come from the language files (led.mode.<key>)
LED_MODES = ["fixed", "breathing", "fading", "pulse", "spectrum-wave", "rainbow-flow",
             "super-rainbow", "rainbow-pulse", "marquee-4", "covering-marquee", "alternating-4",
             "moving-alternating-4", "candle", "starry-night", "off"]
PRESETS = ["silent", "balanced", "performance", "full"]


def sensor_name(info, sid=""):
    if not info:
        return tr("fan.source_missing", id=sid)
    group = tr("sensor.group." + info["group"]) if info.get("group") else info.get("name", "?")
    if info.get("num"):
        group = tr("sensor.group_num", group=group, num=info["num"])
    return tr("sensor.format", group=group, label=info.get("label", ""))


def fan_name(fc, ch):
    return (fc or {}).get("name") or tr("fan.default_name", n=ch)


# --------------------------------------------------------------------------- curve editor
class CurveWidget(QWidget):
    changed = Signal()

    T_MIN, T_MAX = 20.0, 100.0
    HIT = 9

    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = [[30, 30], [85, 100]]
        self.current_temp = None
        self.stopped = False      # fan currently switched off by the fan stop
        self.dc_floor = None      # DC fan: duties below this have no effect
        self.stop = None          # (below, above) when the fan stop is enabled
        self.drag = None
        self.hover = None
        self.setMinimumSize(420, 260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self.setToolTip(tr("curve.tooltip"))

    def set_points(self, pts):
        self.points = sorted([list(map(float, p)) for p in pts])
        self.update()

    def set_current(self, temp, stopped=False):
        self.current_temp = temp
        self.stopped = stopped
        self.update()

    def set_zones(self, dc_floor=None, stop=None):
        self.dc_floor = dc_floor
        self.stop = stop
        self.update()

    # geometry
    def _plot(self):
        return QRectF(48, 14, self.width() - 64, self.height() - 46)

    def _to_px(self, t, d):
        r = self._plot()
        x = r.left() + (t - self.T_MIN) / (self.T_MAX - self.T_MIN) * r.width()
        y = r.bottom() - d / 100.0 * r.height()
        return QPointF(x, y)

    def _from_px(self, p):
        r = self._plot()
        t = self.T_MIN + (p.x() - r.left()) / r.width() * (self.T_MAX - self.T_MIN)
        d = (r.bottom() - p.y()) / r.height() * 100.0
        return t, d

    def _hit(self, pos):
        for i, (t, d) in enumerate(self.points):
            q = self._to_px(t, d)
            if abs(q.x() - pos.x()) <= self.HIT and abs(q.y() - pos.y()) <= self.HIT:
                return i
        return None

    # painting
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        fg = pal.color(pal.ColorRole.WindowText)
        accent = pal.color(pal.ColorRole.Highlight)
        grid = QColor(fg)
        grid.setAlpha(40)
        r = self._plot()

        p.fillRect(r, pal.color(pal.ColorRole.Base))
        small = QFont(self.font())
        small.setPointSizeF(max(7.0, small.pointSizeF() * 0.85))
        p.setFont(small)
        for t in range(int(self.T_MIN), int(self.T_MAX) + 1, 10):
            x = self._to_px(t, 0).x()
            p.setPen(QPen(grid, 1))
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
            p.setPen(fg)
            p.drawText(QRectF(x - 20, r.bottom() + 4, 40, 16), Qt.AlignCenter, "%d°" % t)
        for d in range(0, 101, 20):
            y = self._to_px(self.T_MIN, d).y()
            p.setPen(QPen(grid, 1))
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
            p.setPen(fg)
            p.drawText(QRectF(0, y - 8, 42, 16), Qt.AlignRight | Qt.AlignVCenter, "%d%%" % d)
        p.setPen(fg)
        p.drawText(QRectF(r.left(), r.bottom() + 18, r.width(), 14), Qt.AlignCenter, tr("curve.axis_temp"))

        # DC fan: hatched band where the controller does not lower the voltage further
        if self.dc_floor:
            top = self._to_px(self.T_MIN, self.dc_floor).y()
            band = QRectF(r.left(), top, r.width(), r.bottom() - top)
            hatch = QColor(fg)
            hatch.setAlpha(28)
            p.fillRect(band, QBrush(hatch, Qt.BDiagPattern))
            p.setPen(QPen(hatch, 1, Qt.DashLine))
            p.drawLine(QPointF(r.left(), top), QPointF(r.right(), top))
            muted = QColor(fg)
            muted.setAlpha(150)
            p.setPen(muted)
            p.drawText(band.adjusted(0, 0, -6, -4), Qt.AlignRight | Qt.AlignBottom,
                       tr("curve.dc_zone", floor=self.dc_floor))

        # Fan stop: off below 'below', back on at 'above'
        if self.stop:
            below, above = self.stop
            xb = self._to_px(max(self.T_MIN, min(self.T_MAX, below)), 0).x()
            xa = self._to_px(max(self.T_MIN, min(self.T_MAX, above)), 0).x()
            red = QColor("#e5534b")
            red.setAlpha(30)
            p.fillRect(QRectF(r.left(), r.top(), xb - r.left(), r.height()), red)
            red.setAlpha(14)
            p.fillRect(QRectF(xb, r.top(), xa - xb, r.height()), red)
            red.setAlpha(170)
            p.setPen(QPen(red, 1, Qt.DashLine))
            p.drawLine(QPointF(xa, r.top()), QPointF(xa, r.bottom()))
            p.setPen(red)
            p.drawText(QRectF(r.left(), r.top() + 20, max(0.0, xb - r.left()), 16), Qt.AlignCenter,
                       tr("curve.stop_zone"))
            p.drawText(QRectF(xa + 4, r.bottom() - 20, 80, 16), Qt.AlignLeft, tr("curve.stop_on"))

        # curve (extended flat to the edges)
        pts = sorted(self.points)
        path = QPainterPath(self._to_px(self.T_MIN, interpolate(pts, self.T_MIN)))
        for t, d in pts:
            if self.T_MIN <= t <= self.T_MAX:
                path.lineTo(self._to_px(t, d))
        path.lineTo(self._to_px(self.T_MAX, interpolate(pts, self.T_MAX)))
        fill = QPainterPath(path)
        fill.lineTo(self._to_px(self.T_MAX, 0))
        fill.lineTo(self._to_px(self.T_MIN, 0))
        fill.closeSubpath()
        area = QColor(accent)
        area.setAlpha(45)
        p.fillPath(fill, area)
        p.setPen(QPen(accent, 2.5))
        p.drawPath(path)

        # current operating point
        if self.current_temp is not None:
            t = max(self.T_MIN, min(self.T_MAX, self.current_temp))
            d = 0 if self.stopped else interpolate(pts, self.current_temp)
            c = QColor("#e5534b")
            p.setPen(QPen(c, 1.5, Qt.DashLine))
            x = self._to_px(t, 0).x()
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
            p.setBrush(c)
            p.setPen(Qt.NoPen)
            p.drawEllipse(self._to_px(t, d), 5, 5)
            p.setPen(c)
            label = (tr("curve.marker_off", temp="%.0f" % self.current_temp) if self.stopped
                     else "%.0f °C → %.0f %%" % (self.current_temp, d))
            p.drawText(QRectF(x + 6, r.top() + 2, 160, 16), Qt.AlignLeft, label)

        # handles
        for i, (t, d) in enumerate(pts):
            q = self._to_px(t, d)
            p.setPen(QPen(pal.color(pal.ColorRole.Base), 2))
            p.setBrush(accent.lighter(130) if i in (self.drag, self.hover) else accent)
            p.drawEllipse(q, 6, 6)
            if i in (self.drag, self.hover):
                p.setPen(fg)
                p.drawText(QRectF(q.x() - 50, q.y() - 26, 100, 16), Qt.AlignCenter,
                           "%.0f °C · %.0f %%" % (t, d))
        p.end()

    # interaction
    def mousePressEvent(self, ev):
        i = self._hit(ev.position())
        if ev.button() == Qt.RightButton and i is not None and len(self.points) > 2:
            del self.points[i]
            self.hover = None
            self.update()
            self.changed.emit()
        elif ev.button() == Qt.LeftButton:
            self.drag = i

    def mouseDoubleClickEvent(self, ev):
        if self._hit(ev.position()) is not None:
            return
        t, d = self._from_px(ev.position())
        if self.T_MIN <= t <= self.T_MAX:
            self.points.append([round(t), round(max(0, min(100, d)))])
            self.points.sort()
            self.update()
            self.changed.emit()

    def mouseMoveEvent(self, ev):
        if self.drag is None:
            h = self._hit(ev.position())
            if h != self.hover:
                self.hover = h
                self.update()
            return
        t, d = self._from_px(ev.position())
        lo = self.points[self.drag - 1][0] + 1 if self.drag > 0 else 0
        hi = self.points[self.drag + 1][0] - 1 if self.drag < len(self.points) - 1 else 110
        self.points[self.drag] = [round(max(lo, min(hi, t))), round(max(0, min(100, d)))]
        self.update()
        self.changed.emit()

    def mouseReleaseEvent(self, ev):
        self.drag = None
        self.update()


# --------------------------------------------------------------------------- small widgets
class ColorButton(QToolButton):
    changed = Signal()

    def __init__(self, color="#ffffff"):
        super().__init__()
        self.setFixedSize(34, 34)
        self.set_color(color)
        self.clicked.connect(self._pick)

    def set_color(self, c):
        self.color = QColor(c).name()
        self.setStyleSheet("QToolButton { background: %s; border: 1px solid palette(mid); border-radius: 6px; }"
                           % self.color)
        self.setToolTip(self.color)

    def _pick(self):
        c = QColorDialog.getColor(QColor(self.color), self, tr("led.pick_color"))
        if c.isValid():
            self.set_color(c.name())
            self.changed.emit()


class FanCard(QFrame):
    def __init__(self, ch, on_click):
        super().__init__()
        self.ch = ch
        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)
        self._on_click = on_click
        lay = QVBoxLayout(self)
        self.title = QLabel()
        f = self.title.font()
        f.setBold(True)
        self.title.setFont(f)
        self.rpm = QLabel("– RPM")
        f2 = self.rpm.font()
        f2.setPointSizeF(f2.pointSizeF() * 1.6)
        self.rpm.setFont(f2)
        self.info = QLabel()
        self.info.setStyleSheet("color: palette(placeholder-text);")
        for w in (self.title, self.rpm, self.info):
            lay.addWidget(w)

    def set_selected(self, sel):
        self.setStyleSheet("FanCard { border: 2px solid %s; border-radius: 8px; }"
                           % ("palette(highlight)" if sel else "palette(mid)"))

    def mousePressEvent(self, ev):
        self._on_click(self.ch)


# --------------------------------------------------------------------------- main window
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("cam4linux")
        icon = os.path.join(DATA_DIR, "cam4linux.svg")
        if os.path.exists(icon):
            self.setWindowIcon(QIcon(icon))
        self.resize(980, 680)

        self.cfg = config.load()
        self.cfg_mtime = config.config_mtime()
        self.status = None
        self.loading = False
        self.sel_fan = 1
        self.sel_led = 1
        self.daemon_started = 0.0

        self.save_timer = QTimer(self, singleShot=True, interval=350)
        self.save_timer.timeout.connect(self._save)

        central = QWidget()
        root = QVBoxLayout(central)
        self.setCentralWidget(central)

        # header
        head = QHBoxLayout()
        self.dev_label = QLabel(tr("header.searching"))
        f = self.dev_label.font()
        f.setPointSizeF(f.pointSizeF() * 1.3)
        f.setBold(True)
        self.dev_label.setFont(f)
        self.svc_label = QLabel()
        head.addWidget(self.dev_label)
        head.addStretch()
        head.addWidget(self.svc_label)
        root.addLayout(head)

        # problem banner
        self.banner = QFrame()
        self.banner.setStyleSheet("QFrame { background: rgba(229,83,75,0.15); border-radius: 6px; }")
        bl = QHBoxLayout(self.banner)
        self.banner_text = QLabel()
        self.banner_text.setWordWrap(True)
        self.banner_btn = QPushButton()
        self.banner_btn.clicked.connect(self._banner_action)
        bl.addWidget(self.banner_text, 1)
        bl.addWidget(self.banner_btn)
        self.banner.hide()
        root.addWidget(self.banner)

        tabs = QTabWidget()
        tabs.addTab(self._build_fans(), tr("tab.fans"))
        tabs.addTab(self._build_leds(), tr("tab.lighting"))
        tabs.addTab(self._build_settings(), tr("tab.settings"))
        root.addWidget(tabs, 1)

        hint = QLabel(tr("hint.background"))
        hint.setStyleSheet("color: palette(placeholder-text);")
        root.addWidget(hint)

        self.timer = QTimer(self, interval=1000)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()

        self.ensure_daemon()
        self.refresh()
        self._load_fan_editor()
        self._load_led_editor()

    # ------------------------------------------------------------------ fans tab
    def _build_fans(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        self.cards_lay = QHBoxLayout()
        self.cards = {}
        lay.addLayout(self.cards_lay)

        box = QGroupBox()
        bl = QGridLayout(box)
        self.fan_name = QLineEdit()
        self.fan_name.textEdited.connect(self._fan_edited)
        self.rb_curve = QRadioButton(tr("fan.mode_curve"))
        self.rb_fixed = QRadioButton(tr("fan.mode_fixed"))
        grp = QButtonGroup(w)
        grp.addButton(self.rb_curve)
        grp.addButton(self.rb_fixed)
        self.rb_curve.toggled.connect(self._fan_edited)
        self.fixed_slider = QSlider(Qt.Horizontal)
        self.fixed_slider.setRange(0, 100)
        self.fixed_label = QLabel()
        self.fixed_slider.valueChanged.connect(self._fan_edited)

        top = QHBoxLayout()
        top.addWidget(QLabel(tr("fan.name")))
        top.addWidget(self.fan_name)
        top.addSpacing(20)
        top.addWidget(self.rb_curve)
        top.addWidget(self.rb_fixed)
        top.addWidget(self.fixed_slider, 1)
        top.addWidget(self.fixed_label)
        bl.addLayout(top, 0, 0, 1, 2)

        stoprow = QHBoxLayout()
        self.stop_enabled = QCheckBox(tr("fan.stop"))
        self.stop_enabled.setToolTip(tr("fan.stop_tooltip"))
        self.stop_below = QSpinBox(minimum=0, maximum=95, suffix=" °C")
        self.stop_above = QSpinBox(minimum=2, maximum=100, suffix=" °C")
        self.stop_enabled.toggled.connect(self._fan_edited)
        self.stop_below.valueChanged.connect(lambda v: self._stop_changed("below"))
        self.stop_above.valueChanged.connect(lambda v: self._stop_changed("above"))
        stoprow.addWidget(self.stop_enabled)
        stoprow.addSpacing(12)
        stoprow.addWidget(QLabel(tr("fan.stop_below")))
        stoprow.addWidget(self.stop_below)
        stoprow.addSpacing(12)
        stoprow.addWidget(QLabel(tr("fan.stop_above")))
        stoprow.addWidget(self.stop_above)
        stoprow.addStretch()
        self.dc_hint = QLabel()
        self.dc_hint.setStyleSheet("color: palette(placeholder-text);")
        stoprow.addWidget(self.dc_hint)
        bl.addLayout(stoprow, 2, 0, 1, 2)

        self.curve = CurveWidget()
        self.curve.changed.connect(self._fan_edited)
        bl.addWidget(self.curve, 1, 0)

        side = QVBoxLayout()
        side.addWidget(QLabel(tr("fan.sources")))
        self.sources = QListWidget()
        self.sources.itemChanged.connect(self._fan_edited)
        side.addWidget(self.sources, 1)
        side.addWidget(QLabel(tr("fan.presets")))
        pr = QGridLayout()
        for i, key in enumerate(PRESETS):
            b = QPushButton(tr("preset." + key))
            b.clicked.connect(lambda _=False, k=key: self._preset(k))
            pr.addWidget(b, i // 2, i % 2)
        side.addLayout(pr)
        copy_btn = QPushButton(tr("fan.copy_all"))
        copy_btn.clicked.connect(self._copy_to_all)
        side.addWidget(copy_btn)
        bl.addLayout(side, 1, 1)
        bl.setColumnStretch(0, 3)
        bl.setColumnStretch(1, 1)
        lay.addWidget(box, 1)
        self.fan_box = box
        return w

    def _ensure_cards(self, n):
        if len(self.cards) == n:
            return
        for c in self.cards.values():
            c.deleteLater()
        self.cards = {}
        for ch in range(1, n + 1):
            card = FanCard(ch, self._select_fan)
            self.cards[ch] = card
            self.cards_lay.addWidget(card)
        self._select_fan(min(self.sel_fan, n) if n else 1)

    def _select_fan(self, ch):
        self.sel_fan = ch
        for c, card in self.cards.items():
            card.set_selected(c == ch)
        self._load_fan_editor()

    def _fan_cfg(self, ch=None):
        ch = str(ch or self.sel_fan)
        return self.cfg["fans"].setdefault(ch, config.fan_defaults(int(ch), []))

    def _load_fan_editor(self):
        self.loading = True
        fc = self._fan_cfg()
        self.fan_box.setTitle(fan_name(fc, self.sel_fan))
        self.fan_name.setText(fc.get("name", ""))
        self.fan_name.setPlaceholderText(tr("fan.default_name", n=self.sel_fan))
        curve_mode = fc.get("mode", "curve") == "curve"
        self.rb_curve.setChecked(curve_mode)
        self.rb_fixed.setChecked(not curve_mode)
        self.fixed_slider.setValue(int(fc.get("fixed", 50)))
        self.fixed_label.setText("%d %%" % self.fixed_slider.value())
        self.fixed_slider.setEnabled(not curve_mode)
        self.curve.setEnabled(curve_mode)
        self.curve.set_points(fc.get("curve", config.PRESETS["balanced"]))
        self._fill_sources(fc.get("sources", []))
        st = fc.get("stop") or {}
        self.stop_enabled.setChecked(bool(st.get("enabled")))
        self.stop_below.setValue(int(st.get("below", 40)))
        self.stop_above.setValue(int(st.get("above", 45)))
        self._update_stop_widgets(curve_mode)
        self.loading = False

    def _fill_sources(self, selected):
        sensors = (self.status or {}).get("sensors", {})
        ids = sorted(sensors, key=lambda s: (not s.startswith(("hwmon/k10", "hwmon/core", "nvidia")),
                                             sensor_name(sensors[s])))
        for s in selected:
            if s not in ids:
                ids.append(s)
        self.sources.blockSignals(True)
        self.sources.clear()
        for sid in ids:
            it = QListWidgetItem(self._source_text(sensors.get(sid), sid))
            it.setData(Qt.UserRole, sid)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if sid in selected else Qt.Unchecked)
            self.sources.addItem(it)
        self.sources.blockSignals(False)

    @staticmethod
    def _source_text(info, sid=""):
        t = (info or {}).get("temp")
        return "%s   %s" % (sensor_name(info, sid), "–" if t is None else "%.0f °C" % t)

    def _fan_edited(self, *a):
        if self.loading:
            return
        fc = self._fan_cfg()
        fc["name"] = self.fan_name.text()
        fc["mode"] = "curve" if self.rb_curve.isChecked() else "fixed"
        fc["fixed"] = self.fixed_slider.value()
        fc["curve"] = [[int(t), int(d)] for t, d in self.curve.points]
        fc["stop"] = {"enabled": self.stop_enabled.isChecked(),
                      "below": self.stop_below.value(), "above": self.stop_above.value()}
        self._update_stop_widgets(fc["mode"] == "curve")
        fc["sources"] = [self.sources.item(i).data(Qt.UserRole) for i in range(self.sources.count())
                         if self.sources.item(i).checkState() == Qt.Checked]
        self.fixed_label.setText("%d %%" % fc["fixed"])
        self.fixed_slider.setEnabled(fc["mode"] == "fixed")
        self.curve.setEnabled(fc["mode"] == "curve")
        self.fan_box.setTitle(fan_name(fc, self.sel_fan))
        self.schedule_save()

    def _stop_changed(self, which):
        # keep at least 2 °C between "off" and "on" (hysteresis)
        if self.stop_above.value() < self.stop_below.value() + 2:
            if which == "below":
                self.stop_above.setValue(self.stop_below.value() + 2)
            else:
                self.stop_below.setValue(max(0, self.stop_above.value() - 2))
        self._fan_edited()

    def _update_stop_widgets(self, curve_mode):
        on = self.stop_enabled.isChecked()
        self.stop_enabled.setEnabled(curve_mode)
        self.stop_below.setEnabled(curve_mode and on)
        self.stop_above.setEnabled(curve_mode and on)
        self._update_zones()

    def _update_zones(self):
        f = ((self.status or {}).get("fans") or {}).get(str(self.sel_fan), {})
        dc = f.get("mode") == "DC"
        self.dc_hint.setText(tr("fan.dc_hint", floor=config.DC_FLOOR) if dc else "")
        stop = None
        if self.stop_enabled.isChecked() and self.rb_curve.isChecked():
            stop = (self.stop_below.value(), self.stop_above.value())
        self.curve.set_zones(config.DC_FLOOR if dc else None, stop)

    def _preset(self, key):
        self.rb_curve.setChecked(True)
        self.curve.set_points(config.PRESETS[key])
        self._fan_edited()

    def _copy_to_all(self):
        src = self._fan_cfg()
        for ch in self.cards:
            if ch != self.sel_fan:
                fc = self._fan_cfg(ch)
                for k in ("mode", "fixed", "curve", "sources", "stop"):
                    fc[k] = copy.deepcopy(src[k])
        self.schedule_save()

    # ------------------------------------------------------------------ LED tab
    def _build_leds(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        top = QHBoxLayout()
        self.led_sync = QCheckBox(tr("led.sync"))
        self.led_sync.toggled.connect(self._led_sync_toggled)
        self.led_channel = QComboBox()
        self.led_channel.currentIndexChanged.connect(self._led_channel_changed)
        top.addWidget(self.led_sync)
        top.addWidget(QLabel(tr("led.channel")))
        top.addWidget(self.led_channel)
        top.addStretch()
        lay.addLayout(top)

        self.acc_label = QLabel()
        self.acc_label.setWordWrap(True)
        self.acc_label.setStyleSheet("color: palette(placeholder-text);")
        lay.addWidget(self.acc_label)

        box = QGroupBox(tr("led.effect"))
        form = QFormLayout(box)
        self.led_mode = QComboBox()
        for key in LED_MODES:
            self.led_mode.addItem(tr("led.mode." + key), key)
        self.led_mode.currentIndexChanged.connect(self._led_edited)
        form.addRow(tr("led.mode"), self.led_mode)

        colrow = QHBoxLayout()
        self.color_btns = []
        for i in range(8):
            b = ColorButton()
            b.changed.connect(self._led_edited)
            self.color_btns.append(b)
            colrow.addWidget(b)
        self.col_add = QToolButton(text="+")
        self.col_del = QToolButton(text="−")
        self.col_add.clicked.connect(lambda: self._color_count(+1))
        self.col_del.clicked.connect(lambda: self._color_count(-1))
        colrow.addWidget(self.col_add)
        colrow.addWidget(self.col_del)
        colrow.addStretch()
        self.colors_row = QWidget()
        self.colors_row.setLayout(colrow)
        form.addRow(tr("led.colors"), self.colors_row)

        quick = QHBoxLayout()
        for c in ["#ff0000", "#ff7a00", "#ffd000", "#00ff40", "#00e5ff", "#3c78ff", "#8a2be2", "#ff00c8", "#ffffff"]:
            qb = QToolButton()
            qb.setFixedSize(22, 22)
            qb.setStyleSheet("QToolButton { background: %s; border: 1px solid palette(mid); border-radius: 11px; }" % c)
            qb.clicked.connect(lambda _=False, c=c: self._quick_color(c))
            quick.addWidget(qb)
        quick.addStretch()
        self.quick_row = QWidget()
        self.quick_row.setLayout(quick)
        form.addRow(tr("led.quick"), self.quick_row)

        self.led_speed = QSlider(Qt.Horizontal)
        self.led_speed.setRange(0, 4)
        self.led_speed.setPageStep(1)
        self.led_speed.setTickPosition(QSlider.TicksBelow)
        self.led_speed_label = QLabel()
        self.led_speed.valueChanged.connect(self._led_edited)
        sp = QHBoxLayout()
        sp.addWidget(self.led_speed, 1)
        sp.addWidget(self.led_speed_label)
        form.addRow(tr("led.speed"), sp)

        self.led_backward = QCheckBox(tr("led.backward"))
        self.led_backward.toggled.connect(self._led_edited)
        form.addRow(tr("led.direction"), self.led_backward)
        lay.addWidget(box)
        lay.addStretch()
        self.led_ncolors = 1
        return w

    def _led_cfg(self):
        light = self.cfg.setdefault("lighting", {"sync": True, "channels": {}})
        ch = "1" if light.get("sync", True) else str(self.sel_led)
        return light.setdefault("channels", {}).setdefault(ch, copy.deepcopy(config.DEFAULT_LED))

    def _update_led_channels(self, n, acc):
        if self.led_channel.count() != n:
            self.led_channel.blockSignals(True)
            self.led_channel.clear()
            for c in range(1, n + 1):
                self.led_channel.addItem(tr("led.channel_name", n=c), c)
            self.led_channel.setCurrentIndex(max(0, self.sel_led - 1))
            self.led_channel.blockSignals(False)
        lines = []
        for c in range(1, n + 1):
            names = [ACCESSORIES.get(a) or tr("led.accessory_unknown", id="%02x" % a)
                     for a in acc.get(str(c), [])]
            lines.append("%s: %s" % (tr("led.channel_name", n=c),
                                     ", ".join(names) if names else tr("led.nothing")))
        self.acc_label.setText(tr("led.detected", list=" · ".join(lines)) if n else tr("led.no_channels"))

    def _load_led_editor(self):
        self.loading = True
        sync = self.cfg.get("lighting", {}).get("sync", True)
        self.led_sync.setChecked(sync)
        self.led_channel.setEnabled(not sync)
        lc = self._led_cfg()
        idx = self.led_mode.findData(lc.get("mode", "fixed"))
        self.led_mode.setCurrentIndex(max(0, idx))
        cols = lc.get("colors") or ["#3c78ff"]
        for i, b in enumerate(self.color_btns):
            b.set_color(cols[i] if i < len(cols) else "#ffffff")
        self.led_ncolors = len(cols)
        self.led_speed.setValue(SPEEDS.index(lc.get("speed", "normal")) if lc.get("speed") in SPEEDS else 2)
        self.led_backward.setChecked(lc.get("direction") == "backward")
        self.loading = False
        self._led_visibility()

    def _led_visibility(self):
        mode = self.led_mode.currentData()
        _, _, _, mincol, maxcol = COLOR_MODES[mode]
        n = max(mincol, min(maxcol, self.led_ncolors))
        self.led_ncolors = n if maxcol else self.led_ncolors
        for i, b in enumerate(self.color_btns):
            b.setVisible(maxcol > 0 and i < n)
        self.colors_row.setVisible(maxcol > 0)
        self.quick_row.setVisible(maxcol > 0)
        self.col_add.setVisible(maxcol > 1)
        self.col_del.setVisible(maxcol > 1)
        self.col_add.setEnabled(n < maxcol)
        self.col_del.setEnabled(n > max(1, mincol))
        animated = mode not in ("fixed", "off")
        self.led_speed.setEnabled(animated)
        self.led_backward.setEnabled(animated)
        self.led_speed_label.setText(tr("led.speed." + SPEEDS[self.led_speed.value()]))

    def _color_count(self, delta):
        self.led_ncolors += delta
        self._led_edited()

    def _quick_color(self, c):
        self.color_btns[0].set_color(c)
        self._led_edited()

    def _led_sync_toggled(self, on):
        if self.loading:
            return
        self.cfg.setdefault("lighting", {})["sync"] = on
        self._load_led_editor()
        self.schedule_save()

    def _led_channel_changed(self, idx):
        if idx >= 0:
            self.sel_led = idx + 1
            self._load_led_editor()

    def _led_edited(self, *a):
        if self.loading:
            return
        self._led_visibility()
        lc = self._led_cfg()
        lc["mode"] = self.led_mode.currentData()
        maxcol = COLOR_MODES[lc["mode"]][4]
        lc["colors"] = [b.color for b in self.color_btns[:max(1, min(self.led_ncolors, maxcol or 1))]]
        lc["speed"] = SPEEDS[self.led_speed.value()]
        lc["direction"] = "backward" if self.led_backward.isChecked() else "forward"
        self.schedule_save()

    # ------------------------------------------------------------------ settings tab
    def _build_settings(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        box0 = QGroupBox(tr("settings.general"))
        f0 = QFormLayout(box0)
        self.s_lang = QComboBox()
        self.s_lang.addItem(tr("settings.language_auto"), "auto")
        for code, name in i18n.available().items():
            self.s_lang.addItem(name, code)
        idx = self.s_lang.findData(self.cfg.get("language", "auto"))
        self.s_lang.setCurrentIndex(max(0, idx))
        self.s_lang.currentIndexChanged.connect(self._language_changed)
        f0.addRow(tr("settings.language"), self.s_lang)
        lay.addWidget(box0)

        box = QGroupBox(tr("settings.control"))
        form = QFormLayout(box)
        self.s_interval = QDoubleSpinBox(minimum=0.5, maximum=10, singleStep=0.5, suffix=" s")
        self.s_interval.setValue(float(self.cfg.get("interval", 1.0)))
        self.s_ramp = QDoubleSpinBox(minimum=0.5, maximum=100, singleStep=0.5, suffix=" %/s")
        self.s_ramp.setValue(float(self.cfg.get("ramp_down", 3.0)))
        self.s_exit = QSpinBox(minimum=20, maximum=100, suffix=" %")
        self.s_exit.setValue(int(self.cfg.get("exit_duty", 60)))
        for wdg in (self.s_interval, self.s_ramp, self.s_exit):
            wdg.valueChanged.connect(self._settings_edited)
        form.addRow(tr("settings.interval"), self.s_interval)
        form.addRow(tr("settings.ramp"), self.s_ramp)
        form.addRow(tr("settings.exit"), self.s_exit)
        lay.addWidget(box)

        box2 = QGroupBox(tr("settings.system"))
        v = QVBoxLayout(box2)
        self.autostart = QCheckBox(tr("settings.autostart"))
        self.autostart.setChecked(self._systemctl("is-enabled", SERVICE) == 0)
        self.autostart.toggled.connect(self._toggle_autostart)
        v.addWidget(self.autostart)
        hb = QHBoxLayout()
        b1 = QPushButton(tr("settings.udev"))
        b1.clicked.connect(self.install_udev)
        b2 = QPushButton(tr("settings.restart"))
        b2.clicked.connect(self.restart_daemon)
        hb.addWidget(b1)
        hb.addWidget(b2)
        hb.addStretch()
        v.addLayout(hb)
        lay.addWidget(box2)

        box3 = QGroupBox(tr("settings.sensors"))
        v3 = QVBoxLayout(box3)
        self.sensor_tree = QTreeWidget()
        self.sensor_tree.setHeaderLabels([tr("settings.col_sensor"), tr("settings.col_temp")])
        self.sensor_tree.setRootIsDecorated(False)
        v3.addWidget(self.sensor_tree)
        lay.addWidget(box3, 1)
        return w

    def _settings_edited(self):
        self.cfg["interval"] = self.s_interval.value()
        self.cfg["ramp_down"] = self.s_ramp.value()
        self.cfg["exit_duty"] = self.s_exit.value()
        self.schedule_save()

    def _language_changed(self):
        self.cfg["language"] = self.s_lang.currentData()
        self._save()
        i18n.setup(self.cfg["language"])
        # Rebuild the window so every text is translated
        new = MainWindow()
        new.resize(self.size())
        new.move(self.pos())
        QApplication.instance().main_window = new
        new.show()
        self.timer.stop()
        self.close()

    # ------------------------------------------------------------------ saving
    def schedule_save(self):
        self.save_timer.start()

    def _save(self):
        config.save(self.cfg)
        self.cfg_mtime = config.config_mtime()

    # ------------------------------------------------------------------ daemon / system
    @staticmethod
    def _systemctl(*args):
        if not shutil.which("systemctl"):
            return 1
        return subprocess.run(["systemctl", "--user", *args], capture_output=True).returncode

    def _service_installed(self):
        return self._systemctl("cat", SERVICE) == 0

    def daemon_alive(self):
        st = config.read_status()
        if not st or time.time() - st.get("time", 0) > 6:
            return False
        try:
            os.kill(st["pid"], 0)
            return True
        except (OSError, KeyError, TypeError):
            return False

    def ensure_daemon(self):
        if self.daemon_alive() or time.monotonic() - self.daemon_started < 8:
            return
        self.daemon_started = time.monotonic()
        if self._service_installed() and self._systemctl("start", SERVICE) == 0:
            return
        env = dict(os.environ)
        pkg_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env["PYTHONPATH"] = pkg_parent + os.pathsep + env.get("PYTHONPATH", "")
        subprocess.Popen([sys.executable, "-m", "cam4linux", "--daemon"], env=env,
                         start_new_session=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def restart_daemon(self):
        if self._service_installed() and self._systemctl("is-active", SERVICE) == 0:
            self._systemctl("restart", SERVICE)
        else:
            st = config.read_status()
            if st and st.get("pid"):
                try:
                    os.kill(st["pid"], 15)
                    time.sleep(1.5)
                except OSError:
                    pass
            self.daemon_started = 0
            self.ensure_daemon()

    def _toggle_autostart(self, on):
        if not self._service_installed():
            QMessageBox.information(self, tr("dialog.autostart_title"), tr("dialog.autostart_missing"))
            self.autostart.setChecked(False)
            return
        self._systemctl("enable" if on else "disable", SERVICE)

    def install_udev(self):
        src = os.path.join(DATA_DIR, "70-cam4linux.rules")
        if not shutil.which("pkexec"):
            cmds = ("sudo install -m644 %s %s\nsudo udevadm control --reload && sudo udevadm trigger"
                    % (src, UDEV_RULE))
            QMessageBox.warning(self, tr("dialog.access_title"), tr("dialog.access_no_pkexec", commands=cmds))
            return
        cmd = ("install -m644 '%s' '%s' && udevadm control --reload && "
               "udevadm trigger --subsystem-match=hidraw --action=change" % (src, UDEV_RULE))
        r = subprocess.run(["pkexec", "sh", "-c", cmd], capture_output=True, text=True)
        if r.returncode == 0:
            QMessageBox.information(self, tr("dialog.access_title"), tr("dialog.access_done"))
        elif self._account_locked():
            QMessageBox.warning(self, tr("dialog.access_title"), tr("dialog.access_locked"))
        else:
            QMessageBox.warning(self, tr("dialog.access_title"),
                                tr("dialog.access_failed", reason=r.stderr.strip() or tr("dialog.cancelled")))

    @staticmethod
    def _account_locked():
        """pam_faillock locks the account after (usually) 3 failures - every password is refused then."""
        if not shutil.which("faillock"):
            return False
        try:
            out = subprocess.run(["faillock", "--user", os.environ.get("USER", "")],
                                 capture_output=True, text=True, timeout=3).stdout
        except (OSError, subprocess.SubprocessError):
            return False
        return sum(1 for line in out.splitlines() if line.rstrip().endswith(" V")) >= 3

    def _banner_action(self):
        act = self.banner_btn.property("action")
        if act == "udev":
            self.install_udev()
        elif act == "start":
            self.daemon_started = 0
            self.ensure_daemon()

    def _show_banner(self, text, btn=None, action=None):
        if not text:
            self.banner.hide()
            return
        self.banner_text.setText(text)
        self.banner_btn.setVisible(bool(btn))
        if btn:
            self.banner_btn.setText(btn)
            self.banner_btn.setProperty("action", action)
        self.banner.show()

    # ------------------------------------------------------------------ periodic refresh
    def refresh(self):
        # Config changed by someone else (daemon fills in defaults on first start)?
        mt = config.config_mtime()
        if mt != self.cfg_mtime and not self.save_timer.isActive():
            self.cfg = config.load()
            self.cfg_mtime = mt
            self._load_fan_editor()
            self._load_led_editor()

        alive = self.daemon_alive()
        self.status = config.read_status() if alive else None
        if not alive:
            self.ensure_daemon()
            self.svc_label.setText(tr("service.starting"))
            self.svc_label.setStyleSheet("color: #d29922;")
            if time.monotonic() - self.daemon_started > 6:
                self._show_banner(tr("banner.not_running"), tr("service.start"), "start")
            return
        self.svc_label.setText(tr("service.active"))
        self.svc_label.setStyleSheet("color: #3fb950;")

        st = self.status
        dev = st.get("device")
        err = st.get("error")
        if dev:
            fw = dev.get("firmware")
            self.dev_label.setText(dev["name"] + ("   ·   " + tr("header.firmware", version=fw) if fw else ""))
        else:
            self.dev_label.setText(tr("header.no_device"))
        if err and err.get("code") == "no_access":
            self._show_banner(tr("banner.no_access"), tr("banner.no_access_btn"), "udev")
        elif err:
            self._show_banner(tr("error." + err.get("code", ""), **err.get("args", {})))
        else:
            self._show_banner(None)

        # fans
        fans = st.get("fans", {})
        self._ensure_cards(dev["fans"] if dev else 0)
        for ch, card in self.cards.items():
            f = fans.get(str(ch), {})
            fc = self._fan_cfg(ch)
            card.title.setText(fan_name(fc, ch))
            rpm = f.get("rpm")
            card.rpm.setText("%s RPM" % ("–" if rpm is None else rpm))
            parts = []
            if f.get("kick"):
                parts.append(tr("fan.state_kick"))
            elif f.get("stopped"):
                parts.append(tr("fan.state_off"))
            elif f.get("target") is not None:
                parts.append("%.0f %%" % f["target"])
            if f.get("temp") is not None:
                parts.append("%.0f °C" % f["temp"])
            if f.get("mode"):
                parts.append(f["mode"])
            if f.get("watts") is not None:
                parts.append("%.1f W" % f["watts"])
            card.info.setText(" · ".join(parts))
        sel = fans.get(str(self.sel_fan), {})
        self.curve.set_current(sel.get("temp") if self._fan_cfg().get("mode") == "curve" else None,
                               bool(sel.get("stopped")))
        self._update_zones()

        # sensors (labels in the source list + settings table)
        sensors = st.get("sensors", {})
        if self.sources.count() == 0 or self.sources.count() < len(sensors):
            self.loading = True
            self._fill_sources(self._fan_cfg().get("sources", []))
            self.loading = False
        else:
            for i in range(self.sources.count()):
                it = self.sources.item(i)
                info = sensors.get(it.data(Qt.UserRole))
                if info:
                    it.setText(self._source_text(info, it.data(Qt.UserRole)))
        if self.sensor_tree.topLevelItemCount() != len(sensors):
            self.sensor_tree.clear()
            for sid in sorted(sensors, key=lambda s: sensor_name(sensors[s])):
                it = QTreeWidgetItem([sensor_name(sensors[sid]), ""])
                it.setData(0, Qt.UserRole, sid)
                self.sensor_tree.addTopLevelItem(it)
            self.sensor_tree.resizeColumnToContents(0)
        for i in range(self.sensor_tree.topLevelItemCount()):
            it = self.sensor_tree.topLevelItem(i)
            t = sensors.get(it.data(0, Qt.UserRole), {}).get("temp")
            it.setText(1, "–" if t is None else "%.1f °C" % t)

        # LEDs
        if dev:
            self._update_led_channels(dev.get("leds", 0), dev.get("accessories", {}))
            if not dev.get("writable"):
                self.acc_label.setText("")  # detection needs device access

    def closeEvent(self, ev):
        if self.save_timer.isActive():
            self.save_timer.stop()
            self._save()
        super().closeEvent(ev)


def main():
    i18n.setup(config.load().get("language", "auto"))
    app = QApplication(sys.argv)
    app.setApplicationName("cam4linux")
    app.setDesktopFileName("cam4linux")
    app.main_window = MainWindow()
    app.main_window.show()
    return app.exec()
