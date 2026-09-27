"""
Durood Timer - Android (Kivy) control app.

Pairs with service.py, which runs the real timer + full-screen overlay as a
foreground Android service (works even while another app, e.g. YouTube, is
in front). This file is just the settings/start-stop UI.

Build with Buildozer (see buildozer.spec). Needs a manual "Draw over other
apps" permission grant on first run - use the button below.
"""

import json
import os

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.clock import Clock

try:
    from android.storage import app_storage_path
    DATA_DIR = app_storage_path()
    ON_ANDROID = True
except ImportError:
    DATA_DIR = os.path.expanduser("~/.durood_timer")
    ON_ANDROID = False

os.makedirs(DATA_DIR, exist_ok=True)
CONTROL_FILE = os.path.join(DATA_DIR, "control.json")

DEFAULT_CONTROL = {"running": False, "interval_minutes": 20}


def load_control():
    if os.path.exists(CONTROL_FILE):
        try:
            with open(CONTROL_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = DEFAULT_CONTROL.copy()
            merged.update(data)
            return merged
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_CONTROL.copy()


def save_control(control):
    with open(CONTROL_FILE, "w", encoding="utf-8") as f:
        json.dump(control, f, indent=2)


def request_overlay_permission():
    if not ON_ANDROID:
        return
    from jnius import autoclass
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Settings = autoclass("android.provider.Settings")
    Uri = autoclass("android.net.Uri")
    Intent = autoclass("android.content.Intent")

    activity = PythonActivity.mActivity
    if not Settings.canDrawOverlays(activity):
        intent = Intent(
            Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
            Uri.parse("package:" + activity.getPackageName()),
        )
        activity.startActivity(intent)


def request_ignore_battery_optimizations():
    if not ON_ANDROID:
        return
    from jnius import autoclass
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Intent = autoclass("android.content.Intent")
    Settings = autoclass("android.provider.Settings")
    Uri = autoclass("android.net.Uri")

    activity = PythonActivity.mActivity
    intent = Intent(
        Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
        Uri.parse("package:" + activity.getPackageName()),
    )
    activity.startActivity(intent)


def start_service():
    if not ON_ANDROID:
        return
    from jnius import autoclass
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Intent = autoclass("android.content.Intent")
    ServiceTimer = autoclass("org.kivy.android.PythonService")

    activity = PythonActivity.mActivity
    intent = Intent(activity, ServiceTimer)
    activity.startService(intent)


class RootWidget(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=20, spacing=12, **kwargs)
        self.control = load_control()

        self.add_widget(Label(text="Durood Timer", font_size=24, size_hint_y=None, height=50))

        self.status_label = Label(text="Stopped", font_size=18)
        self.add_widget(self.status_label)

        row = BoxLayout(size_hint_y=None, height=44, spacing=8)
        row.add_widget(Label(text="Interval (min):"))
        self.interval_input = TextInput(
            text=str(self.control["interval_minutes"]),
            multiline=False, input_filter="int",
        )
        row.add_widget(self.interval_input)
        self.add_widget(row)

        apply_btn = Button(text="Apply Interval", size_hint_y=None, height=44)
        apply_btn.bind(on_release=self.apply_interval)
        self.add_widget(apply_btn)

        overlay_btn = Button(text="Grant 'Draw over other apps'", size_hint_y=None, height=44)
        overlay_btn.bind(on_release=lambda *_: request_overlay_permission())
        self.add_widget(overlay_btn)

        battery_btn = Button(text="Ignore Battery Optimization", size_hint_y=None, height=44)
        battery_btn.bind(on_release=lambda *_: request_ignore_battery_optimizations())
        self.add_widget(battery_btn)

        self.toggle_btn = Button(
            text="Stop" if self.control["running"] else "Start",
            size_hint_y=None, height=54,
        )
        self.toggle_btn.bind(on_release=self.toggle_running)
        self.add_widget(self.toggle_btn)

        Clock.schedule_interval(self.refresh_status, 2)

    def apply_interval(self, *_):
        try:
            minutes = int(self.interval_input.text)
            if minutes <= 0:
                raise ValueError
        except ValueError:
            self.status_label.text = "Invalid interval"
            return
        self.control["interval_minutes"] = minutes
        save_control(self.control)

    def toggle_running(self, *_):
        self.control["running"] = not self.control["running"]
        save_control(self.control)
        self.toggle_btn.text = "Stop" if self.control["running"] else "Start"
        if self.control["running"]:
            start_service()

    def refresh_status(self, *_):
        control = load_control()
        remaining = control.get("remaining_seconds")
        if remaining is not None and control.get("running"):
            mins, secs = divmod(max(int(remaining), 0), 60)
            self.status_label.text = f"{mins:02d}:{secs:02d} remaining"
        elif not control.get("running"):
            self.status_label.text = "Stopped"


class DuroodTimerApp(App):
    def build(self):
        return RootWidget()


if __name__ == "__main__":
    DuroodTimerApp().run()
