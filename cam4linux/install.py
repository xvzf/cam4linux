"""
Self-installation, used by the single-file bundle (cam4linux.pyz) and install.sh.

Installs for the current user only - no root needed except for the udev rule,
which is requested once via the graphical polkit dialog (pkexec):

    ~/.local/share/cam4linux/cam4linux     program files
    ~/.local/bin/cam4linux                 launcher
    ~/.local/share/applications            app menu entry
    ~/.local/share/icons                   icon
    ~/.config/systemd/user                 background service (autostart)
    /etc/udev/rules.d/70-cam4linux.rules   device access (pkexec)
"""

import os
import shutil
import subprocess
import sys
import zipfile

from . import __version__

HOME = os.path.expanduser("~")
DATA_HOME = os.environ.get("XDG_DATA_HOME") or os.path.join(HOME, ".local", "share")
CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME") or os.path.join(HOME, ".config")
LIBDIR = os.path.join(DATA_HOME, "cam4linux")
PKGDIR = os.path.join(LIBDIR, "cam4linux")
BINDIR = os.path.join(HOME, ".local", "bin")
LAUNCHER = os.path.join(BINDIR, "cam4linux")
DESKTOP = os.path.join(DATA_HOME, "applications", "cam4linux.desktop")
ICON = os.path.join(DATA_HOME, "icons", "hicolor", "scalable", "apps", "cam4linux.svg")
UNIT = os.path.join(CONFIG_HOME, "systemd", "user", "cam4linux.service")
UDEV_RULE = "/etc/udev/rules.d/70-cam4linux.rules"
VERSION_FILE = os.path.join(LIBDIR, "VERSION")


def _systemctl(*args):
    if shutil.which("systemctl"):
        return subprocess.run(["systemctl", "--user", *args], capture_output=True).returncode
    return 1


def installed_version():
    try:
        with open(VERSION_FILE) as f:
            return f.read().strip()
    except OSError:
        return None


def udev_rule_ok():
    src = os.path.join(PKGDIR, "data", "70-cam4linux.rules")
    try:
        with open(src) as a, open(UDEV_RULE) as b:
            return a.read() == b.read()
    except OSError:
        return False


def udev_command(src):
    return ("install -m644 '%s' %s && udevadm control --reload && "
            "udevadm trigger --subsystem-match=hidraw --action=change" % (src, UDEV_RULE))


def install_udev_rule():
    """Ask for admin rights once (polkit dialog). Returns (ok, stderr)."""
    src = os.path.join(PKGDIR, "data", "70-cam4linux.rules")
    if not shutil.which("pkexec"):
        return False, "pkexec missing"
    r = subprocess.run(["pkexec", "sh", "-c", udev_command(src)], capture_output=True, text=True)
    return r.returncode == 0, r.stderr.strip()


