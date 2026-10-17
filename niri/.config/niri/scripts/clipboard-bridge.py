#!/usr/bin/env python3
"""Sync the X11 and Wayland text clipboards (started by niri, see config.kdl).

xwayland-satellite only syncs the clipboard while an X11 window has focus. VMware's
copy/paste helper (vmtoolsd -n vmusr) is a windowless X11 client, so without this,
text copied on the Mac never reaches Wayland apps and the reverse. Text only.

X11 -> Wayland: GTK's owner-change signal (XFixes), then wl-copy.
Wayland -> X11: `wl-paste --watch`, then this process owns the X11 selection.
Loops are cut by skipping text equal to the last value synced either way.
"""
import base64
import os
import subprocess

# The clipboard object below must be the X11 one. PyGObject initializes Gdk on import,
# so the backend has to be chosen before that (Gdk.set_allowed_backends is too late).
os.environ["GDK_BACKEND"] = "x11"

import gi  # noqa: E402

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

# One base64 line per Wayland clipboard change; empty line when it holds no text.
WATCH = ["wl-paste", "--type", "text", "--watch", "sh", "-c", "base64 -w0; echo"]

clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
last = None


def x11_to_wayland(_clipboard, text):
    global last
    if text and text != last:
        last = text
        subprocess.run(["wl-copy"], input=text.encode(), check=False)


def on_x11_owner_change(_clipboard, _event):
    clipboard.request_text(x11_to_wayland)


def on_wayland_line(source, _condition):
    global last
    line = source.readline()
    if not line:  # wl-paste exited: restart it, drop this watch
        GLib.timeout_add_seconds(1, start_watch)
        return False
    text = base64.b64decode(line.strip()).decode("utf-8", "replace")
    if text and text != last:
        last = text
        clipboard.set_text(text, -1)
    return True


def start_watch():
    proc = subprocess.Popen(WATCH, stdout=subprocess.PIPE)
    GLib.io_add_watch(proc.stdout, GLib.IO_IN | GLib.IO_HUP, on_wayland_line)
    return False


clipboard.connect("owner-change", on_x11_owner_change)
start_watch()
Gtk.main()