def _copy_package(source):
    """source: a directory containing the cam4linux package, or a .pyz archive."""
    tmp = PKGDIR + ".new"
    shutil.rmtree(tmp, ignore_errors=True)
    if zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as z:
            for name in z.namelist():
                if name.startswith("cam4linux/") and not name.endswith("/"):
                    dest = os.path.join(tmp, name[len("cam4linux/"):])
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with z.open(name) as src, open(dest, "wb") as out:
                        shutil.copyfileobj(src, out)
    else:
        shutil.copytree(os.path.join(source, "cam4linux"), tmp,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.rmtree(PKGDIR, ignore_errors=True)
    os.replace(tmp, PKGDIR)


def _write(path, text, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    os.chmod(path, mode)


def install(source, udev=True):
    """Install or update from source. Returns a list of problems (empty = all fine)."""
    problems = []
    os.makedirs(LIBDIR, exist_ok=True)
    _copy_package(source)
    data = os.path.join(PKGDIR, "data")
    python = sys.executable or shutil.which("python3")

    _write(LAUNCHER, '#!/bin/sh\nPYTHONPATH="%s${PYTHONPATH:+:$PYTHONPATH}" exec "%s" -m cam4linux "$@"\n'
           % (LIBDIR, python), 0o755)
    with open(os.path.join(data, "cam4linux.desktop")) as f:
        _write(DESKTOP, f.read().replace("@BINDIR@/cam4linux", LAUNCHER))
    os.makedirs(os.path.dirname(ICON), exist_ok=True)
    shutil.copy(os.path.join(data, "cam4linux.svg"), ICON)
    with open(os.path.join(data, "cam4linux.service")) as f:
        _write(UNIT, f.read().replace("@PYTHON@", python).replace("@LIBDIR@", LIBDIR))
    _write(VERSION_FILE, __version__ + "\n")
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", os.path.dirname(DESKTOP)], capture_output=True)
    if shutil.which("kbuildsycoca6"):
        subprocess.run(["kbuildsycoca6"], capture_output=True)

    if udev and not udev_rule_ok():
        ok, err = install_udev_rule()
        if not ok:
            problems.append(("udev", err))

    _systemctl("daemon-reload")
    _systemctl("enable", "cam4linux.service")
    if _systemctl("restart", "cam4linux.service") != 0:
        problems.append(("service", "systemctl --user restart cam4linux.service failed"))
    return problems


def uninstall():
    _systemctl("disable", "--now", "cam4linux.service")
    for p in (LAUNCHER, DESKTOP, ICON, UNIT):
        try:
            os.unlink(p)
        except OSError:
            pass
    shutil.rmtree(LIBDIR, ignore_errors=True)
    _systemctl("daemon-reload")
    if os.path.exists(UDEV_RULE) and shutil.which("pkexec"):
        subprocess.run(["pkexec", "sh", "-c", "rm -f %s && udevadm control --reload" % UDEV_RULE])


def _message(title, text, error=False):
    """Show a message even when PySide6 is missing."""
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance() or QApplication(sys.argv)
        (QMessageBox.critical if error else QMessageBox.information)(None, title, text)
        return
    except ImportError:
        pass
    for cmd in (["kdialog", "--error" if error else "--msgbox", text, "--title", title],
                ["zenity", "--error" if error else "--info", "--title", title, "--text", text],
                ["notify-send", title, text]):
        if shutil.which(cmd[0]):
            subprocess.run(cmd)
            break
    print("%s: %s" % (title, text), file=sys.stderr)


def run_bundle(archive):
    """Entry point of cam4linux.pyz: install/update if needed, then start the installed app."""
    try:
        import PySide6  # noqa: F401
    except ImportError:
        _message("cam4linux",
                 "PySide6 (Qt for Python) is missing / fehlt.\n\n"
                 "Arch/CachyOS:  sudo pacman -S pyside6\n"
                 "Debian/Ubuntu:  sudo apt install python3-pyside6.qtwidgets\n"
                 "Fedora:  sudo dnf install python3-pyside6", error=True)
        return 1

    # Install on first start and after updates. The udev rule is only requested
    # then - if it was declined, the app shows a banner with a button instead.
    if installed_version() != __version__ or not os.path.isdir(PKGDIR):
        problems = install(archive)
        for kind, err in problems:
            print("cam4linux: %s: %s" % (kind, err), file=sys.stderr)
        # udev problems are shown in the app itself (banner + button), no extra dialog here

    env = dict(os.environ)
    env["PYTHONPATH"] = LIBDIR + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    os.execve(sys.executable, [sys.executable, "-m", "cam4linux"], env)


def main(argv):
    if "--uninstall" in argv:
        uninstall()
        print("cam4linux removed (settings kept in ~/.config/cam4linux)")
        return 0
    # --install from a source checkout: the directory containing the package
    source = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    problems = install(source)
    for kind, err in problems:
        print("!! %s: %s" % (kind, err))
        if kind == "udev":
            print("   Run in a terminal: sudo sh -c \"%s\""
                  % udev_command(os.path.join(PKGDIR, "data", "70-cam4linux.rules")))
    print("OK – cam4linux %s installed. Start it from the app menu." % __version__)
    return 0
